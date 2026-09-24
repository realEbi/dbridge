"""FIFO execution on a connection's owning thread."""

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
import threading
from typing import Any, Generic, TypeVar

from dbridge.logging import get_logger

T = TypeVar("T")


@dataclass(eq=False)
class _Job(Generic[T]):
    call: Callable[[], T]
    future: asyncio.Future[T]
    cancelled: bool = False
    finished: bool = False


class Lane:
    """One daemon worker with cancellation synchronized to its current job.

    The loop owns futures. The condition protects the queue and current job,
    including the interrupt call, so a late cancel cannot hit the following job.
    """

    def __init__(
        self,
        name: str,
        interrupt: Callable[[], None],
        is_interruption: Callable[[BaseException], bool],
    ) -> None:
        self._loop = asyncio.get_running_loop()
        self._interrupt = interrupt
        self._is_interruption = is_interruption
        self._condition = threading.Condition()
        self._queue: deque[_Job[Any]] = deque()
        self._current: _Job[Any] | None = None
        self._closing = False
        self._cleanup: Callable[[], None] | None = None
        self._stopped: asyncio.Future[None] = self._loop.create_future()
        self.thread = threading.Thread(target=self._work, name=name, daemon=True)
        self.thread.start()

    async def run(self, call: Callable[[], T]) -> T:
        job = _Job(call, self._loop.create_future())
        with self._condition:
            if self._closing:
                raise RuntimeError("lane is closed")
            self._queue.append(job)
            self._condition.notify()
        cancel_requested = False
        while True:
            try:
                if cancel_requested:
                    done, _ = await asyncio.wait([job.future], timeout=0.02)
                    if not done:
                        self._cancel(job)
                        continue
                return await asyncio.shield(job.future)
            except asyncio.CancelledError:
                if job.future.done():
                    # Completion wins even if cancellation reached the waiter
                    # before the loop delivered the already-completed outcome.
                    return job.future.result()
                self._cancel(job)
                cancel_requested = True

    def _cancel(self, job: _Job[Any]) -> None:
        with self._condition:
            if job.finished:
                return
            job.cancelled = True
            if self._current is job:
                self._interrupt()
            else:
                self._queue.remove(job)
                job.finished = True
                job.future.cancel()

    async def close(self) -> None:
        """Drain submitted work and stop; callers cancel outstanding work first."""
        with self._condition:
            self._closing = True
            self._condition.notify()
        await asyncio.shield(self._stopped)
        self.thread.join()

    def abandon(self, cleanup: Callable[[], None]) -> None:
        """Release loop waiters and defer cleanup to a possibly stuck worker."""
        with self._condition:
            self._closing = True
            self._cleanup = cleanup
            for job in self._queue:
                job.finished = True
                job.future.cancel()
            self._queue.clear()
            if self._current is not None:
                self._current.future.cancel()
            self._stopped.cancel()
            self._condition.notify()

    def _post(self, callback: Callable[[], None]) -> None:
        try:
            self._loop.call_soon_threadsafe(callback)
        except RuntimeError:
            # Shutdown can abandon an uninterruptible daemon job and close its
            # loop. There is no surviving request to receive that late result.
            pass

    def _work(self) -> None:
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._queue or self._closing)
                if not self._queue:
                    break
                job = self._queue.popleft()
                self._current = job
            result: Any = None
            error: BaseException | None = None
            try:
                result = job.call()
            except BaseException as exc:
                error = exc
            with self._condition:
                self._current = None
                job.finished = True
                if error is not None and job.cancelled and self._is_interruption(error):
                    error = asyncio.CancelledError()
            self._post(partial(self._deliver, job, result, error))
        try:
            if self._cleanup is not None:
                self._cleanup()
        except Exception:
            get_logger().exception("Abandoned lane cleanup failed")
        finally:
            self._post(self._did_stop)

    def _did_stop(self) -> None:
        if not self._stopped.done():
            self._stopped.set_result(None)

    @staticmethod
    def _deliver(job: _Job[Any], result: Any, error: BaseException | None) -> None:
        if job.future.done():
            return
        if error is None:
            job.future.set_result(result)
        elif isinstance(error, asyncio.CancelledError):
            job.future.cancel()
        else:
            job.future.set_exception(error)
