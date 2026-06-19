import json
import sys

from dbridge.protocol.transport.base import Transport


def write_message(stream, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    stream.write(header)
    stream.write(body)
    stream.flush()


def read_message(stream) -> dict | None:
    content_length = None
    while True:
        line = stream.readline()
        if not line:
            return None  # EOF
        line = line.strip()
        if line == b"":
            break  # end of headers
        if line.lower().startswith(b"content-length:"):
            content_length = int(line.split(b":", 1)[1].strip())
    if content_length is None:
        return None
    body = stream.read(content_length)
    return json.loads(body.decode("utf-8"))


class StdioTransport(Transport):
    def serve(self, dispatcher) -> None:
        stdin = sys.stdin.buffer
        stdout = sys.stdout.buffer
        while True:
            request = read_message(stdin)
            if request is None:
                break
            response = dispatcher.handle(request)
            if response is not None:
                write_message(stdout, response)
