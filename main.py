from keep_alive import keep_alive

import discord
from discord.ext import commands, tasks
from discord import app_commands
import re
import os
import random
import asyncio
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
        if all(len(ch.members) == 0 for ch in monitored_channels):
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
        value="선택한 음성 채널의 인원들을 **내가 있는 채널로 소환**합니다.\n"
              "`all` 선택 시 `밥좀묵겠습니다`, `쉼터`, `클랜훈련소`는 제외됩니다.",
        inline=False
    )

    embed.add_field(
        name="🎲 /팀짜기",
        value="현재 음성 채널 인원을 팀으로 나누고, **빈 일반 채널로 자동 분배**합니다.\n"
              "예: 팀당 3명씩 랜덤으로 나눠 일반1, 일반2로 이동",
        inline=False
    )

    embed.add_field(
        name="🍚 /밥",
        value="`밥좀묵겠습니다` 채널로 자신을 이동시킵니다.\n"
              "20분 이상 활동이 없으면 자동 퇴장됩니다.",
        inline=False
    )

    embed.add_field(
        name="🧪 /검사",
        value="서버 멤버들의 **닉네임 형식을 검사**합니다.\n"
              "올바른 닉네임: `이름/ID/두자리숫자`",
        inline=False
    )

    embed.add_field(
        name="📈 /접속시간랭킹",
        value="음성 채널에서 활동한 **접속 시간 Top 10 랭킹**을 확인합니다.\n"
              "버튼 클릭 시 접속 시간 확인 가능",
        inline=False
    )

    embed.set_footer(text="기타 문의는 관리자에게 DM 주세요!")
    await interaction.response.send_message(embed=embed, ephemeral=True)


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


# --- 기존 채널 선택 UI ---
class ChannelSelect(discord.ui.Select):
    def __init__(self, channels: list[str]):
        options = [discord.SelectOption(label=ch) for ch in channels]
        super().__init__(
            placeholder="소환할 채널을 선택하세요 (여러 개 선택 가능)",
            min_values=1,
            max_values=len(options),
            options=options,
            # custom_id에 고유값 부여 (uuid4 사용)
            custom_id=f"channel_select_{uuid.uuid4()}"
        )

    async def callback(self, interaction: discord.Interaction):
        vc = interaction.user.voice.channel if interaction.user.voice else None
        if not vc:
            await interaction.response.send_message("❌ 먼저 음성 채널에 들어가주세요!", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        selected = self.values
        if "all" in selected:
            target_channels = [
                ch for ch in interaction.guild.voice_channels
                if ch.name not in EXCLUDED_CHANNELS
            ]
            excluded_note = "\n\n❗️`all` 선택 시 `밥좀묵겠습니다`, `쉼터`, `클랜훈련소`는 제외됩니다."
        else:
            target_channels = [
                ch for ch in interaction.guild.voice_channels
                if ch.name in selected
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
            return

        embed = discord.Embed(
            title="📢 쿠치요세노쥬츠 !",
            description=f"{interaction.user.mention} 님이 **{moved}명**을 음성채널로 소환했습니다."
                        f"{excluded_note}",
            color=discord.Color.green()
        )
        embed.set_image(url="https://raw.githubusercontent.com/Na-seunghyun/my-discord-bot/main/123123.gif")
        await interaction.followup.send(embed=embed)


class ChannelSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        # 매번 고유한 custom_id 가진 Select 인스턴스 생성
        self.add_item(ChannelSelect(CHANNEL_CHOICES))


# --- 새로 추가: 멤버 선택 UI ---
class MemberSelect(discord.ui.Select):
    def __init__(self, members: list[discord.Member]):
        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id))
            for m in members if not m.bot
        ]
        super().__init__(
            placeholder="소환할 멤버를 선택하세요 (여러 개 선택 가능)",
            min_values=1,
            max_values=min(25, len(options)),  # 디스코드 select 최대 25개
            options=options,
            # custom_id에 고유값 부여 (uuid4 사용)
            custom_id=f"member_select_{uuid.uuid4()}"
        )

    async def callback(self, interaction: discord.Interaction):
        vc = interaction.user.voice.channel if interaction.user.voice else None
        if not vc:
            await interaction.response.send_message("❌ 먼저 음성 채널에 들어가주세요!", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        guild = interaction.guild
        selected_member_ids = [int(id_) for id_ in self.values]
        moved = 0

        for member_id in selected_member_ids:
            member = guild.get_member(member_id)
            if member and member.voice and member.voice.channel != vc and not member.bot:
                try:
                    await member.move_to(vc)
                    moved += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"❌ {member.display_name} 이동 실패: {e}")

        if moved == 0:
            await interaction.followup.send("⚠️ 이동할 멤버가 없습니다.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📢 쿠치요세노쥬츠 !",
            description=f"{interaction.user.mention} 님이 **{moved}명**을 음성채널로 소환했습니다.",
            color=discord.Color.green()
        )
        embed.set_image(url="https://raw.githubusercontent.com/Na-seunghyun/my-discord-bot/main/123123.gif")
        await interaction.followup.send(embed=embed)


class MemberSelectView(discord.ui.View):
    def __init__(self, members: list[discord.Member]):
        super().__init__(timeout=60)
        # 매번 고유한 custom_id 가진 Select 인스턴스 생성
        self.add_item(MemberSelect(members))


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


# ✅ 슬래시 명령어: 소환 (명령어 등록)
@tree.command(name="소환", description="음성 채널 인원 소환", guild=discord.Object(id=GUILD_ID))
async def 소환(interaction: discord.Interaction):
    # 명령어 실행 시 ChannelSelectView 보여줌
    await interaction.response.send_message("소환할 채널을 선택해주세요.", view=ChannelSelectView(), ephemeral=True)


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
