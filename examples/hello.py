import asyncio
import logging
import json
import threading
import traceback

from maxwell.service.server import Server
from maxwell.service.service import Service
from maxwell.service.publisher import Publisher

logger = logging.getLogger(__name__)
service = Service()


# def build_candles():
#     candles = []
#     for i in range(0, 30000):
#         candles.append(
#             {
#                 "ts": i,
#                 "open": i + 1,
#                 "high": i + 2,
#                 "low": i + 3,
#                 "close": i + 4,
#                 "volume": i + 5,
#             }
#         )
#     return candles


@service.ws("/hello")
async def hello(req):
    logger.debug(" %s ", req)
    # return json.dumps(build_candles())
    return json.dumps("python")


async def run_publisher_coro(loop):
    publisher = Publisher(options={}, loop=loop)
    while True:
        try:
            logger.error("publishing a message!!!")
            await publisher.publish("topic_3", b"hello world")
            logger.error("published.")
        except Exception:
            logger.error("Failed to publish: %s", traceback.format_exc())

        await asyncio.sleep(1)


def run_publisher(loop):
    loop.run_until_complete(run_publisher_coro(loop))


if __name__ == "__main__":
    # loop = asyncio.new_event_loop()
    # t = threading.Thread(target=run_publisher, args=(loop,), daemon=True)
    # t.start()
    Server(service.register()).run()
