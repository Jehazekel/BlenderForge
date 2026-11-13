"""Errors and warnings with source line numbers."""

_state = {"path": "<input>", "warnings": 0, "quiet": False}


class ForgeError(Exception):
    """A problem in the input file. Carries the 1-based line number when known."""

    def __init__(self, message, line=None):
        self.message = message
        self.line = line
        super().__init__(self.format())

    def format(self):
        where = _state["path"]
        if self.line:
            where += ":%d" % self.line
        return "%s: error: %s" % (where, self.message)


def set_source(path):
    _state["path"] = path
    _state["warnings"] = 0


def warn(message, line=None):
    _state["warnings"] += 1
    where = _state["path"]
    if line:
        where += ":%d" % line
    print("[forge] %s: warning: %s" % (where, message))


def info(message):
    if not _state["quiet"]:
        print("[forge] " + message)


def warning_count():
    return _state["warnings"]
