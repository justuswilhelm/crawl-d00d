"""The frontend for crawl-d00d."""
import logging
from os import getenv

from aiohttp import web
from asyncio import sleep
from redis import Redis
import jinja2
import aiohttp_jinja2

redis = Redis.from_url(getenv('REDIS_URL', 'redis://localhost:6379/'))


@aiohttp_jinja2.template('index.html')
async def index(request):
    """Serve the index."""
    return {'WEBSOCKET_URL': getenv("WEBSOCKET_URL")}


async def websocket_handler(request):
    """PubSub and send messages to listener."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    p = redis.pubsub()
    p.subscribe('titles')
    while True:
        message = p.get_message()
        if message and message['type'] == 'message':
            ws.send_str(message['data'].decode())
        await sleep(0.0001)

    logging.info('websocket connection closed')
    return ws

application = web.Application()
application.router.add_route('GET', '/', index)
application.router.add_route('GET', '/ws', websocket_handler)
aiohttp_jinja2.setup(
    application, loader=jinja2.FileSystemLoader('./templates/'))

if __name__ == "__main__":
    web.run_app(application)
