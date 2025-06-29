from aiohttp import web
import asyncio

async def handle(request):
    return web.Response(text="🐰 토끼록끼가 살아 있습니다!")

async def start_app():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8080)
    await site.start()
    print("✅ 헬스체크 서버가 8080 포트에서 실행 중입니다.")

    # 무한 대기 상태 유지
    while True:
        await asyncio.sleep(3600)

def keep_alive():
    loop = asyncio.get_event_loop()
    loop.create_task(start_app())
