__all__ = (
    "InstagramStatusCodeError",
)


class InstagramStatusCodeError(Exception):

    def __init__(self, status_code):
        self.status_code = status_code

    def __repr__(self):
        return f"InstagramStatusCodeError(status_code={self.status_code!r})"
