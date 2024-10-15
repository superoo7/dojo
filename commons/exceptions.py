class NoNewUnexpiredTasksYet(Exception):
    """Exception raised when no unexpired tasks are found for processing."""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class UnexpiredTasksAlreadyProcessed(Exception):
    """Exception raised when all unexpired tasks have already been processed."""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
