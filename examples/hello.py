import logging
import json

from maxwell.server.server import Server
from maxwell.server.app import App

logger = logging.getLogger(__name__)
app = App()


@app.ws("/hello")
def hello():
    logger.info("hello")
    return json.dumps("world")


if __name__ == "__main__":
    Server(app).run()
