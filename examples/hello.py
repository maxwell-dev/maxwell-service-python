import asyncio
import logging
import json
import threading
import traceback

from maxwell.server.server import Server
from maxwell.server.app import App
from maxwell.server.publisher import Publisher


logger = logging.getLogger(__name__)
app = App()


@app.ws("/hello")
def hello():
    logger.info("hello")
    return json.dumps("world")


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
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=run_publisher, args=(loop,), daemon=True)
    t.start()
    Server(app).run()
