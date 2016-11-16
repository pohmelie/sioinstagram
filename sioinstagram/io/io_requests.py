import functools
import time
import threading

import requests

from ..protocol import *


__all__ = (
    "RequestsInstagramApi",
)


class RequestsInstagramApi:

    def __init__(self, state=None, delay=1, proxy=None, lock=None):

        self.session = requests.Session()
        if proxy is not None:

            self.session.proxies = dict(http=proxy, https=proxy)

        self.proto = Protocol(state)
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
            while True:

                request = generator.send(response)
                if request is None:

                    break

                now = time.perf_counter()
                timeout = max(0, self.delay - (now - self.last_request_time))
                time.sleep(timeout)

                self.last_request_time = time.perf_counter()
                response = self.session.request(**request._asdict())

                response = Response(
                    cookies=response.cookies,
                    json=response.json(),
                )

        return response.json
