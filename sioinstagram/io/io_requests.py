import functools
import time
import threading
import contextlib

import requests

from ..protocol import Protocol
from ..exceptions import InstagramError


__all__ = (
    "RequestsInstagramApi",
)


class RequestsInstagramApi:

    def __init__(self, username, password, state=None, delay=5, proxy=None, lock=None):
        if proxy is None:
            self.proxies = None
        else:
            self.proxies = dict(http=proxy, https=proxy)
        self.proto = Protocol(username, password, state)
        self.delay = delay
        self.lock = lock or threading.Lock()
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

    def _run(self, generator):
        with self.lock:
            response = None
            with contextlib.suppress(StopIteration):
                while True:
                    request = generator.send(response)
                    now = time.monotonic()
                    timeout = max(0, self.delay - (now - self.last_request_time))
                    time.sleep(timeout)
                    self.last_request_time = time.monotonic()
                    response = requests.request(**request._asdict())
                    if not response.content:
                        raise InstagramError(response)
                    response = Protocol.Response(
                        cookies=response.cookies.get_dict(),
                        json=response.json(),
                        status_code=response.status_code,
                    )
        return response.json
