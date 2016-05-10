class DatasetError(Exception):
    pass

class CommitError(Exception):
    pass

class CommitValidationFailed(CommitError):
    def __init__(self, message, violations=None):
        CommitError.__init__(self, message)
        if violations is None:
            violations = []
        self.violations = violations

class CommitNewerData(CommitError):
    def __init__(self, message, newer=None):
        CommitError.__init__(self, message)
        if newer is None:
            newer = []
        self.newer = newer

class CommitIncomplete(CommitError):
    """Indicates that a commit was successfully stored, but some hooks failed."""
    pass
