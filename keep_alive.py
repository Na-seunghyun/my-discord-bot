# keep_alive.py
from aiohttp import web
import asyncio

async def handle(request):
    return web.Response(text="봇이 실행 중입니다!")

async def start_app():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("✅ 헬스 체크 서버 실행 중 (8080)")

def keep_alive():
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(start_app())
    except RuntimeError:
        # 이미 실행 중이면 create_task 사용
        asyncio.create_task(start_app())
