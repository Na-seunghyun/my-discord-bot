# main.py (정리된 전체 코드 - Part 1)

from keep_alive import keep_alive

# ────────────────────────── 기본 모듈 ──────────────────────────
import discord
from discord.ext import commands, tasks
from discord import app_commands
import os, re, json, asyncio, random, requests, aiohttp, uuid
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
from dotenv import load_dotenv
from supabase import create_client, Client

# ──────────────────────── 환경변수 및 기본값 ────────────────────────
load_dotenv()
KST = timezone(timedelta(hours=9))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_KEY = os.getenv("PUBG_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if not SUPABASE_URL or not SUPABASE_KEY or not DISCORD_TOKEN or not API_KEY:
    print("❌ 환경변수가 누락되었습니다. .env 파일 확인 요망")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ──────────────────────── 디스코드 설정 ────────────────────────
GUILD_ID = 1309433603331198977
WELCOME_CHANNEL_NAME = "자유채팅방"
MONITORED_CHANNEL_NAMES = [f"일반{i}" for i in range(1, 17)] + ["큰맵1", "큰맵2"]
EXCLUDED_CHANNELS = ["밥좀묵겠습니다", "쉼터", "클랜훈련소"]

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ──────────────────────── 전역 상태 변수 ────────────────────────
nickname_pattern = re.compile(r"^[가-힣a-zA-Z0-9_()\-\s]+/[a-zA-Z0-9_-]+/\\d{2}$")
auto_disconnect_tasks = {}
voice_join_times = {}
dm_sent_users = set()
waiting_room_message_cache = {}
streaming_members = set()
invites_cache = {}
auto_kicked_members = {}
all_empty_since = None
notified_after_empty = False

# ──────────────────────── 파일 경로 ────────────────────────
BALANCE_FILE = "balance.json"
WARNINGS_FILE = "warnings.json"
BADWORDS_FILE = "badwords.txt"
LEADERBOARD_FILE = "season_leaderboard.json"
VALID_IDS_FILE = "valid_pubg_ids.json"



# ──────────────────────── [1] 도박 잔고 시스템 ────────────────────────
def ensure_balance_file():
    if not os.path.exists(BALANCE_FILE):
        with open(BALANCE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

def load_balances():
    ensure_balance_file()
    with open(BALANCE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_balances(data):
    if len(data) > 1000:
        data = dict(sorted(data.items(), key=lambda x: x[1].get("last_updated", ""), reverse=True)[:1000])
    with open(BALANCE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def get_balance(user_id):
    data = load_balances()
    return data.get(str(user_id), {}).get("amount", 0)

def set_balance(user_id, amount):
    data = load_balances()
    data[str(user_id)] = {
        "amount": amount,
        "last_updated": datetime.utcnow().isoformat()
    }
    save_balances(data)

def add_balance(user_id, amount):
    current = get_balance(user_id)
    set_balance(user_id, current + amount)

# 하루 1회 5000원 지급
daily_claims = {}
@tree.command(name="돈줘", description="하루에 한 번 5000원 지급", guild=discord.Object(id=GUILD_ID))
async def 돈줘(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    today = datetime.now(KST).date()

    if daily_claims.get(user_id) == today:
        embed = discord.Embed(
            title="❌ 이미 수령하셨습니다",
            description="오늘은 이미 받으셨습니다! 내일 다시 시도해주세요.",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    add_balance(user_id, 5000)
    daily_claims[user_id] = today

    embed = discord.Embed(
        title="💰 돈이 지급되었습니다!",
        description="하루 한 번! 5,000원이 지급되었습니다.\n도박은 책임감 있게!",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ──────────────────────── [2] 욕설 필터링 및 경고 시스템 ────────────────────────
def load_badwords_regex(file_path=BADWORDS_FILE):
    regex_patterns = []
    if not os.path.exists(file_path):
        return regex_patterns
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            word = line.strip().lower()
            if not word:
                continue
            pattern = ".*?".join([re.escape(ch) for ch in word])
            regex_patterns.append(re.compile(pattern, re.IGNORECASE))
    return regex_patterns

BADWORD_PATTERNS = load_badwords_regex()

if os.path.exists(WARNINGS_FILE):
    with open(WARNINGS_FILE, "r", encoding="utf-8") as f:
        warnings = json.load(f)
else:
    warnings = {}

def save_warnings():
    with open(WARNINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(warnings, f, indent=4)

def censor_badwords_regex(text, badword_patterns):
    censored_text = text
    for pattern in badword_patterns:
        censored_text = pattern.sub("***", censored_text)
    return censored_text

@bot.event
async def on_message(message):
    if message.author.bot or str(message.channel.name) != WELCOME_CHANNEL_NAME:
        return

    lowered_msg = message.content.lower()
    if any(p.search(lowered_msg) for p in BADWORD_PATTERNS):
        censored = censor_badwords_regex(message.content, BADWORD_PATTERNS)
        try:
            await message.delete()
        except Exception as e:
            print(f"메시지 삭제 실패: {e}")

        embed = discord.Embed(
            title="💬 욕설 필터링 안내",
            description=f"{message.author.mention} 님의 메시지가 필터링 되었습니다.\n\n**필터링된 메시지:**\n{censored}",
            color=0xFFD700
        )
        embed.set_footer(text="💡 오덕봇은 욕설을 자동으로 걸러주는 평화주의자입니다.")
        await message.channel.send(embed=embed)

        user_id = str(message.author.id)
        warnings[user_id] = warnings.get(user_id, 0) + 1
        save_warnings()

    await bot.process_commands(message)

@tree.command(name="경고확인", description="누가 몇 번 경고받았는지 확인", guild=discord.Object(id=GUILD_ID))
async def check_warnings(interaction: discord.Interaction):
    if not warnings:
        await interaction.response.send_message("📢 현재까지 경고받은 유저가 없습니다.")
        return

    guild = interaction.guild
    report = []
    for user_id, count in warnings.items():
        member = guild.get_member(int(user_id))
        name = member.display_name if member else f"알 수 없음 ({user_id})"
        report.append(f"{name}: {count}회")

    await interaction.response.send_message("📄 경고 목록:\n" + "\n".join(report))

@tree.command(name="경고초기화", description="특정 유저 경고 초기화 (관리자 전용)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="경고를 초기화할 유저를 선택하세요")
async def reset_warning(interaction: discord.Interaction, user: discord.Member):
    member = interaction.user
    is_admin = member.guild_permissions.administrator or discord.utils.get(member.roles, name="채널관리자")

    if not is_admin:
        await interaction.response.send_message("❌ 관리자만 사용할 수 있는 명령어입니다.", ephemeral=True)
        return

    user_id = str(user.id)
    if user_id in warnings:
        warnings[user_id] = 0
        save_warnings()
        await interaction.response.send_message(f"✅ {user.display_name}님의 경고 횟수가 초기화되었습니다.")
    else:
        await interaction.response.send_message(f"ℹ️ {user.display_name}님은 현재 경고 기록이 없습니다.")


# ──────────────────────── [3] PUBG 전적 API 관련 ────────────────────────

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
    return response.json()["data"][0]["id"]

def get_season_id():
    url = f"https://api.pubg.com/shards/{PLATFORM}/seasons"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    for season in response.json()["data"]:
        if season["attributes"]["isCurrentSeason"]:
            return season["id"]

def get_player_stats(player_id, season_id):
    url = f"https://api.pubg.com/shards/{PLATFORM}/players/{player_id}/seasons/{season_id}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def get_player_ranked_stats(player_id, season_id):
    url = f"https://api.pubg.com/shards/{PLATFORM}/players/{player_id}/seasons/{season_id}/ranked"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    return None

# 분석 피드백용 JSON 로딩
with open("feedback_data/pubg_feedback_full.json", "r", encoding="utf-8") as f:
    feedback_json = json.load(f)

def extract_squad_metrics(stats):
    mode_stats = stats["data"]["attributes"]["gameModeStats"].get("squad")
    if not mode_stats or mode_stats["roundsPlayed"] == 0:
        return None, "❌ 스쿼드 전적이 없습니다."
    r = mode_stats
    avg_damage = r["damageDealt"] / r["roundsPlayed"]
    kd = r["kills"] / max(1, r["roundsPlayed"] - r["wins"])
    win_rate = (r["wins"] / r["roundsPlayed"]) * 100
    return (avg_damage, kd, win_rate), None

# 구간 키 추출 함수
def get_damage_key(d): return f"D{min(9, int(d//50))}"
def get_kd_key(k): return "K0" if k<0.3 else "K1" if k<0.6 else "K2" if k<1 else "K3" if k<1.5 else "K4" if k<2 else "K5" if k<3 else "K6" if k<5 else "K7"
def get_winrate_key(w): return "W0" if w==0 else f"W{min(11, int(w//5)+1)}"

def detailed_feedback(avg_damage, kd, win_rate):
    dmg_msg = random.choice(feedback_json["damage"][get_damage_key(avg_damage)])
    kd_msg = random.choice(feedback_json["kdr"][get_kd_key(kd)])
    win_msg = random.choice(feedback_json["winrate"][get_winrate_key(win_rate)])
    return dmg_msg, kd_msg, win_msg

def get_rank_image_path(tier: str, sub_tier: str = "") -> str:
    tier = tier.capitalize()
    filename = f"{tier}-{sub_tier}.png" if sub_tier else f"{tier}.png"
    path = os.path.join("rank-image", filename)
    return path if os.path.exists(path) else os.path.join("rank-image", "Unranked.png")

# 중복 저장 방지용 타임스탬프
import time
recent_saves = {}

def save_player_stats_to_file(nickname, squad_metrics, ranked_stats, stats=None, discord_id=None, source="명령"):
    key = f"{nickname}_{discord_id}"
    now = time.time()
    if key in recent_saves and now - recent_saves[key] < 30:
        return
    recent_saves[key] = now

    season_id = get_season_id()
    data = {
        "nickname": nickname,
        "discord_id": str(discord_id),
        "timestamp": datetime.now().isoformat(),
        "squad": {
            "avg_damage": 0, "kd": 0, "win_rate": 0,
            "rounds_played": 0, "kills": 0
        }
    }

    if stats:
        s = stats["data"]["attributes"]["gameModeStats"].get("squad", {})
        data["squad"]["rounds_played"] = s.get("roundsPlayed", 0)
        data["squad"]["kills"] = s.get("kills", 0)

    if squad_metrics:
        data["squad"]["avg_damage"], data["squad"]["kd"], data["squad"]["win_rate"] = squad_metrics

    if ranked_stats and "data" in ranked_stats:
        ranked = ranked_stats["data"]["attributes"]["rankedGameModeStats"].get("squad")
        if ranked:
            data["ranked"] = {
                "tier": ranked.get("currentTier", {}).get("tier", "Unranked"),
                "subTier": ranked.get("currentTier", {}).get("subTier", ""),
                "points": ranked.get("currentRankPoint", 0)
            }

    if os.path.exists(LEADERBOARD_FILE):
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            file_data = json.load(f)
            stored_season_id = file_data.get("season_id")
            leaderboard = file_data.get("players", [])
    else:
        stored_season_id, leaderboard = None, []

    if stored_season_id != season_id:
        leaderboard = []

    leaderboard = [p for p in leaderboard if p.get("nickname") != nickname]
    leaderboard.append(data)

    with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
        json.dump({"season_id": season_id, "players": leaderboard}, f, ensure_ascii=False, indent=2)

# 슬래시 명령어: /전적
@tree.command(name="전적", description="PUBG 닉네임으로 전적 조회", guild=discord.Object(id=GUILD_ID))
async def 전적(interaction: discord.Interaction, 닉네임: str):
    try:
        await interaction.response.defer()
        if not can_make_request():
            await interaction.followup.send("⚠️ 요청 제한 중입니다. 잠시 후 시도해주세요.", ephemeral=True)
            return

        register_request()
        player_id = get_player_id(닉네임)
        season_id = get_season_id()
        stats = get_player_stats(player_id, season_id)
        ranked = get_player_ranked_stats(player_id, season_id)

        squad_metrics, error = extract_squad_metrics(stats)
        if squad_metrics:
            dmg_msg, kd_msg, win_msg = detailed_feedback(*squad_metrics)
        else:
            dmg_msg = kd_msg = win_msg = error or "데이터 없음"

        embed = discord.Embed(
            title=f"{닉네임}님의 PUBG 전적 요약",
            color=discord.Color.blue()
        )

        for mode in ["solo", "duo", "squad"]:
            m = stats["data"]["attributes"]["gameModeStats"].get(mode)
            if not m or m["roundsPlayed"] == 0:
                continue
            kd = m["kills"] / max(1, m["roundsPlayed"] - m["wins"])
            avg_dmg = m["damageDealt"] / m["roundsPlayed"]
            win_pct = m["wins"] / m["roundsPlayed"] * 100
            embed.add_field(name=mode.upper(), value=(
                f"게임 수: {m['roundsPlayed']}\n"
                f"승리 수: {m['wins']} ({win_pct:.1f}%)\n"
                f"킬 수: {m['kills']}\n"
                f"평균 데미지: {avg_dmg:.1f}\n"
                f"K/D: {kd:.2f}"
            ), inline=True)

        embed.add_field(name="📊 SQUAD 분석 피드백", value="전투 성능 기반 피드백입니다.", inline=False)
        embed.add_field(name="🔫 평균 데미지", value=f"```{dmg_msg}```", inline=False)
        embed.add_field(name="⚔️ K/D", value=f"```{kd_msg}```", inline=False)
        embed.add_field(name="🏆 승률", value=f"```{win_msg}```", inline=False)

        best_rank = {"points": -1}
        if ranked and "data" in ranked:
            for mode, r in ranked["data"]["attributes"]["rankedGameModeStats"].items():
                tier = r.get("currentTier", {}).get("tier", "Unknown")
                sub = r.get("currentTier", {}).get("subTier", "")
                pts = r.get("currentRankPoint", 0)
                embed.add_field(name=f"🏅 {mode.upper()} 랭크 티어", value=f"{tier} {sub}", inline=True)
                embed.add_field(name=f"🏅 포인트", value=str(pts), inline=True)
                if pts > best_rank["points"]:
                    best_rank = {"tier": tier, "sub": sub, "points": pts}

        thumb = get_rank_image_path(best_rank.get("tier", "Unranked"), best_rank.get("sub", ""))
        embed.set_thumbnail(url="attachment://rank.png")
        embed.set_footer(text="PUBG API 제공")

        save_player_stats_to_file(닉네임, squad_metrics, ranked, stats, interaction.user.id)
        image_file = discord.File(thumb, filename="rank.png")
        await interaction.followup.send(embed=embed, file=image_file)

    except Exception as e:
        await interaction.followup.send(f"❌ 오류 발생: {e}", ephemeral=True)

# ──────────────────────── [4] 음성채널 자동퇴장 / 대기방 메시지 / 활동 저장 ────────────────────────

async def auto_disconnect_after_timeout(member, voice_channel, text_channel):
    try:
        await asyncio.sleep(20 * 60)  # 20분 대기
        if member.voice and member.voice.channel == voice_channel:
            auto_kicked_members[member.id] = True
            await member.move_to(None)
            await asyncio.sleep(0.3)

            if text_channel:
                await text_channel.send(
                    f"⏰ {member.mention}님이 '밥좀묵겠습니다' 채널에 20분 이상 머물러 자동 퇴장 처리되었습니다.")
            auto_kicked_members.pop(member.id, None)

    except asyncio.CancelledError:
        print(f"⏹️ {member.display_name} 타이머 취소됨")
    finally:
        auto_disconnect_tasks.pop(member.id, None)

@bot.event
async def on_ready():
    for guild in bot.guilds:
        invites = await guild.invites()
        invites_cache[guild.id] = {invite.code: invite for invite in invites}

    print(f"✅ 봇 로그인: {bot.user}")
    auto_update_valid_ids.start()

    await asyncio.sleep(2)
    for guild in bot.guilds:
        bap_channel = discord.utils.get(guild.voice_channels, name="밥좀묵겠습니다")
        text_channel = discord.utils.get(guild.text_channels, name="봇알림")
        if bap_channel:
            for member in bap_channel.members:
                if not member.bot:
                    try:
                        await member.send("🍚 20분 후 자동 퇴장됩니다.")
                    except: pass
                    task = asyncio.create_task(auto_disconnect_after_timeout(member, bap_channel, text_channel))
                    auto_disconnect_tasks[member.id] = task

@bot.event
async def on_voice_state_update(member, before, after):
    global all_empty_since, notified_after_empty
    if member.bot:
        return

    bap_channel = discord.utils.get(member.guild.voice_channels, name="밥좀묵겠습니다")
    text_channel = discord.utils.get(member.guild.text_channels, name="봇알림")

    # 입장
    if after.channel == bap_channel and before.channel != bap_channel:
        if member.id not in dm_sent_users:
            try:
                await member.send("🍚 '밥좀묵겠습니다' 입장! 20분 후 자동 퇴장됩니다.")
                dm_sent_users.add(member.id)
            except: pass

        task = asyncio.create_task(auto_disconnect_after_timeout(member, bap_channel, text_channel))
        auto_disconnect_tasks[member.id] = task

    # 퇴장
    if before.channel == bap_channel and after.channel != bap_channel:
        task = auto_disconnect_tasks.get(member.id)
        if task:
            task.cancel()
            auto_disconnect_tasks.pop(member.id, None)
        dm_sent_users.discard(member.id)

    # 대기방 중복 메시지 방지
    now_utc = datetime.utcnow()
    if (before.channel != after.channel) and after.channel and after.channel.name == "대기방":
        last_sent = waiting_room_message_cache.get(member.id)
        if not last_sent or (now_utc - last_sent) > timedelta(seconds=30):
            if text_channel:
                await text_channel.send(f"{member.mention} 나도 게임하고싶어! 나 도 끼 워 줘!")
                waiting_room_message_cache[member.id] = now_utc

    # PUBG 감지 (첫 입장 감지)
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
                    description=(
                        f"{member.mention} 님이 첫 배그 포문을 열려고 합니다.\n\n"
                        "같이 해주실 인원들은 G-pop 바랍니다!"
                    ),
                    color=discord.Color.blue()
                )
                await text_channel.send(content='@everyone', embed=embed)
            notified_after_empty = True

    if not all_empty:
        all_empty_since = None
        notified_after_empty = False

    # ───── Supabase 입장/퇴장 기록 저장 ─────
    user_id = str(member.id)
    username = member.display_name
    now = datetime.now(timezone.utc).replace(microsecond=0)

    try:
        if before.channel is None and after.channel is not None:
            existing = supabase.rpc("get_active_voice_activity", {"user_id_input": user_id}).execute()
            if hasattr(existing, "data") and existing.data:
                return
            data = {
                "user_id": user_id,
                "username": username,
                "joined_at": now.isoformat(),
                "left_at": None,
                "duration_sec": 0
            }
            supabase.table("voice_activity").insert(data).execute()

        elif before.channel is not None and after.channel is None:
            records = supabase.rpc("get_active_voice_activity", {"user_id_input": user_id}).execute()
            if hasattr(records, "data") and records.data:
                joined_at_str = records.data[0].get("joined_at")
                joined_dt = datetime.fromisoformat(joined_at_str)
                duration = int((now - joined_dt).total_seconds())

                supabase.table("voice_activity").update({
                    "left_at": now.isoformat(),
                    "duration_sec": duration
                }).eq("id", records.data[0]["id"]).execute()
    except Exception as e:
        print(f"❌ Supabase 오류: {e}")


# ──────────────────────── [5] 환영 메시지 + 초대 추적 + 버튼 ────────────────────────
class WelcomeButton(discord.ui.View):
    def __init__(self, member, original_message):
        super().__init__(timeout=None)
        self.member = member
        self.original_message = original_message

    @discord.ui.button(label="🎈 이 멤버 환영하기!", style=discord.ButtonStyle.success)
    async def welcome_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        msg = random.choice([
            f"{interaction.user.mention} 님이 {self.member.mention} 님을 환영하며 춤을 춥니다! 🕺",
            f"{interaction.user.mention} 님이 {self.member.mention} 님에게 커피 한 잔~ ☕️",
            f"{interaction.user.mention} 님이 {self.member.mention} 님에게 환영 폭죽을 쾅! 🎆",
            f"{interaction.user.mention} 님이 {self.member.mention} 님에게 꽃다발을 건넸습니다! 💐",
            f"{interaction.user.mention} 님이 {self.member.mention} 님에게 따뜻한 악수를 전합니다! 🤝",
            f"{interaction.user.mention} 님이 {self.member.mention} 님을 환영하며 노래를 부릅니다! 🎤",
            f"{interaction.user.mention} 님이 {self.member.mention} 님에게 하이파이브! 🙌",
            f"{interaction.user.mention} 님이 {self.member.mention} 님을 위해 춤추는 곰을 소환했습니다! 🐻💃"
        ])

        gif = random.choice([
            "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
            "https://media.giphy.com/media/26ufdipQqU2lhNA4g/giphy.gif",
            "https://media.giphy.com/media/xT9IgG50Fb7Mi0prBC/giphy.gif",
            "https://media.giphy.com/media/5GoVLqeAOo6PK/giphy.gif",
            "https://media.giphy.com/media/3o7aD2saalBwwftBIY/giphy.gif",
            "https://media.giphy.com/media/111ebonMs90YLu/giphy.gif",
            "https://media.giphy.com/media/xT0xeJpnrWC4XWblEk/giphy.gif",
            "https://media.giphy.com/media/l0HlBo7eyXzSZkJri/giphy.gif",
            "https://media.giphy.com/media/3o7TKtnuHOHHUjR38Y/giphy.gif",
            "https://media.giphy.com/media/xUPGcguWZHRC2HyBRS/giphy.gif",
            "https://media.giphy.com/media/3o6Zt481isNVuQI1l6/giphy.gif",
            "https://media.giphy.com/media/3ohs7Ys8MLv7bRifGU/giphy.gif",
            "https://media.giphy.com/media/l4pTfx2qLszoacZRS/giphy.gif",
            "https://media.giphy.com/media/3oEjHP8ELRNNlnlLGM/giphy.gif",
            "https://media.giphy.com/media/3o6ZsZZ0iXyPr6iCWk/giphy.gif",
            "https://media.giphy.com/media/l3vR7WPE1h8aQhvzC/giphy.gif",
            "https://media.giphy.com/media/26AOsZgMufZnoJXLG/giphy.gif",
            "https://media.giphy.com/media/3oz8xLd9DJq2l2VFtu/giphy.gif",
            "https://media.giphy.com/media/3oz8xLd9DJq2l2VFtu/giphy.gif",
            "https://media.giphy.com/media/3oEduSbSGpGaRX2Vri/giphy.gif",
            "https://media.giphy.com/media/26gsqQxPQXHBiBEUU/giphy.gif",
            "https://media.giphy.com/media/l0MYyQ8PaoC0DfiK0/giphy.gif",
            "https://media.giphy.com/media/3o7TKuXju0u3dRFVMU/giphy.gif",
            "https://media.giphy.com/media/l0MYt5d4fvVXWfCXu/giphy.gif",
            "https://media.giphy.com/media/3o6ozuLELxY7ykWgSG/giphy.gif",
            "https://media.giphy.com/media/xT5LMHxhOfscxPfIfm/giphy.gif",
            "https://media.giphy.com/media/3o7aCSPqXE5C6T8tBC/giphy.gif",
            "https://media.giphy.com/media/3o7aD6PEzM2kx0Wn8c/giphy.gif",
            "https://media.giphy.com/media/3o7aD6SGtWx28WFSUE/giphy.gif",
            "https://media.giphy.com/media/xT0BKmtQGLbumr5RCM/giphy.gif",
            "https://media.giphy.com/media/3o6BRt4oFCc9H0M5lC/giphy.gif"
        ])

        embed = discord.Embed(description=msg, color=discord.Color.random())
        embed.set_image(url=gif)
        embed.set_footer(text="환영합니다 🎉")
        await interaction.followup.send(embed=embed)

@bot.event
async def on_member_join(member):
    guild = member.guild
    channel = discord.utils.get(guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if not channel:
        return

    new_invites = await guild.invites()
    old_invites = invites_cache.get(guild.id, {})
    invites_cache[guild.id] = {invite.code: invite for invite in new_invites}

    inviter = None
    for invite in new_invites:
        old = old_invites.get(invite.code)
        if old and invite.uses > old.uses:
            inviter = invite.inviter
            break

    joined_time = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    embed = discord.Embed(
        title="🎊 신입 멤버 출몰!",
        description=f"😎 {member.mention} 님이 입장하셨습니다!\n누가 먼저 환영할까요?",
        color=discord.Color.orange()
    )
    embed.set_image(url="https://raw.githubusercontent.com/Na-seunghyun/my-discord-bot/main/minion.gif")
    embed.set_footer(text="Gamer Welcome Time", icon_url=member.display_avatar.url)
    embed.add_field(name="입장 시간", value=joined_time, inline=True)
    embed.add_field(name="초대한 사람", value=inviter.mention if inviter else "알 수 없음", inline=True)

    msg = await channel.send(embed=embed)
    await msg.edit(view=WelcomeButton(member, msg))

@bot.event
async def on_member_remove(member):
    channel = discord.utils.get(member.guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if channel:
        embed = discord.Embed(
            title="👋 멤버 탈주!",
            description=f"{member.display_name} 님이 서버를 떠났습니다. 🥲",
            color=discord.Color.red()
        )
        embed.set_image(url="https://raw.githubusercontent.com/Na-seunghyun/my-discord-bot/main/sponge.gif")
        await channel.send(embed=embed)

# ──────────────────────── [6] 자동 PUBG ID 갱신 ────────────────────────
@tasks.loop(hours=1)
async def auto_update_valid_ids():
    for guild in bot.guilds:
        await update_valid_pubg_ids(guild)

async def update_valid_pubg_ids(guild):
    valid_members = []
    for member in guild.members:
        if member.bot:
            continue
        parts = (member.nick or member.name).strip().split("/")
        if len(parts) == 3 and nickname_pattern.fullmatch("/".join(p.strip() for p in parts)):
            name, game_id, _ = [p.strip() for p in parts]
            is_guest = "(게스트)" in (member.nick or member.name)
            valid_members.append({
                "name": name,
                "game_id": game_id,
                "discord_id": member.id,
                "is_guest": is_guest
            })
    with open(VALID_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(valid_members, f, ensure_ascii=False, indent=2)
    print(f"✅ valid_pubg_ids.json 갱신 완료 ({len(valid_members)}명)")

# ──────────────────────── [7] 도움말 명령어 ────────────────────────
@tree.command(name="도움말", description="명령어 및 기능 소개", guild=discord.Object(id=GUILD_ID))
async def 도움말(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 오덕봇 도움말",
        description="서버에서 사용할 수 있는 주요 기능입니다.",
        color=discord.Color.blue()
    )
    embed.add_field(name="🎯 /전적 [닉네임]", value="PUBG 전적을 조회합니다.", inline=False)
    embed.add_field(name="💰 /돈줘", value="하루에 한 번 5000원 지급", inline=False)
    embed.add_field(name="📢 /경고확인", value="욕설 등 경고 받은 횟수를 확인", inline=False)
    embed.add_field(name="🧪 /검사", value="닉네임 형식 검사 (이름/ID/년도)", inline=False)
    embed.add_field(name="🎊 환영 버튼", value="신규 입장자에게 환영 메세지 보내기", inline=False)
    embed.set_footer(text="제작: 토끼록끼 | 문의는 DM!")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ──────────────────────── 봇 실행 ────────────────────────
keep_alive()
bot.run(DISCORD_TOKEN)

