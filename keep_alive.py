# keep_alive.py
from aiohttp import web
import asyncio

async def handle(request):
    return web.Response(text="봇이 실행 중입니다!")

def keep_alive():
    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)

    async def start_app():
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8080)
        await site.start()

    loop = asyncio.get_event_loop()
    loop.create_task(start_app())
