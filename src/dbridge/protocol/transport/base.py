from abc import ABC, abstractmethod


class Transport(ABC):
    @abstractmethod
    def serve(self, dispatcher) -> None: ...
