import asyncio
import functools

import aiorequests

from ..protocol import Protocol, Response
from ..exceptions import InstagramStatusCodeError


__all__ = (
    "AioRequestsInstagramApi",
)


class AioRequestsInstagramApi:

    def __init__(self, state=None, delay=5, proxy=None, loop=None, lock=None):
        self.session = aiorequests.Session()
        if proxy is not None:
            self.session.proxies = dict(http=proxy, https=proxy)
        self.proto = Protocol(state)
        cookies = aiorequests.cookies.cookiejar_from_dict(self.proto.cookies)
        self.session.cookies = cookies
        self.delay = delay
        self.loop = loop or asyncio.get_event_loop()
        self.lock = lock or asyncio.Lock(loop=self.loop)
        self.last_request_time = 0

    def close(self):
        self.session.close()

    @property
    def state(self):
        return self.proto.state

    def __getattr__(self, name):
        method = getattr(self.proto, name)

        @functools.wraps(method)
        def wrapper(*args, **kwargs):
            return self._run(method(*args, **kwargs))

        return wrapper

    async def _run(self, generator):
        with (await self.lock):
            response = None
            while True:
                request = generator.send(response)
                if request is None:
                    break
                now = self.loop.time()
                timeout = max(0, self.delay - (now - self.last_request_time))
                await asyncio.sleep(timeout, loop=self.loop)
                self.last_request_time = self.loop.time()
                response = await self.session.request(**request._asdict())
                if response.status_code != aiorequests.codes.ok:
                    raise InstagramStatusCodeError(response.status_code)
                response = Response(
                    cookies=self.session.cookies.get_dict(),
                    json=response.json(),
                )

        return response.json
