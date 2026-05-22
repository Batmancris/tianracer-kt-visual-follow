
class BaseChecker:
    def __init__(self, platform, logger):
        self.platform = platform
        self.logger = logger
        self.results = {}

    def run(self, config):
        raise NotImplementedError("Subclasses must implement run()")
