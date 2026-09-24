from abc import ABC, abstractmethod


class Transport(ABC):
    @abstractmethod
    async def serve(self, dispatcher) -> None: ...
