import functools
import time
import threading

import requests

from ..protocol import Protocol, Response
from ..exceptions import InstagramStatusCodeError


__all__ = (
    "RequestsInstagramApi",
)


class RequestsInstagramApi:

    def __init__(self, state=None, delay=5, proxy=None, lock=None):
        self.session = requests.Session()
        if proxy is not None:
            self.session.proxies = dict(http=proxy, https=proxy)
        self.proto = Protocol(state)
        cookies = requests.cookies.cookiejar_from_dict(self.proto.cookies)
        self.session.cookies = cookies
        self.delay = delay
        self.lock = lock or threading.Lock()
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

    def _run(self, generator):
        with self.lock:
            response = None
            while True:
                request = generator.send(response)
                if request is None:
                    break
                now = time.monotonic()
                timeout = max(0, self.delay - (now - self.last_request_time))
                time.sleep(timeout)
                self.last_request_time = time.monotonic()
                response = self.session.request(**request._asdict())
                if response.status_code != requests.codes.ok:
                    raise InstagramStatusCodeError(response.status_code)
                response = Response(
                    cookies=self.session.cookies.get_dict(),
                    json=response.json(),
                )

        return response.json
