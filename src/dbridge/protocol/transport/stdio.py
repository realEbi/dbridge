import asyncio
import json
import sys
import threading
from dataclasses import dataclass
from typing import BinaryIO

from dbridge.logging import get_logger
from dbridge.protocol import errors
from dbridge.protocol.handlers import Dispatcher
from dbridge.protocol.messages import make_error
from dbridge.protocol.transport.base import Transport

logger = get_logger(__name__)
SHUTDOWN_GRACE_SECONDS = 1.0


@dataclass(frozen=True)
class FrameError:
    message: str
    fatal: bool


def write_message(stream, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    stream.write(header)
    stream.write(body)
    stream.flush()


def read_message(stream):
    content_length = None
    saw_header = False
    while True:
        line = stream.readline()
        if not line:
            return FrameError("truncated frame headers", True) if saw_header else None
        saw_header = True
        line = line.strip()
        if line == b"":
            break
        if line.lower().startswith(b"content-length:"):
            try:
                content_length = int(line.split(b":", 1)[1].strip())
            except ValueError:
                return FrameError("invalid Content-Length", True)
            if content_length < 0:
                return FrameError("negative Content-Length", True)
    if content_length is None:
        return FrameError("missing Content-Length", True)
    body = bytearray()
    while len(body) < content_length:
        chunk = stream.read(content_length - len(body))
        if not chunk:
            return FrameError("truncated frame body", True)
        body.extend(chunk)
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        return FrameError("frame body is not valid UTF-8 JSON", False)


class StdioTransport(Transport):
    def __init__(self, stdin: BinaryIO | None = None, stdout: BinaryIO | None = None) -> None:
        self._stdin = stdin
        self._stdout = stdout

    async def serve(self, dispatcher: Dispatcher) -> None:
        stdin = self._stdin if self._stdin is not None else sys.stdin.buffer
        stdout = self._stdout if self._stdout is not None else sys.stdout.buffer
        loop = asyncio.get_running_loop()
        incoming: asyncio.Queue = asyncio.Queue()
        stopped = threading.Event()

        def read_frames() -> None:
            while not stopped.is_set():
                try:
                    frame = read_message(stdin)
                except OSError as exc:
                    frame = FrameError(f"input read failed: {exc}", True)
                try:
                    loop.call_soon_threadsafe(incoming.put_nowait, frame)
                except RuntimeError:
                    return  # The loop has already closed after shutdown.
                if frame is None or isinstance(frame, FrameError) and frame.fatal:
                    return

        reader = threading.Thread(target=read_frames, name="dbridge-stdio-reader", daemon=True)
        reader.start()
        output_open = True

        def respond(response: dict) -> None:
            nonlocal output_open
            if output_open:
                try:
                    write_message(stdout, response)
                except (OSError, ValueError):
                    output_open = False
                    logger.debug("Output closed while writing a reply")

        try:
            while True:
                frame = await incoming.get()
                if frame is None:
                    break
                if isinstance(frame, FrameError):
                    if frame.fatal:
                        logger.warning("Stopping after framing error: %s", frame.message)
                        break
                    respond(make_error(None, errors.PARSE_ERROR, frame.message))
                else:
                    dispatcher.submit(frame, respond)
                # Start accepted requests in intake order, including queued DB work.
                await asyncio.sleep(0)
        finally:
            stopped.set()
            await self._shutdown(dispatcher)

    async def _shutdown(self, dispatcher: Dispatcher) -> None:
        requests = [pending.task for pending in dispatcher.pending.values()]
        for task in requests:
            task.cancel()

        async def drain_and_close() -> None:
            if requests:
                await asyncio.gather(*requests, return_exceptions=True)
            await dispatcher.engine.close_all()

        cleanup = asyncio.create_task(drain_and_close())
        done, _ = await asyncio.wait({cleanup}, timeout=SHUTDOWN_GRACE_SECONDS)
        if not done:
            logger.warning("Shutdown grace expired; abandoning driver lanes: connection cleanup incomplete")
            dispatcher.engine.abandon()
            cleanup.cancel()
            for task in requests:
                task.cancel()
        await asyncio.gather(cleanup, return_exceptions=True)
