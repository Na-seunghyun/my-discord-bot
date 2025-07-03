import asyncio

auto_disconnect_tasks = {}

async def auto_disconnect_after_timeout(user, channel, timeout=1200):
    await asyncio.sleep(timeout)
    if user.voice and user.voice.channel == channel:
        try:
            await user.move_to(None)
            text_channel = user.guild.get_channel_by_name("자유채팅방")  # get_channel_by_name 함수 직접 구현 필요
            if text_channel:
                await text_channel.send(f"{user.mention} 님, 20분 지나서 자동 퇴장당했어요. 🍚")
        except Exception as e:
            print(f"오류: {e}")
    auto_disconnect_tasks.pop(user.id, None)

