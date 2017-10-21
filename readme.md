# Sans io implementation of instagram api
* Based on [php instagram api](https://github.com/mgp25/Instagram-API) and [python instagram api](https://github.com/LevPasha/Instagram-API-python).
* Have no
response wrappers, no upload picture/video/avatar.
* Have no api-methods documentation,
since I don't know what exactly some of them do.

## Implementation
[Sans io](http://sans-io.readthedocs.io/) implementation based on generators
for simplifying flow and holding state. `sioinstagram` have io backends based on:
* requests
* aiohttp
* [aiorequests](https://github.com/pohmelie/aiorequests)

## Documentation
Call `api` with any method of `Protocol` class.

## Example
``` python
import asyncio

import sioinstagram


USERNAME = "username"
PASSWORD = "password"


def requests_example():
    api = sioinstagram.RequestsInstagramApi()
    response = api.login(USERNAME, PASSWORD)
    print(response)


async def aiohttp_example():
    async with sioinstagram.AioHTTPInstagramApi() as api:
        response = await api.login(USERNAME, PASSWORD)
        print(response)


async def aiorequests_example():
    api = sioinstagram.AioRequestsInstagramApi()
    response = await api.login(USERNAME, PASSWORD)
    print(response)


if __name__ == "__main__":
    import time

    # requests
    requests_example()
    time.sleep(1)

    # aiohttp
    loop = asyncio.get_event_loop()
    loop.run_until_complete(aiohttp_example())
    time.sleep(1)

    # aiorequests
    import aiorequests
    import concurrent
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        loop = asyncio.get_event_loop()
        loop.set_default_executor(executor)
        aiorequests.set_async_requests(loop=loop)
        loop.run_until_complete(aiorequests_example())

```
