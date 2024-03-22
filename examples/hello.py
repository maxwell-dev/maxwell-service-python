import asyncio
import contextlib
import json
import threading
from typing import Annotated
from fastapi import APIRouter, Body, UploadFile
from fastapi.staticfiles import StaticFiles

from maxwell.utils.logger import get_logger
from maxwell.service.server import Server
from maxwell.service.service import Service, Request, Reply
from maxwell.service.publisher import Publisher

logger = get_logger(__name__)


@contextlib.asynccontextmanager
async def lifespan(service):
    logger.info("on service start: %s", service)
    yield
    logger.info("on service end: %s", service)


service = Service(
    lifespan=lifespan,
    # root_path="/maxwell-service-python",
)


# The following code should be called on startup and shutdown,
# but not called because of the asynccontextmanager above.
service.add_event_handler("startup", lambda: logger.info("on startup 1"))
service.add_event_handler("startup", lambda: logger.info("on startup 2"))
service.add_event_handler("shutdown", lambda: logger.info("on shutdown 1"))
service.add_event_handler("shutdown", lambda: logger.info("on shutdown 2"))


# ************************************************
# http related routes
# ************************************************
# example: curl -X GET http://127.0.0.1:9091/candles/1?q=1
@service.get("/candles/{id}", tags=["candle"])
async def get_candle(q: str | None = None):
    return json.dumps(build_candles(1)[0])


# example: curl -X PUT -d "b=" http://127.0.0.1:9091/candles/1
@service.put("/candles/{id}", tags=["candle"])
async def update_candle(b: Annotated[str, Body()]):
    logger.info(" %s ", b)
    return json.dumps(build_candles(1)[0])


# example: curl -X POST -d "b=" http://127.0.0.1:9091/candles/
@service.post("/candles/", tags=["candle"])
async def create_candle(b: Annotated[str, Body()]):
    logger.info(" %s ", b)
    return json.dumps(build_candles(1)[0])


# example: curl -X POST -F "file=@./examples/hello.py" http://localhost:9091/upload_file
@service.post("/upload_file", tags=["file"])
async def create_file(file: UploadFile):
    content = await file.read()
    logger.info("filename: %s, content_length: %s", file.filename, len(content))
    return {"filename": file.filename, "content": content}


router = APIRouter()


# example: curl -X GET http://127.0.0.1:9091/users/
@router.get("/users/", tags=["user"])
async def read_users():
    return [{"username": "Rick"}, {"username": "Morty"}]


service.include_router(router=router)

# example: curl -X GET http://127.0.0.1:9091/static/hello.py
service.mount("/static", StaticFiles(directory="examples"), name="static")


# ************************************************
# ws related routes
# ************************************************
def add_ws_route_later():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(add_ws_route_later_coro())


async def add_ws_route_later_coro():
    @service.add_ws_route("/hello")
    async def hello(req: Request):
        logger.debug(" %s ", req)
        return Reply(payload="world")

    @service.add_ws_route("/hello2")
    async def hello2(req: Request):
        logger.debug(" %s ", req)
        return Reply(payload="world2")

    await asyncio.sleep(1)

    @service.add_ws_route("/hello3")
    async def hello3(req: Request):
        logger.debug(" %s ", req)
        return Reply(payload="world3")


@service.ws("/get_candles")
async def get_candles(req):
    logger.debug(" %s ", req)
    return json.dumps(build_candles())


# ************************************************
# publisher
# ************************************************
def run_publisher():
    loop = asyncio.new_event_loop()
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


# ************************************************
# utils functions
# ************************************************
def build_candles(length=30000):
    candles = []
    for i in range(0, length):
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


# ************************************************
# main block
# ************************************************
if __name__ == "__main__":
    t = threading.Thread(target=add_ws_route_later, daemon=True)
    t.start()

    # t2 = threading.Thread(target=run_publisher, daemon=True)
    # t2.start()

    Server(f"{__name__}:service").run()
