__all__ = (
    "InstagramError",
    "InstagramProtocolError",
)


class InstagramError(Exception):

    def __init__(self, response):
        self.response = response

    def __repr__(self):
        return f"{self.__class__.__name__}(response={self.response!r})"


class InstagramProtocolError(InstagramError):
    pass
