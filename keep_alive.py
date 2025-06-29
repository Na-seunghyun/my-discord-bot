from aiohttp import web
import asyncio

async def handle(request):
    if request.method == 'HEAD':
        # HEAD 요청에는 본문 없이 200 OK 상태만 응답
        return web.Response(status=200)
    # GET 요청에는 본문 포함 응답
    return web.Response(text="봇이 실행 중입니다!")

async def start_app():
    app = web.Application()
    # GET과 HEAD 모두 handle 함수로 처리하도록 라우팅
    app.router.add_route('*', '/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8000)
    await site.start()
    print("✅ 헬스 체크 서버 실행 중 (8000)")

def keep_alive():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(start_app())
        else:
            loop.run_until_complete(start_app())
    except RuntimeError:
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        new_loop.run_until_complete(start_app())
