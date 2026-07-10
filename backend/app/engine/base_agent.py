from abc import ABC, abstractmethod
from app.engine.state import EngineState

class BaseAgent(ABC):

    @abstractmethod
    async def run(self, state: EngineState) -> EngineState:
        """
        Reads the engine state,
        updates it,
        returns it
        """
        pass