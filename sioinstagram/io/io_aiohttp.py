import asyncio
import functools

import aiohttp

from ..protocol import *


__all__ = (
    "AioHTTPInstagramApi",
)


class AioHTTPInstagramApi:

    def __init__(self, state=None, delay=1, proxy=None, loop=None, lock=None):

        if proxy:

            conn = aiohttp.ProxyConnector(proxy=proxy)

        else:

            conn = None

        self.session = aiohttp.ClientSession(loop=loop, connector=conn)

        self.proto = Protocol(state)
        self.delay = delay
        self.loop = loop or asyncio.get_event_loop()
        self.lock = lock or asyncio.Lock(loop=self.loop)
        self.last_request_time = 0

    async def close(self):

        await self.session.close()

    async def __aenter__(self):

        return self

    def __aexit__(self, exc_type, exc, tb):

        return self.close()

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
                async with self.session.request(**request._asdict()) as resp:

                    response = Response(
                        cookies=resp.cookies,
                        json=(await resp.json()),
                    )

        return response.json
