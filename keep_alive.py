from aiohttp import web
import asyncio

async def handle(request):
    return web.Response(text="봇이 실행 중입니다!")

async def start_app():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 80)
    await site.start()
    print("✅ 헬스 체크 서버 실행 중 (8000)")

def keep_alive():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 이미 이벤트 루프가 돌고 있으면 create_task로 실행
            loop.create_task(start_app())
        else:
            # 이벤트 루프가 돌고 있지 않으면 run_until_complete 실행
            loop.run_until_complete(start_app())
    except RuntimeError:
        # 만약 이벤트 루프가 없으면 새로 만들고 실행
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        new_loop.run_until_complete(start_app())
