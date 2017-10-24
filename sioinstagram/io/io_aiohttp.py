import asyncio
import functools
import contextlib

import aiohttp

from ..protocol import Protocol
from ..exceptions import InstagramError


__all__ = (
    "AioHTTPInstagramApi",
)


class AioHTTPInstagramApi:

    def __init__(self, username, password, state=None, delay=5, proxy=None, loop=None, lock=None):
        if proxy is None:
            self._conn = None
        else:
            self._conn = aiohttp.ProxyConnector(proxy=proxy)
        self.proto = Protocol(username, password, state)
        self.delay = delay
        self.loop = loop or asyncio.get_event_loop()
        self.lock = lock or asyncio.Lock(loop=self.loop)
        self.last_request_time = 0

    @property
    def state(self):
        return self.proto.state

    def __getattr__(self, name):
        method = getattr(self.proto, name)

        @functools.wraps(method)
        def wrapper(*args, **kwargs):
            return self._run(method(*args, **kwargs))

        return wrapper

    async def _request(self, request):
        kw = request._asdict()
        async with aiohttp.ClientSession(cookies=kw.pop("cookies")) as session:
            async with session.request(**kw) as response:
                if not await response.read():
                    raise InstagramError(response)
                return Protocol.Response(
                    cookies={c.key: c.value for c in session.cookie_jar},
                    json=await response.json(),
                    status_code=response.status,
                )

    async def _run(self, generator):
        with (await self.lock):
            response = None
            with contextlib.suppress(StopIteration):
                while True:
                    request = generator.send(response)
                    now = self.loop.time()
                    timeout = max(0, self.delay - (now - self.last_request_time))
                    await asyncio.sleep(timeout, loop=self.loop)
                    self.last_request_time = self.loop.time()
                    response = await self._request(request)
        return response.json
