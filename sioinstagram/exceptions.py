__all__ = (
    "InstagramStatusCodeError",
)


class InstagramStatusCodeError(Exception):

    def __init__(self, status_code):

        self.status_code = status_code

    def __repr__(self):

        return str.format(
            "InstagramStatusCodeError(status_code={!r})",
            self.status_code,
        )
