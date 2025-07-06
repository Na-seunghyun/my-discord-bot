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
import json
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client

# --- 환경 설정 및 상수 ---
KST = timezone(timedelta(hours=9))
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
GUILD_ID = 1309433603331198977
MONITORED_CHANNEL_NAMES = [f"일반{i}" for i in range(1, 17)] + ["큰맵1", "큰맵2"]
EXCLUDED_CHANNELS = ["밥좀묵겠습니다", "쉼터", "클랜훈련소"]
CHANNEL_CHOICES = ["all"] + EXCLUDED_CHANNELS + ["게스트방", "대기방", "큰맵1", "큰맵2"] + [f"일반{i}" for i in range(1, 17)]
nickname_pattern = re.compile(r"^[가-힣a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/\d{2}$")

# --- 디스코드 봇 설정 ---
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# --- 상태 관리 변수 ---
auto_disconnect_tasks = {}
dm_sent_users = set()
waiting_room_message_cache = {}
all_empty_since = None
notified_after_empty = False
streaming_members = set()

# --- 자동 퇴장 로직 ---
async def auto_disconnect_after_timeout(member, voice_channel, text_channel):
    """밥좀묵겠습니다 채널 20분 자동퇴장 처리"""
    try:
        await asyncio.sleep(20 * 60)
        if member.voice and member.voice.channel == voice_channel:
            await member.move_to(None)
            if text_channel:
                await text_channel.send(
                    f"⏰ {member.mention}님이 '밥좀묵겠습니다' 채널에 20분 이상 머물러 자동 퇴장 처리되었습니다.")
    except asyncio.CancelledError:
        pass
    finally:
        auto_disconnect_tasks.pop(member.id, None)

# --- 봇 준비 이벤트 ---
@bot.event
async def on_ready():
    print(f"✅ 봇 온라인: {bot.user.name}")
    await asyncio.sleep(3)
    for guild in bot.guilds:
        bap_channel = discord.utils.get(guild.voice_channels, name="밥좀묵겠습니다")
        text_channel = discord.utils.get(guild.text_channels, name="자유채팅방")
        if bap_channel:
            for member in bap_channel.members:
                if member.bot or member.id in auto_disconnect_tasks:
                    continue
                try:
                    await member.send(f"🍚 {member.display_name}님, '밥좀묵겠습니다' 채널에 입장 중입니다. 20분 후 자동 퇴장됩니다.")
                except Exception: pass
                task = asyncio.create_task(auto_disconnect_after_timeout(member, bap_channel, text_channel))
                auto_disconnect_tasks[member.id] = task
    guild = discord.Object(id=GUILD_ID)
    await tree.sync(guild=guild)
    check_voice_channels_for_streaming.start()

# --- 음성채널 상태 변화 이벤트 ---
@bot.event
async def on_voice_state_update(member, before, after):
    global all_empty_since, notified_after_empty, streaming_members
    if member.bot: return
    bap_channel = discord.utils.get(member.guild.voice_channels, name="밥좀묵겠습니다")
    text_channel = discord.utils.get(member.guild.text_channels, name="자유채팅방")

    # 밥좀묵겠습니다 채널 자동퇴장 타이머 관리
    if after.channel == bap_channel and before.channel != bap_channel:
        if member.id in auto_disconnect_tasks:
            auto_disconnect_tasks[member.id].cancel()
            auto_disconnect_tasks.pop(member.id, None)
        if member.id not in dm_sent_users:
            try:
                await member.send(f"🍚 {member.display_name}님, '밥좀묵겠습니다' 채널에 입장하셨습니다. 20분 후 자동 퇴장됩니다.")
                dm_sent_users.add(member.id)
            except Exception: pass
        task = asyncio.create_task(auto_disconnect_after_timeout(member, bap_channel, text_channel))
        auto_disconnect_tasks[member.id] = task
    elif before.channel == bap_channel and after.channel != bap_channel:
        if member.id in auto_disconnect_tasks:
            auto_disconnect_tasks[member.id].cancel()
            auto_disconnect_tasks.pop(member.id, None)
        dm_sent_users.discard(member.id)

    # 대기방 입장 중복 안내 방지
    now_utc = datetime.utcnow()
    if (before.channel != after.channel) and (after.channel is not None) and after.channel.name == "대기방":
        last_sent = waiting_room_message_cache.get(member.id)
        if not last_sent or (now_utc - last_sent) > timedelta(seconds=30):
            if text_channel:
                await text_channel.send(f"{member.mention} 나도 게임하고싶어! 나 도 끼 워 줘!")
                waiting_room_message_cache[member.id] = now_utc

    # 모니터링 채널 첫 입장/마지막 퇴장 감지
    now = datetime.now(timezone.utc)
    guild = member.guild
    monitored_channels = [ch for ch in guild.voice_channels if ch.name in MONITORED_CHANNEL_NAMES]
    all_empty = all(len(ch.members) == 0 for ch in monitored_channels)
    if before.channel and before.channel.name in MONITORED_CHANNEL_NAMES and all_empty:
        if all_empty_since is None:
            all_empty_since = now
            notified_after_empty = False
    if before.channel is None and after.channel and after.channel.name in MONITORED_CHANNEL_NAMES:
        if all_empty_since and (now - all_empty_since).total_seconds() >= 3600 and not notified_after_empty:
            if text_channel:
                embed = discord.Embed(
                    title="🚀 첫 배그 포문이 열립니다!",
                    description=f"{member.mention} 님이 첫 배그 포문을 열려고 합니다.\n\n같이 해주실 인원들은 현시간 부로 G-pop 바랍니다.",
                    color=discord.Color.blue()
                )
                await text_channel.send(content='@everyone', embed=embed)
            notified_after_empty = True
    if not all_empty:
        all_empty_since, notified_after_empty = None, False

    # Supabase 음성채널 입장/퇴장 기록
    if before.channel is None and after.channel is not None:
        user_id, username = str(member.id), member.display_name
        now = datetime.now(timezone.utc).replace(microsecond=0)
        try:
            existing = supabase.rpc("get_active_voice_activity", {"user_id_input": user_id}).execute()
            if hasattr(existing, 'data') and existing.data and len(existing.data) > 0:
                return
            data = {"user_id": user_id, "username": username, "joined_at": now.isoformat(), "left_at": None, "duration_sec": 0}
            supabase.table("voice_activity").insert(data).execute()
        except Exception: pass
    elif before.channel is not None and after.channel is None:
        user_id, username = str(member.id), member.display_name
        now = datetime.now(timezone.utc).replace(microsecond=0)
        try:
            records = supabase.rpc("get_active_voice_activity", {"user_id_input": user_id}).execute()
            if hasattr(records, 'data') and records.data and len(records.data) > 0:
                record = records.data[0]
                joined_at_str = record.get("joined_at")
                if not joined_at_str: return
                joined_at_dt = datetime.fromisoformat(joined_at_str)
                duration = int((now - joined_at_dt).total_seconds())
                update_data = {"left_at": now.isoformat(), "duration_sec": duration}
                supabase.table("voice_activity").update(update_data).eq("id", record["id"]).execute()
        except Exception: pass

    # Go Live(방송) 알림
    if not before.self_stream and after.self_stream and after.channel is not None:
        if member.id not in streaming_members:
            streaming_members.add(member.id)
            if text_channel:
                embed = discord.Embed(
                    title="📺 방송 시작 알림!",
                    description=f"{member.mention} 님이 `{after.channel.name}` 채널에서 방송을 시작했어요!\n👀 모두 구경하러 가보세요!",
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
                embed.set_footer(text="Go Live 활성화됨")
                await text_channel.send(embed=embed)
    if before.self_stream and not after.self_stream:
        streaming_members.discard(member.id)

# --- 방송(Go Live) 꺼짐 체크 루프 ---
@tasks.loop(minutes=30)
async def check_voice_channels_for_streaming():
    for guild in bot.guilds:
        text_channel = discord.utils.get(guild.text_channels, name="자유채팅방")
        if not text_channel: continue
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

# --- 슬래시 명령어: 도움말 ---
@tree.command(name="도움말", description="봇 명령어 및 기능 안내", guild=discord.Object(id=GUILD_ID))
async def 도움말(interaction: discord.Interaction):
    """현재 사용 가능한 봇 주요 슬래시 명령어 안내 (밥 기능 제외)"""
    embed = discord.Embed(
        title="🤖 봇 명령어 안내",
        description="서버 관리와 음성채널 활동을 돕는 주요 명령어 목록입니다.",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="📢 /소환",
        value=(
            "선택한 음성 채널의 인원들을 **내가 있는 채널로 소환**합니다.\n"
            "`all` 선택 시 일부 채널(밥좀묵겠습니다, 쉼터, 클랜훈련소) 제외"
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
        name="🧪 /검사",
        value="서버 멤버들의 **닉네임 형식을 검사**합니다. (예: 이름/ID/두자리숫자)",
        inline=False
    )
    embed.add_field(
        name="📈 /접속시간랭킹",
        value="음성 채널 **접속 시간 Top 10 랭킹**을 버튼으로 확인할 수 있습니다.",
        inline=False
    )
    embed.add_field(
        name="🎯 /개별소환",
        value="음성 채널에 있는 멤버를 골라서 **내가 있는 채널로 소환**합니다.",
        inline=False
    )
    embed.add_field(
        name="🏅 /전적",
        value="PUBG 닉네임으로 전적을 조회하고, 분석 피드백을 제공합니다.",
        inline=False
    )
    embed.set_footer(text="기타 문의는 관리자에게 DM 주세요!")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# --- 채널 소환 Select & Button 및 View ---

class ChannelSelect(discord.ui.Select):
    """여러 음성채널을 선택하는 드롭다운"""
    def __init__(self, view):
        options = [discord.SelectOption(label=ch) for ch in CHANNEL_CHOICES]
        super().__init__(
            placeholder="소환할 채널을 선택하세요 (여러 개 선택 가능)",
            min_values=1,
            max_values=len(options),
            options=options,
            row=0
        )
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_channels = self.values
        selected_str = ", ".join(self.values)
        await interaction.response.edit_message(
            content=f"선택한 채널: {selected_str}",
            view=self.parent_view
        )

class ChannelConfirmButton(discord.ui.Button):
    """채널 선택 후 소환 확정 버튼"""
    def __init__(self, view):
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

        await interaction.response.defer(thinking=True)
        target_channels = []
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
                    except Exception:
                        pass

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
    """채널 선택 + 소환 버튼 View"""
    def __init__(self):
        super().__init__(timeout=60)
        self.selected_channels = []
        self.add_item(ChannelSelect(self))
        self.add_item(ChannelConfirmButton(self))

# --- 소환 슬래시 명령어 ---
@tree.command(name="소환", description="음성 채널 인원 소환", guild=discord.Object(id=GUILD_ID))
async def 소환(interaction: discord.Interaction):
    await interaction.response.send_message("소환할 채널을 선택해주세요.", view=ChannelSelectView(), ephemeral=True)



# --- 멤버 소환 Select & Button 및 View ---

class MemberSelect(discord.ui.Select):
    """여러 멤버를 선택하는 드롭다운"""
    def __init__(self, members, view):
        options = [
            discord.SelectOption(label=m.display_name, value=str(m.id))
            for m in members if not m.bot
        ]
        super().__init__(
            placeholder="소환할 멤버를 선택하세요 (여러 명 가능)",
            min_values=1,
            max_values=min(25, len(options)),
            options=options,
            row=0
        )
        self.parent_view = view

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_member_ids = [int(v) for v in self.values]
        selected_names = [option.label for option in self.options if option.value in self.values]
        selected_str = ", ".join(selected_names)
        await interaction.response.edit_message(
            content=f"선택한 멤버: {selected_str}",
            view=self.parent_view
        )

class MemberConfirmButton(discord.ui.Button):
    """멤버 선택 후 소환 확정 버튼"""
    def __init__(self, view):
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

        await interaction.response.defer(thinking=True)
        moved = 0
        for member_id in selected_ids:
            member = interaction.guild.get_member(member_id)
            if member and member.voice and member.voice.channel != vc and not member.bot:
                try:
                    await member.move_to(vc)
                    moved += 1
                    await asyncio.sleep(0.5)
                except Exception:
                    pass

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
    """멤버 선택 + 소환 버튼 View"""
    def __init__(self, members):
        super().__init__(timeout=60)
        self.selected_member_ids = []
        self.add_item(MemberSelect(members, self))
        self.add_item(MemberConfirmButton(self))

# --- 개별소환 슬래시 명령어 ---
@tree.command(name="개별소환", description="특정 멤버를 선택해 소환합니다.", guild=discord.Object(id=GUILD_ID))
async def 개별소환(interaction: discord.Interaction):
    vc = interaction.user.voice.channel if interaction.user.voice else None
    if not vc:
        await interaction.response.send_message("❌ 음성 채널에 먼저 들어가 주세요!", ephemeral=True)
        return

    members = [m for m in interaction.guild.members if m.voice and m.voice.channel and not m.bot]
    if not members:
        await interaction.response.send_message("⚠️ 음성채널에 있는 멤버가 없습니다.", ephemeral=True)
        return

    view = MemberSelectView(members)
    await interaction.response.send_message("소환할 멤버를 선택하세요:", view=view, ephemeral=True)


# --- 팀 이동 View ---
class TeamMoveView(discord.ui.View):
    """팀을 빈 채널로 자동 이동시키는 버튼 View"""
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
                except Exception:
                    pass
        self.moved = True
        button.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

# --- 팀짜기 슬래시 명령어 ---
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


# --- 닉네임 검사 슬래시 명령어 ---
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

# --- 접속시간랭킹 버튼 View ---
class VoiceTopButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
    @discord.ui.button(label="접속시간랭킹 보기", style=discord.ButtonStyle.primary)
    async def on_click(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=False)
        # ... (이하 supabase 랭킹 조회 로직 기존대로)

@tree.command(name="접속시간랭킹", description="음성 접속시간 Top 10", guild=discord.Object(id=GUILD_ID))
async def 접속시간랭킹(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await interaction.followup.send(
        "버튼을 눌러 음성 접속시간 랭킹을 확인하세요.",
        view=VoiceTopButton(),
        ephemeral=True
    )





keep_alive()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ 환경변수 DISCORD_TOKEN이 없습니다.")
