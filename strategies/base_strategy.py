from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    def __init__(self, name, config):
        self.name = name
        self.config = config

    @abstractmethod
    async def analyze(self, symbol, data, sentiment, regime):
        pass
