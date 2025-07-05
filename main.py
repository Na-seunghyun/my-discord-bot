from keep_alive import keep_alive

import discord
from discord.ext import commands, tasks
from discord import app_commands
import re
import os
import random
import asyncio
import requests
import aiohttp
from collections import deque
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
import uuid  # uuid 추가

KST = timezone(timedelta(hours=9))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

GUILD_ID = 1309433603331198977
MONITORED_CHANNEL_NAMES = [f"일반{i}" for i in range(1, 17)] + ["큰맵1", "큰맵2"]

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
nickname_pattern = re.compile(r"^[가-힣a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/\d{2}$")
auto_disconnect_tasks = {}
voice_join_times = {}  # user_id: join_time


# 자동 퇴장
async def auto_disconnect_after_timeout(user: discord.Member, channel: discord.VoiceChannel, timeout=1200):
    await asyncio.sleep(timeout)
    if user.voice and user.voice.channel == channel:
        try:
            await user.move_to(None)
            text_channel = discord.utils.get(user.guild.text_channels, name="자유채팅방")
            if text_channel:
                await text_channel.send(f"{user.mention} 님, 20분 지나서 자동 퇴장당했어요. 🍚")
        except Exception as e:
            print(f"오류: {e}")
    auto_disconnect_tasks.pop(user.id, None)


def sql_escape(s):
    if s is None:
        return 'NULL'
    return "'" + str(s).replace("'", "''") + "'"

streaming_members = set()

# 전역 캐시 선언 (함수 밖, 파일 최상단)
waiting_room_message_cache = {}

from datetime import datetime, timezone, timedelta

# voice_activity 중복 저장 방지용 캐시 (유저별 마지막 저장 시간)
voice_activity_cache = {}

channel_last_empty = {}
all_empty_since = None
notified_after_empty = False


@bot.event
async def on_voice_state_update(member, before, after):
    global streaming_members
    global all_empty_since, notified_after_empty

    print(f"Voice state update - member: {member}, before: {before.channel if before else None}, after: {after.channel if after else None}")
    if member.bot:
        return

    # 자동 퇴장 타이머 제거
    if member.id in auto_disconnect_tasks:
        auto_disconnect_tasks[member.id].cancel()
        auto_disconnect_tasks.pop(member.id, None)

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

    # 입장 기록
    if before.channel is None and after.channel is not None:
        voice_join_times[member.id] = datetime.now(timezone.utc).replace(microsecond=0)

    # 퇴장 기록
    elif before.channel is not None and after.channel is None:
        join_time = voice_join_times.pop(member.id, None)
        if join_time:
            left_time = datetime.now(timezone.utc).replace(microsecond=0)
            duration = int((left_time - join_time).total_seconds())

            # ✅ 채널이 완전히 비었으면 시간 기록
            if before.channel and len(before.channel.members) == 0:
                channel_last_empty[before.channel.id] = left_time
                print(f"📌 '{before.channel.name}' 채널이 비었음 — 시간 기록됨")

            # 중복 저장 방지 체크
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
                    voice_activity_cache[member.id] = left_time  # 저장 시간 업데이트
                else:
                    print("⚠️ DB 저장 실패: 응답에 데이터 없음")
            except Exception as e:
                print(f"❌ Supabase 예외 발생: {e}")

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
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

API_KEY = os.environ.get("PUBG_API_KEY")
PLATFORM = "kakao"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/vnd.api+json"
}

RATE_LIMIT = 10
RATE_LIMIT_INTERVAL = 60
_last_requests = []

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

# ✅ 모드별 전체 전적 요약 (SOLO, DUO, SQUAD)
def summarize_stats(stats):
    modes = ["solo", "duo", "squad"]
    lines = []
    for mode in modes:
        mode_stats = stats["data"]["attributes"]["gameModeStats"].get(mode)
        if not mode_stats or mode_stats["roundsPlayed"] == 0:
            continue

        rounds = mode_stats['roundsPlayed']
        wins = mode_stats['wins']
        kills = mode_stats['kills']
        damage = mode_stats['damageDealt']
        avg_damage = damage / rounds
        kd = kills / max(1, rounds - wins)

        lines.append(f"**[{mode.upper()} 모드]**")
        lines.append(f"- 게임 수: {rounds}")
        lines.append(f"- 승리 수: {wins} ({(wins / rounds) * 100:.2f}%)")
        lines.append(f"- 킬 수: {kills}")
        lines.append(f"- 평균 데미지: {avg_damage:.2f}")
        lines.append(f"- K/D: {kd:.2f}")
        lines.append("")  # 간격

    return "\n".join(lines) if lines else "전적이 존재하지 않거나 조회할 수 없습니다."

# ✅ 분석 메시지: 스쿼드 전적 기반
def get_avg_damage_feedback(avg):
    if avg < 100:
        return random.choice([
            "[평균 데미지] 📉 평균 데미지가 매우 낮아요. 초반 교전에서 자신감을 높여봐요.",
            "[평균 데미지] 😢 공격력이 약해 교전에서 밀릴 수 있어요. 사격 연습을 권합니다.",
            "[평균 데미지] 🔫 딜량이 부족합니다. 위치 선정과 사격 타이밍에 집중하세요.",
            "[평균 데미지] ⚠️ 피해량이 적으면 적 제압이 어렵습니다. 적극적으로 공격하세요.",
            "[평균 데미지] 🎯 더 높은 딜량을 위해 무기 숙련도를 키우는 게 좋아요.",
            "[평균 데미지] 🛠 공격 기술 향상이 필요해 보입니다. 꾸준한 연습을!",
            "[평균 데미지] 🚧 교전에서 적극적이 되면 데미지가 증가할 거예요."
        ])
    elif avg < 200:
        return random.choice([
            "[평균 데미지] 🟠 데미지가 조금 낮아요. 교전 참여를 늘려보세요.",
            "[평균 데미지] ⚡ 점차 성장 중입니다. 더 적극적인 플레이가 필요해요.",
            "[평균 데미지] 📈 공격력이 올라가고 있어요. 좋은 방향입니다!",
            "[평균 데미지] 👍 점점 교전에서 영향력을 키우고 있습니다.",
            "[평균 데미지] 🧠 위치 선정과 타이밍이 좋아지고 있어요.",
            "[평균 데미지] 🔄 꾸준히 노력하면 좋은 결과가 따라올 겁니다.",
            "[평균 데미지] 💪 적극적인 딜링으로 팀에 힘이 되고 있어요."
        ])
    elif avg < 300:
        return random.choice([
            "[평균 데미지] 🟡 준수한 딜량입니다. 전투 감각이 좋네요.",
            "[평균 데미지] 🎖 교전에서 영향력이 커지고 있습니다.",
            "[평균 데미지] 🚀 꾸준한 딜로 팀에 크게 기여 중입니다.",
            "[평균 데미지] 🔥 안정적인 공격력을 보여주고 있어요.",
            "[평균 데미지] 💪 전장 주도권을 점차 잡아가고 있습니다.",
            "[평균 데미지] 🛡 전투 중 생존과 공격 모두 균형이 잡혀가네요.",
            "[평균 데미지] 🎯 좋은 딜량으로 성장 중인 플레이어입니다."
        ])
    elif avg < 500:
        return random.choice([
            "[평균 데미지] 🟢 매우 좋은 데미지! 팀에서 핵심 딜러입니다.",
            "[평균 데미지] 🏆 뛰어난 딜량으로 전투를 지배하고 있어요.",
            "[평균 데미지] 💥 공격력이 빛나고 있습니다.",
            "[평균 데미지] 🎯 무기 숙련도와 실력이 뛰어납니다.",
            "[평균 데미지] 🔥 전장 핵심 역할을 맡고 있습니다.",
            "[평균 데미지] 💪 전투에서 팀에 큰 힘이 되고 있어요.",
            "[평균 데미지] 🚀 지속적인 활약이 기대됩니다."
        ])
    else:
        return random.choice([
            "[평균 데미지] 💥 압도적인 데미지! 프로급 플레이입니다.",
            "[평균 데미지] 🔥 전투를 완전히 지배하고 있어요.",
            "[평균 데미지] ⚡ 엄청난 딜량으로 팀을 이끌고 있습니다.",
            "[평균 데미지] 🏅 최고 수준의 공격력을 보여줍니다.",
            "[평균 데미지] 🎉 완벽한 딜러로 팀 승리에 핵심입니다.",
            "[평균 데미지] 🌟 전장의 지배자라고 할 만합니다.",
            "[평균 데미지] 🚀 놀라운 데미지로 상대를 압도하고 있어요."
        ])

def get_kd_feedback(kd):
    if kd < 0.3:
        return random.choice([
            "[K/D] 😢 K/D가 매우 낮아 생존이 어렵습니다. 신중한 플레이를 권장해요.",
            "[K/D] ⚠️ 마무리가 약해요. 차분히 싸움을 끝내는 연습을 해보세요.",
            "[K/D] 🔻 전투 능력이 부족합니다. 은신과 회피를 연습하세요.",
            "[K/D] 😟 킬 확정 능력을 키우면 전적이 개선됩니다.",
            "[K/D] 🚶 신중하게 움직이며 싸움을 피하는 전략도 필요해요.",
            "[K/D] 🛡 생존 위주의 플레이가 우선입니다.",
            "[K/D] 🔍 전투 후 탈출과 생존에 집중해보세요."
        ])
    elif kd < 0.6:
        return random.choice([
            "[K/D] ⚠️ 약간 낮은 편입니다. 마무리 능력을 키워보세요.",
            "[K/D] 😶 킬력이 부족해 교전 후 확정력을 높이세요.",
            "[K/D] 🎯 싸움을 끝내는 능력을 연습하면 좋습니다.",
            "[K/D] 🛡 생존 위주에서 조금 더 공격적으로 변해보세요.",
            "[K/D] 💡 집중력을 높여 교전 마무리에 신경 써보세요.",
            "[K/D] 🔄 꾸준히 연습하면 더 나아질 거예요.",
            "[K/D] 🔥 공격적인 플레이를 시도해 보세요."
        ])
    elif kd < 1.0:
        return random.choice([
            "[K/D] 👍 안정적인 K/D입니다. 점차 공격적으로 변해보세요.",
            "[K/D] 🟢 괜찮은 전투 실력입니다. 킬 기회를 더 노려보세요.",
            "[K/D] ✅ 전장에서 자신감을 얻고 있어요!",
            "[K/D] 🎯 마무리 능력이 좋아지고 있습니다.",
            "[K/D] 🚀 좋은 K/D로 팀에 도움이 되고 있어요.",
            "[K/D] 🎖 꾸준한 노력의 결과가 보입니다.",
            "[K/D] 🔥 전투 감각이 점점 더 좋아지고 있어요."
        ])
    elif kd < 2.0:
        return random.choice([
            "[K/D] 💪 훌륭한 K/D! 전투 감각이 뛰어나네요.",
            "[K/D] 🔥 팀을 이끄는 중심 플레이어입니다.",
            "[K/D] 👏 안정적인 킬 능력으로 팀에 힘이 됩니다.",
            "[K/D] ⭐ 믿음직한 전장 사수입니다.",
            "[K/D] 🚀 높은 K/D로 큰 위협이 되고 있어요.",
            "[K/D] 🎯 전투 능력이 매우 뛰어납니다.",
            "[K/D] 🏆 팀 승리에 크게 기여하고 있어요."
        ])
    else:
        return random.choice([
            "[K/D] 💥 압도적인 K/D! 에이스 플레이어입니다.",
            "[K/D] 🔥 공격적이고 효율적인 플레이가 돋보여요.",
            "[K/D] 🏆 최고의 전투력을 보여줍니다.",
            "[K/D] ⚡ 적들을 제압하는 놀라운 능력자입니다.",
            "[K/D] 🎖 전투의 중심으로 팀을 이끌고 있습니다.",
            "[K/D] 🌟 엄청난 킬 능력으로 팀을 캐리 중입니다.",
            "[K/D] 🚀 압도적인 전장 지배자입니다."
        ])

def get_winrate_feedback(win_rate):
    if win_rate == 0:
        return random.choice([
            "[승률] 😓 아직 승리가 없네요. 생존과 전략에 집중해 보세요.",
            "[승률] 📉 승리 경험이 없으면 끝까지 버티는 연습이 필요합니다.",
            "[승률] 🌀 후반 집중력이 중요합니다. 인내심을 가져보세요.",
            "[승률] 😟 위치 선정과 회피가 부족해 보입니다. 전략을 고민하세요.",
            "[승률] ⚠️ 승리를 위해 좀 더 신중한 플레이가 필요합니다.",
            "[승률] 🛠 게임 후반 운영에 신경 써보세요.",
            "[승률] 🛡 생존 중심의 플레이가 중요합니다."
        ])
    elif win_rate < 5:
        return random.choice([
            "[승률] 🛠 승률이 낮은 편입니다. 안전한 플레이를 시도해보세요.",
            "[승률] 🔍 신중한 진입과 회피로 생존 시간을 늘려보세요.",
            "[승률] 🚶 조심스럽게 움직이며 팀과 협력하세요.",
            "[승률] 🛡 생존 위주 운영이 승률 향상에 도움이 됩니다.",
            "[승률] ⚠️ 교전 빈도 조절로 승률 개선이 가능합니다.",
            "[승률] 🔄 팀워크에 집중하면 결과가 좋아질 거예요.",
            "[승률] 🧭 전략적인 이동이 승리에 큰 영향을 미칩니다."
        ])
    elif win_rate < 10:
        return random.choice([
            "[승률] 📈 승률이 점차 좋아지고 있습니다. 팀워크 강화하세요.",
            "[승률] 🤝 협력과 포지셔닝이 승률 핵심입니다.",
            "[승률] 📊 꾸준한 성장세입니다. 더 좋은 결과 기대돼요.",
            "[승률] 🎯 팀 플레이 집중하면 더 나아질 겁니다.",
            "[승률] 👍 전략 수정이 효과를 발휘하고 있습니다.",
            "[승률] 🏅 점진적인 향상이 눈에 띕니다.",
            "[승률] 🛡 안정적인 운영으로 팀에 도움이 됩니다."
        ])
    elif win_rate < 20:
        return random.choice([
            "[승률] 🟢 꽤 좋은 승률입니다! 전략이 잘 맞고 있네요.",
            "[승률] 🎖 팀워크와 운영이 안정적입니다.",
            "[승률] 🏆 승리 경험이 늘어나면서 자신감도 붙었어요.",
            "[승률] 🌟 좋은 위치 선정과 판단력이 돋보입니다.",
            "[승률] 🚀 꾸준한 승리로 성장 중인 플레이어입니다.",
            "[승률] 🎯 전략적인 운영으로 팀에 큰 도움이 되고 있어요.",
            "[승률] 👍 승률 향상을 위한 노력이 보입니다."
        ])
    elif win_rate < 40:
        return random.choice([
            "[승률] 🏅 매우 훌륭한 승률입니다! 전투와 전략이 조화롭습니다.",
            "[승률] 🎯 팀을 이끄는 리더 역할을 잘 해내고 있어요.",
            "[승률] 🚀 안정적인 플레이로 좋은 결과를 만들어가고 있습니다.",
            "[승률] 🌟 뛰어난 전략과 판단력으로 승률을 유지합니다.",
            "[승률] 💪 전투 집중력이 우수한 편입니다.",
            "[승률] 🥇 팀에서 핵심적인 역할을 맡고 있네요.",
            "[승률] 🎉 지속적인 성장과 좋은 성적을 보여주고 있습니다."
        ])
    else:
        return random.choice([
            "[승률] 🏆 압도적인 승률! 최상위권 플레이어입니다.",
            "[승률] 🎖 뛰어난 전략과 운영 능력으로 팀을 이끕니다.",
            "[승률] 🌟 완벽한 플레이 스타일과 판단력을 갖췄어요.",
            "[승률] 🚀 높은 승률로 전장에서 지배적인 위치를 차지합니다.",
            "[승률] 🥇 최고의 승률로 많은 팀원들의 신뢰를 받고 있어요.",
            "[승률] 💥 놀라운 집중력과 전투 능력으로 승리를 쌓고 있습니다.",
            "[승률] 🎉 꾸준히 정상급 플레이를 보여주는 프로 수준입니다."
        ])

def detailed_feedback(avg_damage, kd, win_rate):
    return "\n".join([
        get_avg_damage_feedback(avg_damage),
        get_kd_feedback(kd),
        get_winrate_feedback(win_rate)
    ])

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

# ✅ 차트 이미지 생성 및 전송 함수
async def send_stats_chart(interaction, stats, nickname):
    modes = ["solo", "duo", "squad"]
    rounds_played = []
    labels = []

    for mode in modes:
        mode_stats = stats["data"]["attributes"]["gameModeStats"].get(mode)
        if mode_stats and mode_stats["roundsPlayed"] > 0:
            rounds_played.append(mode_stats["roundsPlayed"])
            labels.append(mode.upper())

    if not rounds_played:
        await interaction.followup.send("No data available to create chart.")
        return

    # SQUAD 모드 데이터로 추가 통계 가져오기
    squad_stats = stats["data"]["attributes"]["gameModeStats"].get("squad", {})
    avg_damage = squad_stats.get("damageDealt", 0)
    wins = squad_stats.get("wins", 0)
    rounds = squad_stats.get("roundsPlayed", 1)
    kills = squad_stats.get("kills", 0)
    kd = kills / max(1, rounds - wins)
    win_rate = (wins / max(1, rounds)) * 100

    plt.figure(figsize=(8,5))
    bars = plt.bar(labels, rounds_played, color=['#1f77b4', '#ff7f0e', '#2ca02c'])
    plt.title(f"PUBG Game Count by Mode for {nickname}", fontsize=14, weight='bold')
    plt.ylabel("Games Played", fontsize=12)
    plt.ylim(0, max(rounds_played)*1.2)
    plt.grid(axis='y', linestyle='--', alpha=0.6)

    # 막대 위 숫자 표시
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, height * 1.02, f'{int(height)}', ha='center', va='bottom', fontsize=11)

    # 차트 오른쪽에 텍스트 박스 추가
    stats_text = (
        f"Squad Stats Summary:\n"
        f"Avg Damage: {avg_damage:.1f}\n"
        f"K/D Ratio: {kd:.2f}\n"
        f"Win Rate: {win_rate:.1f}%"
    )
    plt.gcf().text(0.85, 0.6, stats_text, fontsize=11, bbox=dict(facecolor='lightgray', alpha=0.3, boxstyle='round,pad=0.5'))

    plt.tight_layout(rect=[0,0,0.8,1])  # 오른쪽 공간 확보

    chart_path = "temp_chart.png"
    plt.savefig(chart_path)
    plt.close()

    await interaction.followup.send(file=discord.File(chart_path))
    os.remove(chart_path)

# ✅ 슬래시 커맨드
@tree.command(name="전적", description="PUBG 닉네임으로 전적 조회", guild=discord.Object(id=GUILD_ID))
async def 전적(interaction: discord.Interaction, 닉네임: str):
    await interaction.response.defer()

    if not can_make_request():
        await interaction.followup.send("⚠️ API 요청 제한(분당 10회)으로 인해 잠시 후 다시 시도해주세요.", ephemeral=True)
        return

    try:
        register_request()
        player_id = get_player_id(닉네임)
        season_id = get_season_id()
        stats = get_player_stats(player_id, season_id)

        # 전체 전적 요약 (SOLO, DUO, SQUAD)
        summary = summarize_stats(stats)

        # SQUAD 전적 기반 피드백
        squad_metrics, error = extract_squad_metrics(stats)
        if squad_metrics:
            avg_damage, kd, win_rate = squad_metrics
            feedback = detailed_feedback(avg_damage, kd, win_rate)
        else:
            feedback = error

        # Embed 구성: 필드 분리
        embed = discord.Embed(
            title=f"{닉네임}님의 PUBG 전적 요약",
            color=discord.Color.teal()
        )
        embed.add_field(name="🧾 전체 전적 요약", value=summary, inline=False)
        embed.add_field(name="📊 SQUAD 분석 피드백", value=feedback, inline=False)
        embed.set_footer(text="PUBG API 제공")

        await interaction.followup.send(embed=embed)

        # 여기서 차트 이미지 전송 함수 호출
        await send_stats_chart(interaction, stats, 닉네임)

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


# ✅ 슬래시 명령어: 밥
@tree.command(name="밥", description="밥좀묵겠습니다 채널로 이동", guild=discord.Object(id=GUILD_ID))
async def 밥(interaction: discord.Interaction):
    user = interaction.user
    guild = interaction.guild
    vc = discord.utils.get(guild.voice_channels, name="밥좀묵겠습니다")
    if not vc:
        await interaction.response.send_message("❌ 채널 없음", ephemeral=True)
        return
    try:
        await user.move_to(vc)
        await interaction.response.send_message("🍚 밥 채널로 이동 완료", ephemeral=True)

        task = asyncio.create_task(auto_disconnect_after_timeout(user, vc, timeout=1200))
        auto_disconnect_tasks[user.id] = task
    except:
        await interaction.response.send_message("❌ 이동 실패", ephemeral=True)


# ——— 여기부터 추가 ———
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


from discord.ui import View, button


class VoiceTopButton(View):
    def __init__(self):
        super().__init__(timeout=180)  # 뷰 타임아웃 3분

    @button(label="접속시간랭킹 보기", style=discord.ButtonStyle.primary)
    async def on_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=False)

        try:
            response = supabase.rpc("get_top_voice_activity", {}).execute()

            if not hasattr(response, "data") or response.data is None:
                await interaction.followup.send("❌ Supabase 응답 오류 또는 데이터 없음", ephemeral=False)
                return

            data = response.data
            if not data:
                await interaction.followup.send("😥 기록된 접속 시간이 없습니다.", ephemeral=False)
                return

            msg = "🎤 음성 접속시간 Top 10\n"
            for rank, info in enumerate(data, 1):
                time_str = format_duration(info['total_duration'])
                msg += f"{rank}. {info['username']} — {time_str}\n"

            button.disabled = True
            try:
                await interaction.message.edit(view=self)
            except discord.errors.NotFound:
                print("⚠️ 편집할 메시지를 찾을 수 없습니다.")

            await interaction.followup.send(msg, ephemeral=False)

        except Exception as e:
            await interaction.followup.send(f"❗ 오류 발생: {e}", ephemeral=False)


@tree.command(name="접속시간랭킹", description="음성 접속시간 Top 10", guild=discord.Object(id=GUILD_ID))
async def 접속시간랭킹(interaction: discord.Interaction):
    # 1) 즉시 defer — followup 으로 버튼 메시지 전송 준비
    await interaction.response.defer(ephemeral=True)
    # 2) 버튼 메시지는 followup.send 로
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
    print(f"✅ 봇 로그인: {bot.user}")


keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ 환경변수 DISCORD_TOKEN이 없습니다.")
