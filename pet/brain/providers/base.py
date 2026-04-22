from abc import ABC, abstractmethod


class Provider(ABC):
    @abstractmethod
    def complete(self, system: str, user: str) -> str: ...
