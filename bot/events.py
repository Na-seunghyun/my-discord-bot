import asyncio
from datetime import datetime, timezone, timedelta
import re

from discord import Embed, utils
from bot.bot_instance import bot, tree, supabase, GUILD_ID

nickname_pattern = re.compile(r"^[가-힣a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/\d{2}$")

MONITORED_CHANNEL_NAMES = [f"일반{i}" for i in range(1, 17)] + ["큰맵1", "큰맵2"]

auto_disconnect_tasks = {}
voice_join_times = {}
streaming_members = set()
waiting_room_message_cache = {}
voice_activity_cache = {}
channel_last_empty = {}
all_empty_since = None
notified_after_empty = False

# 함수: 자동 퇴장 구현
async def auto_disconnect_after_timeout(user, channel, timeout=1200):
    await asyncio.sleep(timeout)
    if user.voice and user.voice.channel == channel:
        try:
            await user.move_to(None)
            text_channel = utils.get(user.guild.text_channels, name="자유채팅방")
            if text_channel:
                await text_channel.send(f"{user.mention} 님, 20분 지나서 자동 퇴장당했어요. 🍚")
        except Exception as e:
            print(f"오류: {e}")
    auto_disconnect_tasks.pop(user.id, None)

def sql_escape(s):
    if s is None:
        return 'NULL'
    return "'" + str(s).replace("'", "''") + "'"

# 이벤트: 음성 상태 업데이트 감지
@bot.event
async def on_voice_state_update(member, before, after):
    global streaming_members, all_empty_since, notified_after_empty

    if member.bot:
        return

    if member.id in auto_disconnect_tasks:
        auto_disconnect_tasks[member.id].cancel()
        auto_disconnect_tasks.pop(member.id, None)

    now_utc = datetime.utcnow()

    if (before.channel != after.channel) and (after.channel is not None):
        if after.channel.name == "대기방":
            last_sent = waiting_room_message_cache.get(member.id)
            if not last_sent or (now_utc - last_sent) > timedelta(seconds=30):
                text_channel = utils.get(member.guild.text_channels, name="자유채팅방")
                if text_channel:
                    await text_channel.send(f"{member.mention} 나도 게임하고싶어! 나 도 끼 워 줘!")
                    waiting_room_message_cache[member.id] = now_utc

    # 수정된 배그 채널 입장 감지
    now = datetime.now(timezone.utc)
    guild = member.guild
    monitored_channels = [ch for ch in guild.voice_channels if ch.name in MONITORED_CHANNEL_NAMES]

    all_empty = all(len(ch.members) == 0 for ch in monitored_channels)

    if before.channel and before.channel.name in MONITORED_CHANNEL_NAMES:
        if all_empty:
            if all_empty_since is None:
                all_empty_since = now
                notified_after_empty = False
                print(f"⚠️ 모든 모니터링 채널 비어있음 - 시간 기록 시작: {all_empty_since.isoformat()}")

    if before.channel is None and after.channel and after.channel.name in MONITORED_CHANNEL_NAMES:
        if all_empty_since and (now - all_empty_since).total_seconds() >= 3600 and not notified_after_empty:
            text_channel = utils.get(guild.text_channels, name="자유채팅방")
            if text_channel:
                embed = Embed(
                    title="🚀 첫 배그 포문이 열립니다!",
                    description=(
                        f"{member.mention} 님이 첫 배그 포문을 열려고 합니다.\n\n"
                        "같이 해주실 인원들은 현시간 부로 G-pop 바랍니다."
                    ),
                    color=discord.Color.blue()
                )
                await text_channel.send(content='@everyone', embed=embed)
                print("📢 G-pop 안내 메시지 전송됨 ✅")
            notified_after_empty = True

    if not all_empty:
        all_empty_since = None
        notified_after_empty = False

    if before.channel is None and after.channel is not None:
        voice_join_times[member.id] = datetime.now(timezone.utc).replace(microsecond=0)

    elif before.channel is not None and after.channel is None:
        join_time = voice_join_times.pop(member.id, None)
        if join_time:
            left_time = datetime.now(timezone.utc).replace(microsecond=0)
            duration = int((left_time - join_time).total_seconds())

            if before.channel and len(before.channel.members) == 0:
                channel_last_empty[before.channel.id] = left_time
                print(f"📌 '{before.channel.name}' 채널이 비었음 — 시간 기록됨")

            last_save_time = voice_activity_cache.get(member.id)
            if last_save_time and (left_time - last_save_time) < timedelta(seconds=3):
                print(f"중복 저장 방지: {member.id} - 최근 저장 시간 {last_save_time}")
                return

            user_id = str(member.id)
            username = member.display_name
            joined_at = join_time.isoformat()
            left_at = left_time.isoformat()

            data = {
                "user_id": user_id,
                "username": username,
                "joined_at": joined_at,
                "left_at": left_at,
                "duration_sec": duration,
            }

            try:
                response = supabase.table("voice_activity").insert(data).execute()
                if response.data:
                    print("✅ DB 저장 성공")
                    voice_activity_cache[member.id] = left_time
                else:
                    print("⚠️ DB 저장 실패: 응답에 데이터 없음")
            except Exception as e:
                print(f"❌ Supabase 예외 발생: {e}")

    # 방송 시작 감지
    if not before.self_stream and after.self_stream and after.channel is not None:
        if member.id not in streaming_members:
            streaming_members.add(member.id)
            text_channel = utils.get(member.guild.text_channels, name="자유채팅방")
            if text_channel:
                embed = Embed(
                    title="📺 방송 시작 알림!",
                    description=f"{member.mention} 님이 `{after.channel.name}` 채널에서 방송을 시작했어요!\n👀 모두 구경하러 가보세요!",
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
                embed.set_footer(text="Go Live 활성화됨")
                await text_channel.send(embed=embed)

    # 방송 종료 감지
    if before.self_stream and not after.self_stream:
        if member.id in streaming_members:
            streaming_members.remove(member.id)
