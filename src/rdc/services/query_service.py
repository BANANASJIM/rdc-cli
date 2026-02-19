
def _rid(value: Any) -> int:
    return int(getattr(value, "value", 0))
