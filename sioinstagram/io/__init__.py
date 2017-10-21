import contextlib


__all__ = ()

with contextlib.suppress(ImportError):
    from .io_aiorequests import AioRequestsInstagramApi
    __all__ += io_aiorequests.__all__


with contextlib.suppress(ImportError):
    from .io_aiohttp import AioHTTPInstagramApi
    __all__ += io_aiohttp.__all__


with contextlib.suppress(ImportError):
    from .io_requests import RequestsInstagramApi
    __all__ += io_requests.__all__
