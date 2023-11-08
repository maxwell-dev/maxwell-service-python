import asyncio
import json
import threading
from maxwell.utils.logger import get_logger
from maxwell.service.server import Server
from maxwell.service.service import Service, Request, Reply
from maxwell.service.publisher import Publisher

logger = get_logger(__name__)
service = Service()


@service.add_ws_route("/hello")
async def hello(req: Request):
    logger.debug(" %s ", req)
    return Reply(payload="python")


@service.ws("/get_candles")
async def get_candles(req):
    logger.debug(" %s ", req)
    return json.dumps(build_candles())


def build_candles():
    candles = []
    for i in range(0, 30000):
        candles.append(
            {
                "ts": i,
                "open": i + 1,
                "high": i + 2,
                "low": i + 3,
                "close": i + 4,
                "volume": i + 5,
            }
        )
    return candles


def run_publisher(loop):
    loop.run_until_complete(run_publisher_coro(loop))


async def run_publisher_coro(loop):
    publisher = Publisher(options={}, loop=loop)
    while True:
        try:
            rep = await publisher.publish("topic_1", b"hello world")
            logger.info("***published: %s", rep)
        except Exception as e:
            logger.error("Failed to publish: %s", e)

        await asyncio.sleep(1)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=run_publisher, args=(loop,), daemon=True)
    t.start()
    Server(service.register()).run()
