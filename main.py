from keep_alive import keep_alive

import discord
from discord.ext import commands, tasks
from discord import app_commands
import re
import os
import pytz
import random
import asyncio
import requests
import aiohttp
from collections import deque
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
import uuid  # uuid 추가

from dotenv import load_dotenv
load_dotenv()



KST = timezone(timedelta(hours=9))


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print(f"SUPABASE_URL: {SUPABASE_URL}")
print(f"SUPABASE_KEY: {SUPABASE_KEY}")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("환경변수가 올바르게 로드되지 않았습니다!")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("Supabase 클라이언트 생성 완료")

GUILD_ID = 1309433603331198977
MONITORED_CHANNEL_NAMES = [f"일반{i}" for i in range(1, 17)] + ["큰맵1", "큰맵2"]

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
nickname_pattern = re.compile(r"^[가-힣a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/\d{2}$")
auto_disconnect_tasks = {}
voice_join_times = {}  # user_id: join_time
dm_sent_users = set()
waiting_room_message_cache = {}

all_empty_since = None
notified_after_empty = False
streaming_members = set()
invites_cache = {}















WELCOME_CHANNEL_NAME = "자유채팅방"  # 자유롭게 바꿔도 됨

# 🎈 환영 버튼 구성
class WelcomeButton(discord.ui.View):
    def __init__(self, member, original_message):
        super().__init__(timeout=None)
        self.member = member
        self.original_message = original_message

    @discord.ui.button(label="🎈 이 멤버 환영하기!", style=discord.ButtonStyle.success)
    async def welcome_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.channel.send(
            f"🎉 {interaction.user.mention} 님이 {self.member.mention} 님을 환영했어요!",
            allowed_mentions=discord.AllowedMentions(users=True)
        )

@bot.event
async def on_ready():
    # 서버마다 초대 링크 캐싱
    for guild in bot.guilds:
        invites = await guild.invites()
        invites_cache[guild.id] = {invite.code: invite.uses for invite in invites}
    print("초대 캐시 초기화 완료!")

@bot.event
async def on_member_join(member):
    guild = member.guild
    channel = discord.utils.get(guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if not channel:
        return

    # 초대 링크 정보 다시 받아오기
    invites = await guild.invites()
    old_invites = invites_cache.get(guild.id, {})
    invites_cache[guild.id] = {invite.code: invite.uses for invite in invites}

    inviter = None
    for invite in invites:
        # 사용횟수가 증가한 초대 링크 찾기
        if invite.code in old_invites and invite.uses > old_invites[invite.code]:
            inviter = invite.inviter
            break

    # 입장 시간 (KST 기준)
    KST = timezone(timedelta(hours=9))
    joined_time = datetime.now(tz=KST).strftime("%Y-%m-%d %H:%M:%S")

    embed = discord.Embed(
        title="🎊 신입 멤버 출몰!",
        description=f"😎 {member.mention} 님이 **화려하게 입장!** 🎉\n\n누가 먼저 환영해볼까요?",
        color=discord.Color.orange()
    )
    embed.set_image(url="https://raw.githubusercontent.com/Na-seunghyun/my-discord-bot/main/minion.gif")
    embed.set_footer(text="누구보다 빠르게 남들과는 다르게!", icon_url=member.display_avatar.url)

    # 초대한 사람 정보 추가
    if inviter:
        embed.add_field(name="초대한 사람", value=inviter.mention, inline=True)
    else:
        embed.add_field(name="초대한 사람", value="알 수 없음", inline=True)

    # 입장 시간 추가
    embed.add_field(name="입장 시간", value=joined_time, inline=True)

    message = await channel.send(embed=embed)
    view = WelcomeButton(member=member, original_message=message)
    await message.edit(view=view)

@bot.event
async def on_member_remove(member):
    channel = discord.utils.get(member.guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if channel:
        embed = discord.Embed(
            title="👋 멤버 탈주!",
            description=f"💨 {member.name} 님이 조용히 서버를 떠났습니다...\n\n**그가 남긴 것은... 바로 추억뿐...** 🥲",
            color=discord.Color.red()
        )
        embed.set_image(url="https://raw.githubusercontent.com/Na-seunghyun/my-discord-bot/main/sponge.gif")
        embed.set_footer(text="다음엔 꼭 다시 만나요!")

        await channel.send(embed=embed)









# 자동 퇴장 로직
async def auto_disconnect_after_timeout(member, voice_channel, text_channel):
    try:
        await asyncio.sleep(20 * 60)  # 20분 대기
        if member.voice and member.voice.channel == voice_channel:
            await member.move_to(None)  # 퇴장 처리
            if text_channel:
                await text_channel.send(
                    f"⏰ {member.mention}님이 '밥좀묵겠습니다' 채널에 20분 이상 머물러 자동 퇴장 처리되었습니다.")
            print(f"🚪 {member.display_name}님 자동 퇴장 완료")
    except asyncio.CancelledError:
        print(f"⏹️ {member.display_name}님 타이머 취소됨")
    finally:
        auto_disconnect_tasks.pop(member.id, None)


@bot.event
async def on_ready():
    print(f"✅ 봇 온라인: {bot.user.name}")

    await asyncio.sleep(3)  # 잠깐 대기: on_voice_state_update에서 중복 실행되는 것 방지

    for guild in bot.guilds:
        bap_channel = discord.utils.get(guild.voice_channels, name="밥좀묵겠습니다")
        text_channel = discord.utils.get(guild.text_channels, name="자유채팅방")

        if bap_channel:
            for member in bap_channel.members:
                if member.bot:
                    continue
                if member.id in auto_disconnect_tasks:
                    continue  # 이미 타이머가 있다면 중복 방지

                # DM 전송
                try:
                    await member.send(
                        f"🍚 {member.display_name}님, '밥좀묵겠습니다' 채널에 입장 중입니다. 20분 후 자동 퇴장됩니다.")
                except Exception as e:
                    print(f"DM 전송 실패 (재시작 시): {member.display_name} - {e}")

                task = asyncio.create_task(
                    auto_disconnect_after_timeout(member, bap_channel, text_channel))
                auto_disconnect_tasks[member.id] = task
                print(f"🔄 재시작 후 타이머 적용됨: {member.display_name}")


@bot.event
async def on_voice_state_update(member, before, after):
    global all_empty_since, notified_after_empty, streaming_members
    if member.bot:
        return

    bap_channel = discord.utils.get(member.guild.voice_channels, name="밥좀묵겠습니다")
    text_channel = discord.utils.get(member.guild.text_channels, name="자유채팅방")

    # 밥좀묵겠습니다 입장 시
    if after.channel == bap_channel and before.channel != bap_channel:
        # 기존 타이머 있으면 취소
        if member.id in auto_disconnect_tasks:
            auto_disconnect_tasks[member.id].cancel()
            auto_disconnect_tasks.pop(member.id, None)

        # ✅ DM 중복 방지
        if member.id not in dm_sent_users:
            try:
                await member.send(
                    f"🍚 {member.display_name}님, '밥좀묵겠습니다' 채널에 입장하셨습니다. 20분 후 자동 퇴장됩니다.")
                dm_sent_users.add(member.id)
            except Exception as e:
                print(f"DM 전송 실패: {member.display_name} - {e}")

        task = asyncio.create_task(auto_disconnect_after_timeout(member, bap_channel, text_channel))
        auto_disconnect_tasks[member.id] = task
        print(f"⏳ {member.display_name}님 타이머 시작됨")

    # 밥좀묵겠습니다 채널에서 나갔을 때 → 타이머 취소
    elif before.channel == bap_channel and after.channel != bap_channel:
        if member.id in auto_disconnect_tasks:
            auto_disconnect_tasks[member.id].cancel()
            auto_disconnect_tasks.pop(member.id, None)
            print(f"❌ {member.display_name}님 퇴장 → 타이머 취소됨")
        # ✅ 퇴장 시 DM 보낸 기록도 초기화
        dm_sent_users.discard(member.id)


    # 대기방 입장 메시지 중복 방지 캐시
    now_utc = datetime.utcnow()

    if (before.channel != after.channel) and (after.channel is not None):
        if after.channel.name == "대기방":
            last_sent = waiting_room_message_cache.get(member.id)
            if not last_sent or (now_utc - last_sent) > timedelta(seconds=30):
                text_channel = discord.utils.get(member.guild.text_channels, name="자유채팅방")
                if text_channel:
                    await text_channel.send(f"{member.mention} 나도 게임하고싶어! 나 도 끼 워 줘!")
                    waiting_room_message_cache[member.id] = now_utc

    # ===== 수정된 배그 채널 첫 입장 감지 로직 =====
    now = datetime.now(timezone.utc)
    guild = member.guild
    monitored_channels = [ch for ch in guild.voice_channels if ch.name in MONITORED_CHANNEL_NAMES]

    # 모든 모니터링 채널이 비어있는지 확인
    all_empty = all(len(ch.members) == 0 for ch in monitored_channels)

    # 퇴장으로 인해 마지막 인원이 나가서 모든 채널이 비게 되었을 경우
    if before.channel and before.channel.name in MONITORED_CHANNEL_NAMES:
        if all_empty:
            if all_empty_since is None:
                all_empty_since = now
                notified_after_empty = False
                print(f"⚠️ 모든 모니터링 채널 비어있음 - 시간 기록 시작: {all_empty_since.isoformat()}")

    # 입장 시점에만 아래 메시지 체크
    if before.channel is None and after.channel and after.channel.name in MONITORED_CHANNEL_NAMES:
        if all_empty_since and (now - all_empty_since).total_seconds() >= 3600 and not notified_after_empty:
            text_channel = discord.utils.get(guild.text_channels, name="자유채팅방")
            if text_channel:
                embed = discord.Embed(
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

    # 모니터링 채널에 사람이 존재하면 상태 초기화
    if not all_empty:
        all_empty_since = None
        notified_after_empty = False
    # ===== 여기까지 수정된 부분 =====


    
   # 입장 처리
    if before.channel is None and after.channel is not None:
        user_id = str(member.id)
        username = member.display_name

        now = datetime.now(timezone.utc).replace(microsecond=0)
        print(f"✅ [입장 이벤트] {username}({user_id}) 님이 '{after.channel.name}'에 입장 at {now.isoformat()}")

        try:
            existing = supabase.rpc("get_active_voice_activity", {"user_id_input": user_id}).execute()

            if hasattr(existing, 'data') and existing.data and len(existing.data) > 0:
                print(f"⚠️ 이미 입장 기록 존재, 중복 저장 방지: {user_id}")
                return

            data = {
                "user_id": user_id,
                "username": username,
                "joined_at": now.isoformat(),
                "left_at": None,
                "duration_sec": 0,
            }
            response = supabase.table("voice_activity").insert(data).execute()

            if hasattr(response, 'error') and response.error:
                print(f"❌ 입장 DB 저장 실패: {response.error}")
                return

            print(f"✅ 입장 DB 저장 성공: {username} - {now.isoformat()}")

        except Exception as e:
            print(f"❌ 입장 DB 저장 예외 발생: {e}")

    # 퇴장 처리
    elif before.channel is not None and after.channel is None:
        user_id = str(member.id)
        username = member.display_name

        now = datetime.now(timezone.utc).replace(microsecond=0)
        print(f"🛑 [퇴장 이벤트] {username}({user_id}) 님이 '{before.channel.name}'에서 퇴장 at {now.isoformat()}")

        try:
            records = supabase.rpc("get_active_voice_activity", {"user_id_input": user_id}).execute()

            if hasattr(records, 'data') and records.data and len(records.data) > 0:
                record = records.data[0]
                joined_at_str = record.get("joined_at")
                if not joined_at_str:
                    print(f"⚠️ joined_at 값 없음, 퇴장 처리 불가: {user_id}")
                    return

                joined_at_dt = datetime.fromisoformat(joined_at_str)
                duration = int((now - joined_at_dt).total_seconds())

                update_data = {
                    "left_at": now.isoformat(),
                    "duration_sec": duration,
                }
                update_response = supabase.table("voice_activity").update(update_data).eq("id", record["id"]).execute()

                if hasattr(update_response, 'error') and update_response.error:
                    print(f"❌ 퇴장 DB 업데이트 실패: {update_response.error}")
                    return

                print(f"✅ 퇴장 DB 업데이트 성공: {username} - {now.isoformat()}")

            else:
                print(f"⚠️ 입장 기록이 없음 - 퇴장 기록 업데이트 불가: {user_id}")

        except Exception as e:
            print(f"❌ 퇴장 DB 처리 예외 발생: {e}")












    # ——— 방송 시작/종료 알림 처리 ———

    # 방송 시작 감지 (False -> True)
    if not before.self_stream and after.self_stream and after.channel is not None:
        if member.id not in streaming_members:
            streaming_members.add(member.id)
            text_channel = discord.utils.get(member.guild.text_channels, name="자유채팅방")
            if text_channel:
                embed = discord.Embed(
                    title="📺 방송 시작 알림!",
                    description=f"{member.mention} 님이 `{after.channel.name}` 채널에서 방송을 시작했어요!\n👀 모두 구경하러 가보세요!",
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
                embed.set_footer(text="Go Live 활성화됨")
                await text_channel.send(embed=embed)

    # 방송 종료 감지 (True -> False)
    if before.self_stream and not after.self_stream:
        if member.id in streaming_members:
            streaming_members.remove(member.id)
        # 방송 종료 알림 메시지는 보내지 않습니다!


@tasks.loop(minutes=30)
async def check_voice_channels_for_streaming():
    for guild in bot.guilds:
        text_channel = discord.utils.get(guild.text_channels, name="자유채팅방")
        if not text_channel:
            continue

        for vc in guild.voice_channels:
            if vc.name in MONITORED_CHANNEL_NAMES and vc.members:
                non_bot_members = [m for m in vc.members if not m.bot]
                if not any(m.voice and m.voice.self_stream for m in non_bot_members):
                    mentions = " ".join(m.mention for m in non_bot_members)

                    embed = discord.Embed(
                        title="🚨 방송 꺼짐 감지",
                        description=f"`{vc.name}` 채널에 사람이 있지만 **Go Live 방송이 꺼져 있습니다.**",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="현재 인원", value=f"{len(non_bot_members)}명", inline=True)
                    embed.add_field(name="라이브 상태", value="❌ 없음", inline=True)
                    embed.set_footer(text="실수로 꺼졌다면 다시 방송을 켜주세요! 🎥")

                    await text_channel.send(content=mentions, embed=embed)


@tree.command(name="도움말", description="봇 명령어 및 기능 안내", guild=discord.Object(id=GUILD_ID))
async def 도움말(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 봇 명령어 안내",
        description="서버 관리와 음성채널 활동을 도와주는 명령어 목록입니다.",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="📢 /소환",
        value=(
            "선택한 음성 채널의 인원들을 **내가 있는 채널로 소환**합니다.\n"
            "`all` 선택 시 `밥좀묵겠습니다`, `쉼터`, `클랜훈련소`는 제외됩니다."
        ),
        inline=False
    )

    embed.add_field(
        name="🎲 /팀짜기",
        value=(
            "현재 음성 채널 인원을 팀으로 나누고, **빈 일반 채널로 자동 분배**합니다.\n"
            "예: 팀당 3명씩 랜덤으로 나눠 일반1, 일반2로 이동"
        ),
        inline=False
    )

    embed.add_field(
        name="🍚 /밥",
        value=(
            "`밥좀묵겠습니다` 채널로 자신을 이동시킵니다.\n"
            "20분 이상 활동이 없으면 자동 퇴장됩니다."
        ),
        inline=False
    )

    embed.add_field(
        name="🧪 /검사",
        value=(
            "서버 멤버들의 **닉네임 형식을 검사**합니다.\n"
            "올바른 닉네임: `이름/ID/두자리숫자`"
        ),
        inline=False
    )

    embed.add_field(
        name="📈 /접속시간랭킹",
        value=(
            "음성 채널에서 활동한 **접속 시간 Top 10 랭킹**을 확인합니다.\n"
            "버튼 클릭 시 접속 시간 확인 가능"
        ),
        inline=False
    )

    embed.add_field(
        name="🎯 /개별소환",
        value=(
            "음성 채널에 있는 멤버를 골라서 **내가 있는 채널로 소환**합니다.\n"
            "여러 멤버 선택 가능"
        ),
        inline=False
    )

    embed.set_footer(text="기타 문의는 관리자에게 DM 주세요!")
    await interaction.response.send_message(embed=embed, ephemeral=True)



# ✅ 슬래시 명령어: 전적조회
import discord
import requests
import os
import json
import random
from datetime import datetime, timedelta

# API 및 디스코드 기본 설정
API_KEY = os.environ.get("PUBG_API_KEY")
PLATFORM = "kakao"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/vnd.api+json"
}

RATE_LIMIT = 10
RATE_LIMIT_INTERVAL = 60
_last_requests = []

# ✅ JSON 피드백 로딩
with open("feedback_data/pubg_feedback_full.json", "r", encoding="utf-8") as f:
    feedback_json = json.load(f)

def can_make_request():
    now = datetime.now()
    global _last_requests
    _last_requests = [t for t in _last_requests if (now - t).total_seconds() < RATE_LIMIT_INTERVAL]
    return len(_last_requests) < RATE_LIMIT

def register_request():
    global _last_requests
    _last_requests.append(datetime.now())

def get_player_id(player_name):
    url = f"https://api.pubg.com/shards/{PLATFORM}/players?filter[playerNames]={player_name}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    return data["data"][0]["id"]

def get_season_id():
    url = f"https://api.pubg.com/shards/{PLATFORM}/seasons"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    for season in data["data"]:
        if season["attributes"]["isCurrentSeason"]:
            return season["id"]

def get_player_stats(player_id, season_id):
    url = f"https://api.pubg.com/shards/{PLATFORM}/players/{player_id}/seasons/{season_id}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

# ✅ 스쿼드 전적만 피드백용으로 추출
def extract_squad_metrics(stats):
    mode_stats = stats["data"]["attributes"]["gameModeStats"].get("squad")
    if not mode_stats or mode_stats["roundsPlayed"] == 0:
        return None, "❌ 스쿼드 모드 전적이 없어 분석 피드백을 제공할 수 없습니다."

    rounds = mode_stats['roundsPlayed']
    wins = mode_stats['wins']
    kills = mode_stats['kills']
    damage = mode_stats['damageDealt']
    avg_damage = damage / rounds
    kd = kills / max(1, rounds - wins)
    win_rate = (wins / rounds) * 100

    return (avg_damage, kd, win_rate), None

# ✅ 구간 분류 함수
def get_damage_key(avg_damage):
    if avg_damage < 100: return "D0"
    elif avg_damage < 150: return "D1"
    elif avg_damage < 200: return "D2"
    elif avg_damage < 250: return "D3"
    elif avg_damage < 300: return "D4"
    elif avg_damage < 350: return "D5"
    elif avg_damage < 400: return "D6"
    elif avg_damage < 450: return "D7"
    elif avg_damage < 500: return "D8"
    else: return "D9"

def get_kd_key(kd):
    if kd < 0.3: return "K0"
    elif kd < 0.6: return "K1"
    elif kd < 1.0: return "K2"
    elif kd < 1.5: return "K3"
    elif kd < 2.0: return "K4"
    elif kd < 3.0: return "K5"
    elif kd < 5.0: return "K6"
    else: return "K7"

def get_winrate_key(win_rate):
    if win_rate == 0: return "W0"
    elif win_rate < 1: return "W1"
    elif win_rate < 3: return "W2"
    elif win_rate < 5: return "W3"
    elif win_rate < 7: return "W4"
    elif win_rate < 10: return "W5"
    elif win_rate < 15: return "W6"
    elif win_rate < 20: return "W7"
    elif win_rate < 30: return "W8"
    elif win_rate < 40: return "W9"
    elif win_rate < 50: return "W10"
    else: return "W11"

# ✅ 구간 기반 JSON 피드백 반환
def detailed_feedback(avg_damage, kd, win_rate):
    dmg_key = get_damage_key(avg_damage)
    kd_key = get_kd_key(kd)
    win_key = get_winrate_key(win_rate)

    dmg_msg = random.choice(feedback_json["damage"][dmg_key])
    kd_msg = random.choice(feedback_json["kdr"][kd_key])
    win_msg = random.choice(feedback_json["winrate"][win_key])

    return dmg_msg, kd_msg, win_msg  # 각각 분리하여 리턴


# ✅ 디스코드 봇 커맨드

@tree.command(name="전적", description="PUBG 닉네임으로 전적 조회", guild=discord.Object(id=GUILD_ID))
async def 전적(interaction: discord.Interaction, 닉네임: str):
    try:
        await interaction.response.defer()
    except discord.NotFound:
        print("❌ Interaction expired before defer.")
        return

    if not can_make_request():
        await interaction.followup.send("⚠️ API 요청 제한(분당 10회)으로 인해 잠시 후 다시 시도해주세요.", ephemeral=True)
        return

    try:
        register_request()
        player_id = get_player_id(닉네임)
        season_id = get_season_id()
        stats = get_player_stats(player_id, season_id)

        # 분석 피드백
        squad_metrics, error = extract_squad_metrics(stats)
        if squad_metrics:
            avg_damage, kd, win_rate = squad_metrics
            dmg_msg, kd_msg, win_msg = detailed_feedback(avg_damage, kd, win_rate)
        else:
            dmg_msg = kd_msg = win_msg = error

        embed = discord.Embed(
            title=f"{닉네임}님의 PUBG 전적 요약",
            color=discord.Color.blue()
        )

        for mode in ["solo", "duo", "squad"]:
            mode_stats = stats["data"]["attributes"]["gameModeStats"].get(mode)
            if not mode_stats or mode_stats["roundsPlayed"] == 0:
                continue

            rounds = mode_stats['roundsPlayed']
            wins = mode_stats['wins']
            kills = mode_stats['kills']
            damage = mode_stats['damageDealt']
            avg_damage = damage / rounds
            kd = kills / max(1, rounds - wins)
            win_pct = (wins / rounds) * 100

            value = (
                f"게임 수: {rounds}\n"
                f"승리 수: {wins} ({win_pct:.2f}%)\n"
                f"킬 수: {kills}\n"
                f"평균 데미지: {avg_damage:.2f}\n"
                f"K/D: {kd:.2f}"
            )
            embed.add_field(name=mode.upper(), value=value, inline=True)

        # 세분화된 피드백 임베드 필드 추가
        embed.add_field(name="📊 SQUAD 분석 피드백", value="전투 성능을 바탕으로 분석된 결과입니다.", inline=False)

        embed.add_field(name="🔫 평균 데미지", value=f"```{dmg_msg}```", inline=False)
        embed.add_field(name="⚔️ K/D", value=f"```{kd_msg}```", inline=False)
        embed.add_field(name="🏆 승률", value=f"```{win_msg}```", inline=False)


        embed.set_footer(text="PUBG API 제공")

        await interaction.followup.send(embed=embed)

    except requests.HTTPError as e:
        await interaction.followup.send(f"❌ API 오류가 발생했습니다: {e}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ 전적 조회 중 오류가 발생했습니다: {e}", ephemeral=True)















# ✅ 슬래시 명령어: 검사
@tree.command(name="검사", description="닉네임 검사", guild=discord.Object(id=GUILD_ID))
async def 검사(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    count = 0
    for member in interaction.guild.members:
        if member.bot:
            continue
        parts = (member.nick or member.name).split("/")
        if len(parts) != 3 or not nickname_pattern.fullmatch("/".join(p.strip() for p in parts)):
            count += 1
            try:
                await interaction.channel.send(f"{member.mention} 닉네임 형식이 올바르지 않아요.")
            except:
                pass
    await interaction.followup.send(f"🔍 검사 완료: {count}명 문제 있음", ephemeral=True)


# ✅ 슬래시 명령어: 소환


EXCLUDED_CHANNELS = ["밥좀묵겠습니다", "쉼터", "클랜훈련소"]

CHANNEL_CHOICES = [
    "all",
    "밥좀묵겠습니다", "쉼터", "클랜훈련소",
    "게스트방", "대기방",
    "큰맵1", "큰맵2"
] + [f"일반{i}" for i in range(1, 17)]

# --- 채널 소환 UI 구성 ---
class ChannelSelect(discord.ui.Select):
    def __init__(self, view: 'ChannelSelectView'):
        self.parent_view = view
        options = [discord.SelectOption(label=ch) for ch in CHANNEL_CHOICES]
        super().__init__(
            placeholder="소환할 채널을 선택하세요 (여러 개 선택 가능)",
            min_values=1,
            max_values=len(options),
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_channels = self.values
        selected_str = ", ".join(self.values)
        await interaction.response.edit_message(
            content=f"선택한 채널: {selected_str}",
            view=self.parent_view
        )


class ChannelConfirmButton(discord.ui.Button):
    def __init__(self, view: 'ChannelSelectView'):
        super().__init__(label="✅ 소환하기", style=discord.ButtonStyle.green, row=1)
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):
        vc = interaction.user.voice.channel if interaction.user.voice else None
        if not vc:
            await interaction.response.send_message("❌ 먼저 음성 채널에 들어가주세요!", ephemeral=True)
            return

        selected = self.parent_view.selected_channels
        if not selected:
            await interaction.response.send_message("⚠️ 채널을 선택해주세요.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)  # 여기서 1회 응답

        if "all" in selected:
            target_channels = [
                ch for ch in interaction.guild.voice_channels if ch.name not in EXCLUDED_CHANNELS
            ]
            excluded_note = "\n\n❗️`all` 선택 시 `밥좀묵겠습니다`, `쉼터`, `클랜훈련소`는 제외됩니다."
        else:
            target_channels = [
                ch for ch in interaction.guild.voice_channels if ch.name in selected
            ]
            excluded_note = ""

        moved = 0
        for ch in target_channels:
            for member in ch.members:
                if not member.bot:
                    try:
                        await member.move_to(vc)
                        moved += 1
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        print(f"❌ {member.display_name} 이동 실패: {e}")

        if moved == 0:
            await interaction.followup.send("⚠️ 이동할 멤버가 없습니다.", ephemeral=True)
        else:
            embed = discord.Embed(
                title="📢 쿠치요세노쥬츠 !",
                description=f"{interaction.user.mention} 님이 **{moved}명**을 음성채널로 소환했습니다.{excluded_note}",
                color=discord.Color.green()
            )
            embed.set_image(url="https://raw.githubusercontent.com/Na-seunghyun/my-discord-bot/main/123123.gif")
            await interaction.followup.send(embed=embed, ephemeral=False)

        self.parent_view.stop()
        try:
            await interaction.message.edit(view=None)
        except discord.NotFound:
            pass


class ChannelSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.selected_channels: list[str] = []
        self.add_item(ChannelSelect(self))
        self.add_item(ChannelConfirmButton(self))


# --- 멤버 소환 UI 구성 ---
class MemberSelect(discord.ui.Select):
    def __init__(self, members: list[discord.Member], view: 'MemberSelectView'):
        self.parent_view = view
        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id))
            for m in members if not m.bot
        ]
        super().__init__(
            placeholder="소환할 멤버를 선택하세요 (여러 개 선택 가능)",
            min_values=1,
            max_values=min(25, len(options)),
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_member_ids = [int(v) for v in self.values]
        selected_names = [option.label for option in self.options if option.value in self.values]
        selected_str = ", ".join(selected_names)
        await interaction.response.edit_message(
            content=f"선택한 멤버: {selected_str}",
            view=self.parent_view
        )


class MemberConfirmButton(discord.ui.Button):
    def __init__(self, view: 'MemberSelectView'):
        super().__init__(label="✅ 소환하기", style=discord.ButtonStyle.green, row=1)
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):
        vc = interaction.user.voice.channel if interaction.user.voice else None
        if not vc:
            await interaction.response.send_message("❌ 먼저 음성 채널에 들어가주세요!", ephemeral=True)
            return

        selected_ids = self.parent_view.selected_member_ids
        if not selected_ids:
            await interaction.response.send_message("⚠️ 멤버를 선택해주세요.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)  # 1회 응답

        moved = 0
        for member_id in selected_ids:
            member = interaction.guild.get_member(member_id)
            if member and member.voice and member.voice.channel != vc and not member.bot:
                try:
                    await member.move_to(vc)
                    moved += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"❌ {member.display_name} 이동 실패: {e}")

        if moved == 0:
            await interaction.followup.send("⚠️ 이동할 멤버가 없습니다.", ephemeral=True)
        else:
            embed = discord.Embed(
                title="📢 쿠치요세노쥬츠 !",
                description=f"{interaction.user.mention} 님이 **{moved}명**을 음성채널로 소환했습니다.",
                color=discord.Color.green()
            )
            embed.set_image(url="https://raw.githubusercontent.com/Na-seunghyun/my-discord-bot/main/123123.gif")
            await interaction.followup.send(embed=embed, ephemeral=False)

        self.parent_view.stop()
        try:
            await interaction.message.edit(view=None)
        except discord.NotFound:
            pass


class MemberSelectView(discord.ui.View):
    def __init__(self, members: list[discord.Member]):
        super().__init__(timeout=60)
        self.selected_member_ids: list[int] = []
        self.add_item(MemberSelect(members, self))
        self.add_item(MemberConfirmButton(self))


# --- 슬래시 명령어 등록 ---
@tree.command(name="소환", description="음성 채널 인원 소환", guild=discord.Object(id=GUILD_ID))
async def 소환(interaction: discord.Interaction):
    await interaction.response.send_message("소환할 채널을 선택해주세요.", view=ChannelSelectView(), ephemeral=True)


@tree.command(name="개별소환", description="특정 멤버를 선택해 소환합니다.", guild=discord.Object(id=GUILD_ID))
async def 개별소환(interaction: discord.Interaction):
    # 1. 음성채널 입장 확인
    vc = interaction.user.voice.channel if interaction.user.voice else None
    if not vc:
        # 응답 여부 체크 후 응답
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ 음성 채널에 들어가주세요!", ephemeral=True)
        return

    # 2. 멤버 필터링
    members = [m for m in interaction.guild.members if m.voice and m.voice.channel and not m.bot]
    if not members:
        if not interaction.response.is_done():
            await interaction.response.send_message("⚠️ 음성채널에 있는 멤버가 없습니다.", ephemeral=True)
        return

    # 3. View 생성
    view = MemberSelectView(members)

    # 4. interaction 응답 시도 (중복응답 방지)
    if not interaction.response.is_done():
        try:
            await interaction.response.send_message("소환할 멤버를 선택하세요:", view=view, ephemeral=True)
        except discord.errors.InteractionResponded:
            # 이미 응답했으면 무시 또는 로깅
            print("interaction already responded")
    else:
        # 이미 응답했으면 followup 보내기 (필요 시)
        await interaction.followup.send("소환할 멤버를 선택하세요:", view=view, ephemeral=True)







    

    # 서버 멤버 중 음성채널에 들어와있는 멤버만 필터링 (봇 제외)
    members = [m for m in interaction.guild.members if m.voice and m.voice.channel and not m.bot]

    if not members:
        await interaction.response.send_message("⚠️ 음성채널에 있는 멤버가 없습니다.", ephemeral=True)
        return

    view = MemberSelectView(members)
    await interaction.response.send_message("소환할 멤버를 선택하세요:", view=view, ephemeral=True)


# ✅ 슬래시 명령어: 팀짜기
class TeamMoveView(discord.ui.View):
    def __init__(self, teams, empty_channels, origin_channel):
        super().__init__(timeout=None)
        self.teams = teams
        self.empty_channels = empty_channels
        self.origin_channel = origin_channel
        self.moved = False

    @discord.ui.button(label="🚀 팀 이동 시작", style=discord.ButtonStyle.green)
    async def move(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.moved:
            await interaction.response.send_message("이미 이동 완료됨", ephemeral=True)
            return
        for team, channel in zip(self.teams[1:], self.empty_channels):
            for member in team:
                try:
                    await member.move_to(channel)
                except:
                    pass
        self.moved = True
        button.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


@tree.command(name="팀짜기", description="음성 채널 팀 나누기", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(team_size="팀당 인원 수")
@app_commands.choices(team_size=[
    app_commands.Choice(name="2", value=2),
    app_commands.Choice(name="3", value=3),
    app_commands.Choice(name="4", value=4),
])
async def 팀짜기(interaction: discord.Interaction, team_size: app_commands.Choice[int]):
    vc = interaction.user.voice.channel if interaction.user.voice else None
    if not vc:
        await interaction.response.send_message("❌ 음성 채널에 먼저 들어가 주세요!", ephemeral=True)
        return

    members = [m for m in vc.members if not m.bot]
    random.shuffle(members)
    teams = [members[i:i + team_size.value] for i in range(0, len(members), team_size.value)]

    guild = interaction.guild
    empty_channels = [ch for ch in guild.voice_channels if ch.name.startswith("일반") and len(ch.members) == 0 and ch != vc]

    if len(empty_channels) < len(teams) - 1:
        await interaction.response.send_message("❌ 빈 채널 부족", ephemeral=True)
        return

    msg = f"🎲 팀 나누기 완료\n\n**팀 1 (현재 채널):** {', '.join(m.display_name for m in teams[0])}\n"
    for idx, (team, ch) in enumerate(zip(teams[1:], empty_channels), start=2):
        msg += f"**팀 {idx} ({ch.name}):** {', '.join(m.display_name for m in team)}\n"

    await interaction.response.send_message(msg, view=TeamMoveView(teams, empty_channels, vc))



# ——— 여기부터 추가 ———

from discord.ui import View, button
from datetime import datetime, timedelta
import pytz
import discord

def format_duration(seconds: int) -> str:
    days, remainder = divmod(seconds, 86400)  # 86400초 = 1일
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}일")
    if hours > 0 or days > 0:
        parts.append(f"{hours}시간")
    if minutes > 0 or hours > 0 or days > 0:
        parts.append(f"{minutes}분")
    parts.append(f"{seconds}초")

    return " ".join(parts)


def get_current_kst_year_month() -> str:
    now_utc = datetime.utcnow()
    now_kst = now_utc + timedelta(hours=9)  # UTC +9 = KST
    return now_kst.strftime("%Y-%m")


def get_current_kst_time_str():
    kst = pytz.timezone('Asia/Seoul')
    now_kst = datetime.now(kst)
    return now_kst.strftime("%Y-%m-%d %H:%M:%S KST")


class VoiceTopButton(View):
    def __init__(self):
        super().__init__(timeout=180)

    @button(label="접속시간랭킹 보기", style=discord.ButtonStyle.primary)
    async def on_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=False)

        try:
            year_month = get_current_kst_year_month()
            print(f"DEBUG: year_month parameter = {year_month}")

            response = supabase.rpc("top_voice_activity_tracker", {"year_month": year_month}).execute()

            print(f"DEBUG: supabase.rpc response = {response}")
            print(f"DEBUG: supabase.rpc response.data = {response.data}")

            if not hasattr(response, "data") or response.data is None:
                await interaction.followup.send("❌ Supabase 응답 오류 또는 데이터 없음", ephemeral=False)
                return

            data = response.data
            if not data:
                await interaction.followup.send(f"😥 {year_month} 월에 기록된 접속 시간이 없습니다.", ephemeral=False)
                return

            embed = discord.Embed(title=f"🎤 {year_month} 음성 접속시간 Top 10", color=0x5865F2)

            
            start_kst_str = f"{year_month}-01 00:00"
            current_kst_str = get_current_kst_time_str()
            embed.set_footer(text=f"{start_kst_str}부터 {current_kst_str}까지의 음성 접속 데이터를 기준으로 조회했습니다. (한국 시간)")


            trophy_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
            for rank, info in enumerate(data, 1):
                emoji = trophy_emojis.get(rank, f"{rank}.")
                time_str = format_duration(info['total_duration'])
                print(f"DEBUG - user: {info['username']}, total_duration raw: {info['total_duration']}")
                embed.add_field(name=f"{emoji} {info['username']}", value=time_str, inline=False)

            button.disabled = True
            try:
                await interaction.message.edit(view=self)
            except discord.errors.NotFound:
                print("⚠️ 편집할 메시지를 찾을 수 없습니다.")

            await interaction.followup.send(embed=embed, ephemeral=False)

        except Exception as e:
            await interaction.followup.send(f"❗ 오류 발생: {e}", ephemeral=False)


@tree.command(name="접속시간랭킹", description="음성 접속시간 Top 10", guild=discord.Object(id=GUILD_ID))
async def 접속시간랭킹(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send(
        "버튼을 눌러 음성 접속시간 랭킹을 확인하세요.",
        view=VoiceTopButton(),
        ephemeral=True
    )





@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await tree.sync(guild=guild)
    check_voice_channels_for_streaming.start()
    monitor_voice_channels.start()  # ✅ 추가됨
    process_play_queue.start()      # ✅ 추가됨
    print(f"✅ 봇 로그인: {bot.user}")


keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ 환경변수 DISCORD_TOKEN이 없습니다.")
