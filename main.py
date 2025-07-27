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
import json
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
intents.guilds = True
intents.voice_states = True
intents.messages = True
intents.message_content = True
intents.presences = True  # 유저 활동 상태 감지 (PUBG 감지에 필수)

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
nickname_pattern = re.compile(r"^[가-힣a-zA-Z0-9_()\-\s]+/[a-zA-Z0-9_-]+/\d{2}$")
auto_disconnect_tasks = {}
voice_join_times = {}  # user_id: join_time
dm_sent_users = set()
waiting_room_message_cache = {}

all_empty_since = None
notified_after_empty = False
streaming_members = set()
invites_cache = {}




WARNINGS_FILE = "warnings.json"
BADWORDS_FILE = "badwords.txt"


import os
import json
import random

# 📁 파일 경로
INVESTMENT_FILE = "investments.json"
STOCKS_FILE = "stocks.json"

# ✅ 최대 종목 수
MAX_STOCKS = 30

# ✅ 종목 이름 생성용 한글 조합 확장
KOREAN_PARTS = [
    # 감성 단어
    "오로라", "크림", "달빛", "스노우", "블루", "버터", "하늘", "라레", "소울", "루나",
    "피치", "아보카도", "우주", "몽길", "카카오", "마카론", "구름", "퍽키", "선셋", "무지개",
    "초코", "멜로디", "코튼", "허니", "미넛", "밤하늘", "브리즈", "해피", "그레이", "플레인",
    "민트", "라일락", "달콤", "보라빛", "노을", "자몽", "바닐라", "시나몬", "비건", "마시멜로",
    "반딧불", "딸기", "아이스", "열대어", "초여름", "봄비", "해질녘", "모카", "카페", "체리"
]

CATEGORY_PARTS = [
    # 산업/분야
    "랩", "소프트", "테크", "스튜디오", "웍스", "마켓", "네트웍스", "그룹", "다이나믹스", "클라우드",
    "시스템", "바이브스", "캐피탈", "푸드", "모터스", "헬스", "솔루션", "디지털", "미디어", "엔진",
    "센터", "팩토리", "파이낸스", "이노베이션", "컨설팅", "링크", "네이션", "컴퍼니", "벤처스", "코퍼레이션",
    "랩스", "테크놀로지", "마이데이터", "핀테크", "AI랩", "플랫폼", "파트너스", "트레이딩", "이커머스", "에듀",
    "에너지", "바이오텍", "헬스케어", "디자인", "제약", "자동차", "항공", "우주", "로봇", "반도체",
    "스포츠", "패션", "음악", "출판", "게임즈", "VR", "AR", "모바일", "광고", "광학",
    "생명과학", "환경", "농업", "식품", "금융", "물류", "유통", "부동산", "산업", "제조",
    "기술", "창업", "혁신", "정보", "보안", "네트워크", "AI", "블록체인", "데이터", "연구소",
    "협동조합", "재단", "협회", "클럽", "매니지먼트", "에이전시", "서비스", "하우스", "셀", "엔터프라이즈"
]

# ✅ 래더망 종목 이름 생성
used_names = set()
def generate_random_stock_name():
    for _ in range(100):
        name = f"{random.choice(KOREAN_PARTS)}{random.choice(CATEGORY_PARTS)}"
        if name not in used_names:
            used_names.add(name)
            return name
    return None

# ✅ 종목 1개 생성
def create_new_stock(stocks: dict) -> str:
    for _ in range(50):  # 중복 회피 최대 50번 시도
        name = generate_random_stock_name()
        if name and name not in stocks:
            stocks[name] = {
                "price": random.randint(500, 3000),
                "change": 0
            }
            return name
    return None  # 실패 시

# ✅ 초기화 또는 부족 시 종목 생성
def ensure_stocks_filled():
    stocks = {}
    if os.path.exists(STOCKS_FILE):
        with open(STOCKS_FILE, "r", encoding="utf-8") as f:
            stocks = json.load(f)

    while len(stocks) < MAX_STOCKS:
        create_new_stock(stocks)

    with open(STOCKS_FILE, "w", encoding="utf-8") as f:
        json.dump(stocks, f, indent=2)

# ✅ 종목 등록 로드하기
def load_stocks():
    ensure_stocks_filled()
    with open(STOCKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ✅ 종목 저장
def save_stocks(data):
    with open(STOCKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ✅ 투자 내역 로드하기
def load_investments():
    if not os.path.exists(INVESTMENT_FILE):
        return []
    with open(INVESTMENT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ✅ 투자 내역 저장
def save_investments(data):
    with open(INVESTMENT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def reset_investments(user_id: str):
    investments = load_investments()
    updated = [inv for inv in investments if inv["user_id"] != user_id]
    save_investments(updated)


async def fetch_user_safe(user_id):
    try:
        return await bot.fetch_user(int(user_id))
    except Exception:
        return None


async def send_to_oduk_channel(message: str):
    channel = discord.utils.get(bot.get_all_channels(), name="오덕도박장")
    if channel:
        await channel.send(message)









# 🎲 도박 기능용 상수 및 유틸
BALANCE_FILE = "balance.json"

def ensure_balance_file():
    if not os.path.exists(BALANCE_FILE):
        with open(BALANCE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

def load_balances():
    ensure_balance_file()
    with open(BALANCE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_balances(data):
    # 1,000명 이상 시 가장 오래된 데이터 제거 (최대 1000명 유지)
    if len(data) > 1000:
        data = dict(sorted(data.items(), key=lambda x: x[1].get("last_updated", ""), reverse=True)[:1000])
    with open(BALANCE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def get_balance(user_id):
    data = load_balances()
    return data.get(str(user_id), {}).get("amount", 0)

def set_balance(user_id, amount):
    data = load_balances()
    uid = str(user_id)
    user_data = data.get(uid, {})
    
    user_data["amount"] = amount
    user_data["last_updated"] = datetime.utcnow().isoformat()
    
    # 도박 승/패 기록 유지
    user_data.setdefault("gamble", {"win": 0, "lose": 0})
    
    data[uid] = user_data
    save_balances(data)

def record_gamble_result(user_id, success: bool):
    data = load_balances()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"amount": 0, "last_updated": datetime.utcnow().isoformat()}
    
    data[uid].setdefault("gamble", {"win": 0, "lose": 0})
    if success:
        data[uid]["gamble"]["win"] += 1
    else:
        data[uid]["gamble"]["lose"] += 1

    save_balances(data)

def get_gamble_title(user_id: str, success: bool) -> str:
    data = load_balances().get(str(user_id), {})
    stats = data.get("gamble", {})
    win = stats.get("win", 0)
    lose = stats.get("lose", 0)
    total = win + lose
    rate = win / total if total > 0 else 0

    success_titles = []
    failure_titles = []
    winrate_titles = []

    # 🎯 A. 성공 수 기반 칭호
    if win >= 500:
        success_titles.append("👑 전설의 갬블러")
    elif win >= 300:
        success_titles.append("🥇 도박왕")
    elif win >= 200:
        success_titles.append("🥈 대박 기운")
    elif win >= 100:
        success_titles.append("🥉 강운 보유자")
    elif win >= 50:
        success_titles.append("🌟 행운의 손")
    elif win >= 20:
        success_titles.append("🎯 슬슬 감이 온다")
    elif win >= 10:
        success_titles.append("🔰 초심자 치고 잘함")

    # 💀 B. 실패 수 기반 칭호
    if lose >= 500:
        failure_titles.append("💀 도박중독자")
    elif lose >= 300:
        failure_titles.append("⚰️ 파산 직전")
    elif lose >= 200:
        failure_titles.append("☠️ 불운의 화신")
    elif lose >= 100:
        failure_titles.append("💔 눈물의 도박사")
    elif lose >= 50:
        failure_titles.append("😵 현타 온다")
    elif lose >= 20:
        failure_titles.append("😓 안 풀리는 하루")

    # 🧠 C. 승률 기반 (50회 이상)
    if total >= 50:
        if rate >= 0.85:
            winrate_titles.append("🍀 신의 손")
        elif rate >= 0.70:
            winrate_titles.append("🧠 전략가")
        elif rate <= 0.20:
            winrate_titles.append("🐌 패배 장인")
        elif rate <= 0.35:
            winrate_titles.append("🪦 계속 해도 괜찮은가요?")

    # 🗂️ D. 누적 시도 칭호 (추가)
    if total >= 1000:
        winrate_titles.append("🕹️ 역사적인 갬블러")
    elif total >= 500:
        winrate_titles.append("📜 기록을 남긴 자")
    elif total >= 200:
        winrate_titles.append("🧾 꽤 해본 사람")
    elif total >= 100:
        winrate_titles.append("🔖 갬블러 생활 중")

    # ✅ 반환: 성공 or 실패 칭호 + 승률 칭호 (조건 충족 시)
    if success:
        return " / ".join(success_titles + winrate_titles) or "🔸 무명 도전자"
    else:
        return " / ".join(failure_titles + winrate_titles) or "🔸 무명 도전자"





def add_balance(user_id, amount):
    current = get_balance(user_id)
    set_balance(user_id, current + amount)

@tasks.loop(hours=1)
async def auto_update_valid_ids():
    for guild in bot.guilds:
        await update_valid_pubg_ids(guild)



ODUK_POOL_FILE = "oduk_pool.json"

def load_oduk_pool():
    default_data = {
        "amount": 0,
        "last_lotto_date": "",
        "last_winner": ""
    }

    if not os.path.exists(ODUK_POOL_FILE):
        # ✅ 초기값 저장 후 반환
        with open(ODUK_POOL_FILE, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=2)
        return default_data

    with open(ODUK_POOL_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {}

    for key in default_data:
        data.setdefault(key, default_data[key])

    return data





def save_oduk_pool(data):
    with open(ODUK_POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def add_oduk_pool(amount: int):
    global oduk_pool_cache  # 전역 캐시를 수정할 거면 꼭 필요함

    if not oduk_pool_cache:
        # 처음 호출된 경우, 캐시를 생성하면서 초기화
        oduk_pool_cache = {
            "amount": 0,
            "last_lotto_date": "",
            "last_winner": ""
        }

    if "amount" not in oduk_pool_cache:
        oduk_pool_cache["amount"] = 0

    oduk_pool_cache["amount"] += amount
    save_oduk_pool(oduk_pool_cache)



def get_oduk_pool_amount() -> int:
    return oduk_pool_cache.get("amount", 0)


oduk_pool_cache = load_oduk_pool()

if oduk_pool_cache is None:
    print("⚠️ 오덕 잔고 파일이 아직 없습니다. 처음 사용할 때 생성됩니다.")
    oduk_pool_cache = {}  # or 기본값 dict
else:
    print(f"🔄 오덕 캐시 로딩됨: {oduk_pool_cache}")





# ✅ 자산 구간별 유지비율 설정 (필요시 수정)
MAINTENANCE_TIERS = [
    (500_0000, 0.15),   #  오백만 원 이상 → 10%
    (1000_0000, 0.50),   # 천 만 원 이상 → 25%
    (3000_0000, 0.70),   # 삼천 만 원 이상 → 50%
]

# 예시로 채널 ID 설정 (실제 사용 중인 ID로 교체하세요)
DOKDO_CHANNEL_ID = 1394331814642057418  # 오덕도박장


async def apply_maintenance_costs(bot):
    balances = load_balances()
    now = datetime.now(KST).isoformat()
    changed_users = []

    for user_id, info in balances.items():
        amount = info.get("amount", 0)

        if amount < 10_000_000:
            continue  # 1억 미만은 감가 대상 아님

        # ✅ MAINTENANCE_TIERS 기준 감가율 결정
        rate = 0
        for threshold, r in MAINTENANCE_TIERS:
            if amount >= threshold:
                rate = r
                break

        deduction = int(amount * rate)
        new_amount = amount - deduction

        # ✅ 최소 1억 보장
        if new_amount < 10_000_000:
            deduction = amount - 10_000_000
            new_amount = 10_000_000

        if deduction > 0:
            balances[user_id]["amount"] = new_amount
            balances[user_id]["last_updated"] = now
            changed_users.append((user_id, amount, new_amount))
            print(f"💸 유지비 차감: {user_id} → {deduction:,}원")

    save_balances(balances)

    # ✅ 오덕도박장 채널에 안내 메시지 전송
    if changed_users:
        channel = bot.get_channel(DOKDO_CHANNEL_ID)
        if channel:
            msg_lines = ["💸 **자산 유지비 감가 정산 결과**"]
            for uid, before, after in changed_users:
                member = await fetch_user_safe(uid)
                name = member.display_name if member else f"ID:{uid}"
                msg_lines.append(f"• {name} → **{before:,}원 → {after:,}원**")
            msg_lines.append("\n📉 자산이 오백 만 원 이상일 경우 6시간 마다 감가가 적용됩니다.")
            await channel.send("\n".join(msg_lines))





@tasks.loop(hours=6)
async def auto_apply_maintenance():
    print("🕓 자산 유지비 정산 시작")
    await apply_maintenance_costs(bot)     # ✅ await + bot 전달
    await apply_bank_depreciation(bot)     # ✅ 비동기 메시지 포함
    print("✅ 자산 유지비 정산 완료")





async def decay_oduk_pool(bot):  # ✅ 인자 추가
    global oduk_pool_cache

    current_amount = oduk_pool_cache.get("amount", 0)
    minimum_amount = 1_000_000  # 백만 원 보장
    decay_rate = 0.50  # 50%

    if current_amount > minimum_amount:
        excess = current_amount - minimum_amount
        cut = int(excess * decay_rate)
        new_amount = current_amount - cut

        oduk_pool_cache["amount"] = new_amount
        save_oduk_pool(oduk_pool_cache)
        print(f"📉 오덕로또 상금 감가: {current_amount:,} → {new_amount:,}")

        # ✅ 알림 전송
        channel = bot.get_channel(DOKDO_CHANNEL_ID)
        if channel:
            await channel.send(
                f"📉 **오덕로또 상금 감가 적용**\n"
                f"💰 기존 상금: **{current_amount:,}원** → 현재 상금: **{new_amount:,}원**\n"
                f"🧾 **100만 원 초과분의 50%**가 감가되었으며, 최소 **100만 원**은 보장됩니다.\n"
                f"🎟️ `/오덕로또참여`로 오늘의 행운에 도전해보세요!"
            )
    else:
        print("✅ 오덕로또 상금이 100만 원 이하라 감가되지 않음")


@tasks.loop(hours=6)
async def auto_decay_oduk_pool():
    print("🕓 오덕로또 감가 시작")
    await decay_oduk_pool(bot)
    print("✅ 오덕로또 감가 완료")

@auto_decay_oduk_pool.before_loop
async def before_auto_decay():
    print("🕓 봇 시작 후 첫 감가까지 6시간 대기...")
    await asyncio.sleep(6 * 3600)  # 6시간 대기














WELCOME_CHANNEL_NAME = "자유채팅방"  # 자유롭게 바꿔도 됨



# 욕설 리스트 정규식 패턴 로드 함수
def load_badwords_regex(file_path=BADWORDS_FILE):
    regex_patterns = []
    if not os.path.exists(file_path):
        print(f"⚠️ 경고: {file_path} 파일이 없습니다.")
        return regex_patterns
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            word = line.strip().lower()
            if not word:
                continue
            # 글자 사이 공백이나 특수문자 무시하는 패턴
            pattern = ".*?".join([re.escape(ch) for ch in word])
            regex_patterns.append(re.compile(pattern, re.IGNORECASE))
    return regex_patterns

# ✅ 링크 제거 함수
def remove_urls(text: str):
    return re.sub(r"https?://[^\s]+", "", text)

# ✅ visible text만 필터링에 사용
def extract_visible_text(message: discord.Message) -> str:
    return remove_urls(message.content or "")
    
# ✅ 필터링 로직 (URL 제거 후 검사)
def filter_message(text: str):
    for pattern in BADWORD_PATTERNS:
        if pattern.search(text):
            return True
    return False

# ✅ *** 마스킹 함수도 URL 제거 적용
def censor_badwords_regex(text, badword_patterns):
    text = remove_urls(text)
    for pattern in badword_patterns:
        text = pattern.sub("***", text)
    return text

BADWORD_PATTERNS = load_badwords_regex()

# 경고 데이터 불러오기
if os.path.exists(WARNINGS_FILE):
    with open(WARNINGS_FILE, "r", encoding="utf-8") as f:
        warnings = json.load(f)
else:
    warnings = {}

def save_warnings():
    with open(WARNINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(warnings, f, indent=4)



@bot.event
async def on_member_update(before, after):
    if before.nick != after.nick:
        print(f"🔄 닉네임 변경 감지: {before.display_name} → {after.display_name}")
        await update_valid_pubg_ids(after.guild)

# ✅ on_message 핸들러
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if not isinstance(message.channel, discord.TextChannel):
        return

    visible_text = extract_visible_text(message)  # ⛔ 링크 제거된 본문만 필터링
    lowered_text = visible_text.lower()

    if filter_message(lowered_text):
        censored = censor_badwords_regex(message.content, BADWORD_PATTERNS)
        try:
            await message.delete()
        except Exception as e:
            print(f"❌ 메시지 삭제 실패: {e}")

        embed = discord.Embed(
            title="💬 욕설 필터링 안내",
            description=f"{message.author.mention} 님이 작성한 메시지에 욕설이 포함되어 필터링 되었습니다.\n\n"
                        f"**필터링된 메시지:**\n{censored}",
            color=0xFFD700
        )
        embed.set_footer(text="💡 오덕봇은 욕설은 자동으로 걸러주는 평화주의자입니다.")
        await message.channel.send(embed=embed)

        user_id = str(message.author.id)
        warnings[user_id] = warnings.get(user_id, 0) + 1
        save_warnings()

    await bot.process_commands(message)




# 경고 확인 슬래시 명령어
@tree.command(name="경고확인", description="누가 몇 번 경고받았는지 확인합니다", guild=discord.Object(id=GUILD_ID))
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

    result = "\n".join(report)
    await interaction.response.send_message(f"📄 경고 목록:\n{result}")

# 경고 초기화 슬래시 명령어 (서버 관리자 or 채널관리자 역할)
@tree.command(name="경고초기화", description="특정 유저의 경고 횟수를 0으로 초기화합니다 (관리자 전용)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="경고를 초기화할 유저를 선택하세요")
async def reset_warning(interaction: discord.Interaction, user: discord.Member):
    member = interaction.user
    has_admin = member.guild_permissions.administrator
    has_channel_admin_role = discord.utils.get(member.roles, name="채널관리자") is not None

    if not (has_admin or has_channel_admin_role):
        await interaction.response.send_message("❌ 관리자만 사용할 수 있는 명령어입니다.", ephemeral=True)
        return

    user_id = str(user.id)
    if user_id in warnings:
        warnings[user_id] = 0
        save_warnings()
        await interaction.response.send_message(f"✅ {user.display_name}님의 경고 횟수가 초기화되었습니다.")
    else:
        await interaction.response.send_message(f"ℹ️ {user.display_name}님은 현재 경고 기록이 없습니다.")









# 🎈 환영 버튼 구성
import random
import discord

class WelcomeButton(discord.ui.View):
    def __init__(self, member, original_message):
        super().__init__(timeout=None)
        self.member = member
        self.original_message = original_message

    @discord.ui.button(label="🎈 이 멤버 환영하기!", style=discord.ButtonStyle.success)
    async def welcome_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        messages = [
            f"🎉 {interaction.user.mention} 님이 {self.member.mention} 님에게 환영 폭죽을 터뜨렸어요!",
            f"🕺 {interaction.user.mention} 님과 {self.member.mention} 님이 환영 댄스를 춥니다!",
            f"🎤 {interaction.user.mention} 님이 {self.member.mention} 님에게 환영 노래를 불러줍니다!",
            f"🍪 {interaction.user.mention} 님이 {self.member.mention} 님에게 환영 쿠키를 건넸어요!",
            f"🌟 {interaction.user.mention} 님이 {self.member.mention} 님을 위한 별빛을 뿌렸습니다!",
            f"🚀 {interaction.user.mention} 님이 {self.member.mention} 님을 우주로 환영합니다!",
            f"🪄 {interaction.user.mention} 님이 {self.member.mention} 님에게 환영 마법을 부렸어요!",
            f"📸 {interaction.user.mention} 님이 {self.member.mention} 님과 환영 셀카 찰칵!",
            f"🍔 {interaction.user.mention} 님이 {self.member.mention} 님에게 버거 한 입!",
            f"💃 {interaction.user.mention} 님이 {self.member.mention} 님을 위해 춤을 춰요!",
            f"🎈 {interaction.user.mention} 님이 {self.member.mention} 님을 향해 풍선을 날렸어요!",
            f"🔥 {interaction.user.mention} 님과 {self.member.mention} 님이 불꽃처럼 반가워요!",
            f"⚡ {interaction.user.mention} 님이 {self.member.mention} 님을 향해 전기처럼 빠르게 환영!",
            f"🧁 {interaction.user.mention} 님이 {self.member.mention} 님에게 환영 컵케이크 선물!",
            f"🧡 {interaction.user.mention} 님이 {self.member.mention} 님에게 따뜻한 마음을 전했어요!",
            f"🎶 {interaction.user.mention} 님이 {self.member.mention} 님을 위한 환영 멜로디를 틀었어요!",
            f"🍕 {interaction.user.mention} 님이 {self.member.mention} 님에게 피자를 한 조각!",
            f"🪅 {interaction.user.mention} 님이 {self.member.mention} 님 환영 파티를 열었어요!",
            f"🎮 {interaction.user.mention} 님이 {self.member.mention} 님과 게임으로 환영을 표현했어요!",
            f"☀️ {interaction.user.mention} 님이 {self.member.mention} 님에게 햇살 같은 환영을 보냅니다!"
        ]

        gifs = [
            "https://media.giphy.com/media/3o7aD2saalBwwftBIY/giphy.gif",
            "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
            "https://media.giphy.com/media/26ufdipQqU2lhNA4g/giphy.gif",
            "https://media.giphy.com/media/5GoVLqeAOo6PK/giphy.gif",
            "https://media.giphy.com/media/3o7TKtnuHOHHUjR38Y/giphy.gif",
            "https://media.giphy.com/media/xT9IgG50Fb7Mi0prBC/giphy.gif",
            "https://media.giphy.com/media/3oEjHP8ELRNNlnlLGM/giphy.gif",
            "https://media.giphy.com/media/l4pTfx2qLszoacZRS/giphy.gif",
            "https://media.giphy.com/media/3o6Zt6ML6BklcajjsA/giphy.gif",
            "https://media.giphy.com/media/3oEduSbSGpGaRX2Vri/giphy.gif",
            "https://media.giphy.com/media/3oz8xLd9DJq2l2VFtu/giphy.gif",
            "https://media.giphy.com/media/3o7aD6SGtWx28WFSUE/giphy.gif",
            "https://media.giphy.com/media/l0MYyQ8PaoC0DfiK0/giphy.gif",
            "https://media.giphy.com/media/l0MYB8Ory7Hqefo9a/giphy.gif",
            "https://media.giphy.com/media/xT0xeJpnrWC4XWblEk/giphy.gif",
            "https://media.giphy.com/media/26gsqQxPQXHBiBEUU/giphy.gif",
            "https://media.giphy.com/media/l4HlBo7eyXzSZkJri/giphy.gif",
            "https://media.giphy.com/media/3o6Zt481isNVuQI1l6/giphy.gif",
            "https://media.giphy.com/media/xT5LMHxhOfscxPfIfm/giphy.gif",
            "https://media.giphy.com/media/l41lFw057lAJQMwg0/giphy.gif"
        ]

        selected_message = random.choice(messages)
        selected_gif = random.choice(gifs)

        embed = discord.Embed(
            description=selected_message,
            color=discord.Color.random()
        )
        embed.set_image(url=selected_gif)
        embed.set_footer(text="🧸 with_토끼록끼 | 따뜻한 환영을 전해요!")

        await interaction.followup.send(embed=embed, ephemeral=False)



INVITE_CACHE_FILE = "invites_cache.json"
invites_cache = {}

def load_invite_cache():
    global invites_cache
    if os.path.exists(INVITE_CACHE_FILE):
        with open(INVITE_CACHE_FILE, "r", encoding="utf-8") as f:
            invites_cache = json.load(f)
        print(f"📂 [DEBUG] invites_cache.json 내용:\n{json.dumps(invites_cache, indent=2, ensure_ascii=False)}")
    else:
        invites_cache = {}
        print("⚠️ invites_cache.json 파일이 존재하지 않음 (처음 실행이거나 삭제됨)")


def save_invite_cache():
    with open(INVITE_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(invites_cache, f, ensure_ascii=False, indent=2)
    print(f"💾 [DEBUG] invites_cache.json 저장됨:\n{json.dumps(invites_cache, indent=2, ensure_ascii=False)}")






@bot.event
async def on_member_join(member):
    global invites_cache  # ✅ 맨 위에서 선언해줘야 안전

    guild = member.guild
    channel = discord.utils.get(guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if not channel:
        return

    # ✅ 이전 invite 정보 확보 먼저
    old_invites = invites_cache.get(str(guild.id), {})

    # ✅ fallback: invites_cache.json 파일에서 불러오기 (초기 실행 대비)
    if not old_invites:
        try:
            with open("invites_cache.json", "r", encoding="utf-8") as f:
                file_cache = json.load(f)
                old_invites = file_cache.get(str(guild.id), {})
                print("📂 invites_cache.json에서 캐시 불러옴")
        except Exception as e:
            print(f"❌ invites_cache.json 로딩 실패: {e}")
            old_invites = {}

    # ✅ 초대 링크 반영을 기다리기 위해 약간의 대기 추가
    await asyncio.sleep(2)

    # ✅ 현재 초대 링크 목록 가져오기
    try:
        current_invites = await guild.invites()
    except Exception as e:
        print(f"❌ 현재 초대 링크 불러오기 실패: {e}")
        return

    # ✅ 누가 초대한 것인지 가장 사용량이 증가한 초대 코드로 추정
    inviter = None
    best_match = None
    max_diff = 0

    for invite in current_invites:
        code = invite.code
        old_uses = old_invites.get(code, {}).get("uses", 0)
        diff = invite.uses - old_uses
        if diff > max_diff:
            max_diff = diff
            best_match = invite

    # ✅ 가장 유력한 초대 코드가 1회만 증가한 경우에만 초대자 확정
    if best_match and max_diff == 1:
        inviter_id = best_match.inviter.id if best_match.inviter else old_invites.get(best_match.code, {}).get("inviter_id")
        if inviter_id:
            inviter = guild.get_member(inviter_id)

    # ✅ 현재 초대 상태를 실시간으로 캐시에 반영
    invites_cache[str(guild.id)] = {
        invite.code: {
            "uses": invite.uses,
            "inviter_id": invite.inviter.id if invite.inviter else None
        }
        for invite in current_invites
    }
    save_invite_cache()

    # ✅ 입장 시간 계산
    KST = timezone(timedelta(hours=9))
    joined_dt = datetime.now(tz=KST)
    timestamp = int(joined_dt.timestamp())
    formatted_time = joined_dt.strftime("%Y-%m-%d %H:%M:%S")
    relative_time = f"<t:{timestamp}:R>"  # 예: 1분 전

    # ✅ 환영 임베드 생성
    embed = discord.Embed(
        title="🎊 신입 멤버 출몰!",
        description=f"😎 {member.mention} 님이 **화려하게 입장!** 🎉",
        color=discord.Color.orange()
    )
    embed.set_image(url="https://raw.githubusercontent.com/Na-seunghyun/my-discord-bot/main/minion.gif")
    embed.set_footer(text="누구보다 빠르게 남들과는 다르게!", icon_url=member.display_avatar.url)

    if inviter:
        embed.add_field(name="초대한 사람", value=f"{inviter.mention} (`{inviter.display_name}`)", inline=True)
    else:
        embed.add_field(name="초대한 사람", value="알 수 없음", inline=True)

    embed.add_field(name="입장 시간", value=f"{formatted_time} ({relative_time})", inline=True)

    # ✅ 메시지 전송 및 버튼 추가
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





from discord.ext import tasks

@tasks.loop(minutes=1)  # 주기적으로 초대 캐시 갱신
async def auto_refresh_invites():
    global invites_cache
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            invites_cache[str(guild.id)] = {
                invite.code: {
                    "uses": invite.uses,
                    "inviter_id": invite.inviter.id if invite.inviter else None
                }
                for invite in invites
            }
        except Exception as e:
            print(f"❌ 주기적 초대 캐시 실패 ({guild.name}): {e}")

    try:
        with open("invites_cache.json", "w", encoding="utf-8") as f:
            json.dump(invites_cache, f, ensure_ascii=False, indent=2)
        print("💾 초대 캐시 invites_cache.json 주기적 저장 완료!")
    except Exception as e:
        print(f"❌ 초대 캐시 저장 실패: {e}")












async def safe_send_message(channel, content, max_retries=5, delay=1):
    for attempt in range(max_retries):
        try:
            msg = await channel.send(content)
            print(f"✅ 메시지 전송 성공 (ID: {msg.id})")
            return True
        except Exception as e:
            print(f"⚠️ 메시지 전송 실패 {attempt + 1}회차: {e}")
            await asyncio.sleep(delay)
    print("❌ 메시지 전송 완전 실패")
    return False


# 자동 퇴장 로직
auto_disconnect_tasks = {}
auto_kicked_members = {}  # 자동퇴장 중 멤버 ID 저장

async def auto_disconnect_after_timeout(member, voice_channel, text_channel):
    try:
        await asyncio.sleep(20 * 60)  # 또는 테스트용 2초
        if member.voice and member.voice.channel == voice_channel:
            auto_kicked_members[member.id] = True  # 자동퇴장 시작 플래그
            await member.move_to(None)
            await asyncio.sleep(0.3)  # 안전한 딜레이

            # 메시지 보내기
            if text_channel is None:
                text_channel = discord.utils.get(member.guild.text_channels, name="봇알림")

            if text_channel:
                await text_channel.send(f"⏰ {member.mention}님이 '밥좀묵겠습니다' 채널에 20분 이상 머물러 토끼록끼가 후라이팬으로 강력하게 후려쳐 만리장성으로 날려버렸습니다.")
            print(f"🚪 {member.display_name}님 자동 퇴장 완료")

            auto_kicked_members.pop(member.id, None)

    except asyncio.CancelledError:
        print(f"⏹️ {member.display_name}님 타이머 취소됨")
    finally:
        auto_disconnect_tasks.pop(member.id, None)












@bot.event
async def on_voice_state_update(member, before, after):
    global all_empty_since, notified_after_empty  # ✅ 전역 변수 선언
    if member.bot:
        return

    bap_channel = discord.utils.get(member.guild.voice_channels, name="밥좀묵겠습니다")
    text_channel = discord.utils.get(member.guild.text_channels, name="봇알림")

    # 입장 시
    if after.channel == bap_channel and before.channel != bap_channel:
        if member.id in auto_disconnect_tasks:
            auto_disconnect_tasks[member.id].cancel()
            auto_disconnect_tasks.pop(member.id, None)

        if member.id not in dm_sent_users:
            try:
                await member.send(f"🍚 {member.display_name}님, '밥좀묵겠습니다' 채널에 입장하셨습니다. 20분 후 자동 퇴장됩니다.")
                dm_sent_users.add(member.id)
            except Exception as e:
                print(f"DM 전송 실패: {member.display_name} - {e}")

        task = asyncio.create_task(auto_disconnect_after_timeout(member, bap_channel, text_channel))
        auto_disconnect_tasks[member.id] = task
        print(f"⏳ {member.display_name}님 타이머 시작됨")

    # 퇴장 시
    elif before.channel == bap_channel and after.channel != bap_channel:
        if auto_kicked_members.get(member.id):
            # 자동퇴장으로 발생한 퇴장, 타이머 취소하지 않고 플래그만 제거
            auto_kicked_members.pop(member.id, None)
            print(f"🚪 {member.display_name}님 자동퇴장 이벤트 감지 - 타이머 유지")
        else:
            # 사람이 직접 나간 경우에만 타이머 취소
            task = auto_disconnect_tasks.get(member.id)
            if task and not task.done():
                task.cancel()
                auto_disconnect_tasks.pop(member.id, None)
                print(f"❌ {member.display_name}님 직접 퇴장 → 타이머 취소됨")

        dm_sent_users.discard(member.id)





    # 대기방 입장 메시지 중복 방지 캐시
    now_utc = datetime.utcnow()

    if (before.channel != after.channel) and (after.channel is not None):
        if after.channel.name == "대기방":
            last_sent = waiting_room_message_cache.get(member.id)
            if not last_sent or (now_utc - last_sent) > timedelta(seconds=30):
                text_channel = discord.utils.get(member.guild.text_channels, name="봇알림")
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
            text_channel = discord.utils.get(guild.text_channels, name="봇알림")
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
            text_channel = discord.utils.get(member.guild.text_channels, name="봇알림")
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
        text_channel = discord.utils.get(guild.text_channels, name="봇알림")
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

_cached_season_id = None
_cached_season_time = None

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
    global _cached_season_id, _cached_season_time

    now = datetime.utcnow()
    if _cached_season_id and _cached_season_time and (now - _cached_season_time) < timedelta(hours=1):
        return _cached_season_id

    url = f"https://api.pubg.com/shards/{PLATFORM}/seasons"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    for season in data["data"]:
        if season["attributes"]["isCurrentSeason"]:
            season_id = season["id"]
            _cached_season_id = season_id
            _cached_season_time = now
            print(f"🔁 시즌 ID 새로 로드됨: {season_id}")
            return season_id

def get_player_stats(player_id, season_id):
    url = f"https://api.pubg.com/shards/{PLATFORM}/players/{player_id}/seasons/{season_id}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

import time

recent_saves = {}

def save_player_stats_to_file(nickname, squad_metrics, ranked_stats, stats=None, discord_id=None, source="기본"):
    key = f"{nickname}_{discord_id}"
    now = time.time()

    if key in recent_saves and now - recent_saves[key] < 30:
        print(f"⏹ 중복 저장 방지: {nickname} ({source})")
        return
    recent_saves[key] = now

    season_id = get_season_id()
    data_to_save = {
        "nickname": nickname,
        "discord_id": str(discord_id),
        "timestamp": datetime.now().isoformat()
    }

    if stats:
        rounds_played = stats["data"]["attributes"]["gameModeStats"].get("squad", {}).get("roundsPlayed", 0)
        kills = stats["data"]["attributes"]["gameModeStats"].get("squad", {}).get("kills", 0)
    else:
        rounds_played = 0
        kills = 0

    if squad_metrics:
        avg_damage, kd, win_rate = squad_metrics
        data_to_save["squad"] = {
            "avg_damage": avg_damage,
            "kd": kd,
            "win_rate": win_rate,
            "rounds_played": rounds_played,
            "kills": kills
        }
    else:
        data_to_save["squad"] = {
            "avg_damage": 0,
            "kd": 0,
            "win_rate": 0,
            "rounds_played": rounds_played,
            "kills": kills
        }

    if ranked_stats and "data" in ranked_stats:
        ranked_modes = ranked_stats["data"]["attributes"]["rankedGameModeStats"]
        squad_rank = ranked_modes.get("squad")
        if squad_rank:
            data_to_save["ranked"] = {
                "tier": squad_rank.get("currentTier", {}).get("tier", "Unranked"),
                "subTier": squad_rank.get("currentTier", {}).get("subTier", ""),
                "points": squad_rank.get("currentRankPoint", 0)
            }

    leaderboard_path = "season_leaderboard.json"
    try:
        if os.path.exists(leaderboard_path):
            with open(leaderboard_path, "r", encoding="utf-8") as f:
                file_data = json.load(f)
                stored_season_id = file_data.get("season_id")
                leaderboard = file_data.get("players", [])
        else:
            stored_season_id = None
            leaderboard = []

        if stored_season_id != season_id:
            leaderboard = []

        leaderboard = [
            p for p in leaderboard
            if p.get("nickname") != nickname and p.get("discord_id") != str(discord_id)
        ]
        leaderboard.append(data_to_save)

        with open(leaderboard_path, "w", encoding="utf-8") as f:
            json.dump({"season_id": season_id, "players": leaderboard}, f, ensure_ascii=False, indent=2)
        print(f"✅ 저장 성공 ({source}): {nickname}")
    except Exception as e:
        print(f"❌ 저장 실패 ({source}): {nickname} | 이유: {e}")










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

def get_player_ranked_stats(player_id, season_id):
    url = f"https://api.pubg.com/shards/{PLATFORM}/players/{player_id}/seasons/{season_id}/ranked"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return None


#  ✅  랭크 티어 이미지 경로 반환 함수
def get_rank_image_path(tier: str, sub_tier: str = "") -> str:
    tier = tier.capitalize()
    filename = f"{tier}-{sub_tier}.png" if sub_tier else f"{tier}.png"
    path = os.path.join("rank-image", filename)
    if os.path.exists(path):
        return path
    return os.path.join("rank-image", "Unranked.png")

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
        ranked_stats = get_player_ranked_stats(player_id, season_id)  # 랭크 전적 호출

        # 일반 스쿼드 전적 피드백
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

        # 일반 전적 필드 추가
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

        # 일반 스쿼드 피드백 임베드 필드
        embed.add_field(name="📊 SQUAD 분석 피드백", value="전투 성능을 바탕으로 분석된 결과입니다.", inline=False)
        embed.add_field(name="🔫 평균 데미지", value=f"```{dmg_msg}```", inline=False)
        embed.add_field(name="⚔️ K/D", value=f"```{kd_msg}```", inline=False)
        embed.add_field(name="🏆 승률", value=f"```{win_msg}```", inline=False)

        # 랭크 썸네일용 대표 티어 추적
        best_rank_score = -1
        best_rank_tier = "Unranked"
        best_rank_sub_tier = ""

        # ✅ 이 줄 추가하세요
        save_player_stats_to_file(닉네임, squad_metrics, ranked_stats, stats, discord_id=interaction.user.id, source="전적명령")



        # 랭크 전적 임베드 필드 추가
        if ranked_stats and "data" in ranked_stats:
            ranked_modes = ranked_stats["data"]["attributes"]["rankedGameModeStats"]
            for mode in ["solo", "duo", "squad"]:
                mode_rank = ranked_modes.get(mode)
                if not mode_rank:
                    continue

                tier = mode_rank.get("currentTier", {}).get("tier", "Unknown")
                sub_tier = mode_rank.get("currentTier", {}).get("subTier", "")
                rank_point = mode_rank.get("currentRankPoint", 0)
                rounds = mode_rank.get("roundsPlayed", 0)
                wins = mode_rank.get("wins", 0)
                kills = mode_rank.get("kills", 0)
                kd = mode_rank.get("kda", 0)
                win_pct = (wins / rounds * 100) if rounds > 0 else 0

                embed.add_field(name=f"🏅 {mode.upper()} 랭크 티어", value=f"{tier} {sub_tier}티어", inline=True)
                embed.add_field(name=f"🏅 {mode.upper()} 랭크 포인트", value=str(rank_point), inline=True)
                embed.add_field(name=f"🏅 {mode.upper()} 게임 수", value=str(rounds), inline=True)
                embed.add_field(name=f"🏅 {mode.upper()} 승리 수", value=f"{wins} ({win_pct:.2f}%)", inline=True)
                embed.add_field(name=f"🏅 {mode.upper()} 킬 수", value=str(kills), inline=True)
                embed.add_field(name=f"🏅 {mode.upper()} K/D", value=f"{kd:.2f}", inline=True)

                # 가장 높은 랭크 이미지용
                if rank_point > best_rank_score:
                    best_rank_score = rank_point
                    best_rank_tier = tier
                    best_rank_sub_tier = sub_tier
        else:
            embed.add_field(name="🏅 랭크 전적 정보", value="랭크 전적 정보를 불러올 수 없습니다.", inline=False)

        # 랭크 이미지 설정
        image_path = get_rank_image_path(best_rank_tier, best_rank_sub_tier)
        image_file = discord.File(image_path, filename="rank.png")
        embed.set_thumbnail(url="attachment://rank.png")

        embed.set_footer(text="PUBG API 제공")
        await interaction.followup.send(embed=embed, file=image_file)

    except requests.HTTPError as e:
        await interaction.followup.send(f"❌ API 오류가 발생했습니다: {e}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ 전적 조회 중 오류가 발생했습니다: {e}", ephemeral=True)

@전적.autocomplete("닉네임")
async def 닉네임_자동완성(interaction: discord.Interaction, current: str):
    guild = interaction.guild
    if not guild:
        return []

    choices = []
    for member in guild.members:
        if member.bot or not member.nick:
            continue

        parts = member.nick.split("/")
        if len(parts) >= 2:
            nickname = parts[1].strip()
            full_nick = member.nick.strip()

            # current 검색어가 닉네임 전체 또는 PUBG ID에 포함될 때만
            if current.lower() in full_nick.lower() or current.lower() in nickname.lower():
                choices.append(app_commands.Choice(
                    name=full_nick,  # 자동완성에 보이는 항목: 예) 토끼 / N_cafe24_A / 90
                    value=nickname  # 실제 입력될 값: N_cafe24_A
                ))

    return choices[:25]



@tree.command(name="시즌랭킹", description="현재 시즌의 항목별 TOP5을 확인합니다.", guild=discord.Object(id=GUILD_ID))
async def 시즌랭킹(interaction: discord.Interaction):
    await interaction.response.defer()

    leaderboard_path = "season_leaderboard.json"
    if not os.path.exists(leaderboard_path):
        await interaction.followup.send("❌ 아직 저장된 전적 데이터가 없습니다.", ephemeral=True)
        return

    with open(leaderboard_path, "r", encoding="utf-8") as f:
        file_data = json.load(f)
        all_players = file_data.get("players", [])
        # (게스트) 닉네임 가진 유저 제외
        players = [p for p in all_players if "(게스트)" not in p.get("nickname", "")]
        stored_season_id = file_data.get("season_id", "알 수 없음")

    if not players:
        await interaction.followup.send("❌ 현재 시즌에 저장된 유저 데이터가 없습니다.", ephemeral=True)
        return

    # 항목별 리스트 만들기
    damage_list = []
    kd_list = []
    winrate_list = []
    rankpoint_list = []
    rounds_list = []
    kills_list = []

    for player in players:
        name = player["nickname"]
        squad = player.get("squad", {})
        ranked = player.get("ranked", {})

        if squad:
            damage_list.append((name, squad.get("avg_damage", 0)))
            kd_list.append((name, squad.get("kd", 0)))
            winrate_list.append((name, squad.get("win_rate", 0)))
            rounds_list.append((name, squad.get("rounds_played", 0)))
            kills_list.append((name, squad.get("kills", 0)))

        if ranked:
            rankpoint_list.append((name, ranked.get("points", 0), ranked.get("tier", ""), ranked.get("subTier", "")))

    # 상위 5명 정렬
    damage_top5 = sorted(damage_list, key=lambda x: x[1], reverse=True)[:5]
    kd_top5 = sorted(kd_list, key=lambda x: x[1], reverse=True)[:5]
    win_top5 = sorted(winrate_list, key=lambda x: x[1], reverse=True)[:5]
    rank_top5 = sorted(rankpoint_list, key=lambda x: x[1], reverse=True)[:5]
    rounds_top5 = sorted(rounds_list, key=lambda x: x[1], reverse=True)[:5]
    kills_top5 = sorted(kills_list, key=lambda x: x[1], reverse=True)[:5]

    # 고정폭 글꼴(코드블록)으로 예쁘게 보여주기 함수
    def format_top5_codeblock(entries, is_percentage=False):
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        lines = []
        for i, entry in enumerate(entries):
            val = f"{entry[1]:.2f}%" if is_percentage else f"{entry[1]:.2f}"
            name = entry[0][:10].ljust(10)  # 닉네임 최대 10자, 좌측정렬
            val_str = val.rjust(7)           # 값 우측정렬
            lines.append(f"{medals[i]} {i+1}. {name} {val_str}")
        return "```\n" + "\n".join(lines) + "\n```"

    def format_top5_int_codeblock(entries):
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        lines = []
        for i, entry in enumerate(entries):
            name = entry[0][:10].ljust(10)
            val_str = str(entry[1]).rjust(7)
            lines.append(f"{medals[i]} {i+1}. {name} {val_str}")
        return "```\n" + "\n".join(lines) + "\n```"

    embed = discord.Embed(title=f"🏆 현재 시즌 항목별 TOP 5 (시즌 ID: {stored_season_id})", color=discord.Color.gold())

    embed.add_field(name="🔫 평균 데미지", value=format_top5_codeblock(damage_top5), inline=True)
    embed.add_field(name="⚔️ K/D", value=format_top5_codeblock(kd_top5), inline=True)
    embed.add_field(name="🏆 승률", value=format_top5_codeblock(win_top5, is_percentage=True), inline=True)
    embed.add_field(name="🎮 게임 수", value=format_top5_int_codeblock(rounds_top5), inline=True)
    embed.add_field(name="💀 킬 수", value=format_top5_int_codeblock(kills_top5), inline=True)

    if rank_top5:
        rank_msg = []
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, (name, points, tier, sub) in enumerate(rank_top5):
            rank_msg.append(f"{medals[i]} {i+1}. {name[:10].ljust(10)} - {tier} {sub} ({points})")
        embed.add_field(name="🥇 랭크 포인트", value="```\n" + "\n".join(rank_msg) + "\n```", inline=False)

    # footer 내용 (저장 유저 수 / 적합 유저 수)
    try:
        with open("valid_pubg_ids.json", "r", encoding="utf-8") as f:
            valid_members = json.load(f)
        embed.set_footer(
            text=f"※ 기준: 저장된 유저 {len(players)}명 / 총 적합 인원 {len(valid_members)}명"
        )
    except:
        embed.set_footer(
            text="※ 기준: 저장된 유저 전적"
        )

    await interaction.followup.send(embed=embed)





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

    with open("valid_pubg_ids.json", "w", encoding="utf-8") as f:
        json.dump(valid_members, f, ensure_ascii=False, indent=2)

    print(f"✅ valid_pubg_ids.json 자동 갱신 완료 (총 {len(valid_members)}명)")





from collections import defaultdict
import discord

@tree.command(name="검사", description="닉네임 검사", guild=discord.Object(id=GUILD_ID))
async def 검사(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    count = 0
    year_groups = defaultdict(list)

    for member in interaction.guild.members:
        if member.bot:
            continue

        parts = [p.strip() for p in (member.nick or member.name).strip().split("/")]
        if len(parts) != 3 or not nickname_pattern.fullmatch("/".join(p.strip() for p in parts)):
            count += 1
            try:
                await interaction.channel.send(f"{member.mention} 닉네임 형식이 올바르지 않아요.")
            except Exception as e:
                print(f"❗ 메시지 전송 오류: {member.name} - {e}")
        else:
            name, game_id, year = [p.strip() for p in parts]
            if year.isdigit():
                year_groups[year].append(member.display_name)

    # 형식 오류 안내 (ephemeral)
    await interaction.followup.send(f"🔍 검사 완료: {count}명 형식 오류 발견", ephemeral=True)


    await update_valid_pubg_ids(interaction.guild)










    
    
    # Embed 준비
    fields = []
    for year, members in sorted(year_groups.items(), key=lambda x: x[0]):
        member_list = ", ".join(members)
        if len(member_list) > 1024:
            member_list = member_list[:1021] + "..."
        fields.append((f"{year}년생 ({len(members)}명)", member_list))

    # 25개씩 분할 전송
    for i in range(0, len(fields), 25):
        embed = discord.Embed(
            title="📊 년생별 유저 분포",
            description="올바른 닉네임 형식의 유저 분포입니다.",
            color=discord.Color.green()
        )
        for name, value in fields[i:i+25]:
            embed.add_field(name=name, value=value, inline=False)
        await interaction.channel.send(embed=embed)




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

        await interaction.response.defer(thinking=True)

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

        # ✅ 이동 대상 수집
        members_to_move = []
        for ch in target_channels:
            for member in ch.members:
                if member.bot:
                    continue
                if member.voice and member.voice.channel.id == vc.id:
                    continue
                members_to_move.append(member)

        # ✅ 고속 이동 함수 정의
        async def move_members_in_batches(members, target_vc, batch_size=4, delay=0.3):
            moved_names = []
            for i in range(0, len(members), batch_size):
                batch = members[i:i+batch_size]
                tasks = [m.move_to(target_vc) for m in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for member, result in zip(batch, results):
                    if isinstance(result, Exception):
                        print(f"❌ {member.display_name} 이동 실패: {result}")
                    else:
                        moved_names.append(member.display_name)
                await asyncio.sleep(delay)
            return moved_names

        # ✅ 이동 실행
        moved_members = await move_members_in_batches(members_to_move, vc)

        if not moved_members:
            await interaction.followup.send("⚠️ 이동할 멤버가 없습니다.", ephemeral=True)
        else:
            embed = discord.Embed(
                title="📢 쿠치요세노쥬츠 !",
                description=(
                    f"{interaction.user.mention} 님이 **{len(moved_members)}명**을 음성채널로 소환했습니다.\n\n"
                    + "\n".join(f"▸ {name}" for name in moved_members)
                    + excluded_note
                ),
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
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 먼저 음성 채널에 들어가주세요!", ephemeral=True)
            else:
                await interaction.followup.send("❌ 먼저 음성 채널에 들어가주세요!", ephemeral=True)
            return

        selected_ids = self.parent_view.selected_member_ids
        if not selected_ids:
            if not interaction.response.is_done():
                await interaction.response.send_message("⚠️ 멤버를 선택해주세요.", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ 멤버를 선택해주세요.", ephemeral=True)
            return

        if not interaction.response.is_done():
            await interaction.response.defer(thinking=True)

        moved_members = []
        for member_id in selected_ids:
            member = interaction.guild.get_member(member_id)
            if member and member.voice and member.voice.channel.id != vc.id and not member.bot:
                try:
                    await member.move_to(vc)
                    moved_members.append(member.display_name)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"❌ {member.display_name} 이동 실패: {e}")

        if not moved_members:
            await interaction.followup.send("⚠️ 이동할 멤버가 없습니다.", ephemeral=True)
        else:
            embed = discord.Embed(
                title="📢 쿠치요세노쥬츠 !",
                description=(
                    f"{interaction.user.mention} 님이 **{len(moved_members)}명**을 음성채널로 소환했습니다.\n\n"
                    + "\n".join(f"▸ {name}" for name in moved_members)
                ),
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
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    vc = interaction.user.voice.channel if interaction.user.voice else None
    if not vc:
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ 음성 채널에 들어가주세요!", ephemeral=True)
        else:
            await interaction.followup.send("❌ 음성 채널에 들어가주세요!", ephemeral=True)
        return

    members = [m for m in interaction.guild.members if m.voice and m.voice.channel and not m.bot]
    if not members:
        if not interaction.response.is_done():
            await interaction.response.send_message("⚠️ 음성채널에 있는 멤버가 없습니다.", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ 음성채널에 있는 멤버가 없습니다.", ephemeral=True)
        return

    view = MemberSelectView(members)

    if not interaction.response.is_done():
        await interaction.response.send_message("소환할 멤버를 선택하세요:", view=view, ephemeral=True)
    else:
        await interaction.followup.send("소환할 멤버를 선택하세요:", view=view, ephemeral=True)










    

    # 서버 멤버 중 음성채널에 들어와있는 멤버만 필터링 (봇 제외)
    members = [m for m in interaction.guild.members if m.voice and m.voice.channel and not m.bot]

    if not members:
        await interaction.response.send_message("⚠️ 음성채널에 있는 멤버가 없습니다.", ephemeral=True)
        return

    view = MemberSelectView(members)
    await interaction.response.send_message("소환할 멤버를 선택하세요:", view=view, ephemeral=True)




# ✅ 팀 이동 버튼 View 클래스
class TeamMoveView(discord.ui.View):
    def __init__(self, teams, empty_channels, origin_channel):
        super().__init__(timeout=None)
        self.teams = teams
        self.empty_channels = empty_channels
        self.origin_channel = origin_channel
        self.moved = False

        self.initial_members = set()
        for team in teams[1:]:  # 팀1 제외 (원래 채널)
            self.initial_members.update(team)

    @discord.ui.button(label="🚀 팀 이동 시작", style=discord.ButtonStyle.green)
    async def move(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.moved:
            await interaction.response.send_message("이미 이동 완료됨", ephemeral=True)
            return

        # ✅ 인터랙션 응답 예약 (상호작용 실패 방지)
        await interaction.response.defer(ephemeral=True)

        button.disabled = True
        try:
            await interaction.message.edit(view=self)
        except Exception as e:
            print(f"⚠️ 메시지 편집 실패: {e}")
            return

        skipped_users = []

        async def move_member(member, target_channel):
            try:
                if member in self.initial_members:
                    if member.voice and member.voice.channel == self.origin_channel:
                        await member.move_to(target_channel)
                    else:
                        skipped_users.append(member.display_name)
            except Exception as e:
                print(f"이동 중 오류 발생: {member.display_name}: {e}")
                skipped_users.append(member.display_name)

        # ✅ 병렬 이동 처리
        tasks = []
        for team, channel in zip(self.teams[1:], self.empty_channels):
            for member in team:
                tasks.append(move_member(member, channel))

        await asyncio.gather(*tasks)

        self.moved = True
        self.stop()

        # ✅ 이동 결과 응답
        if skipped_users:
            names = ", ".join(skipped_users)
            await interaction.followup.send(
                f"⚠️ 아래 유저는 이동 전 다른 채널로 옮겨져 이동되지 않았습니다:\n{names}",
                ephemeral=True
            )
        else:
            await interaction.followup.send("✅ 모든 팀원이 정상적으로 이동되었습니다!", ephemeral=True)




# ✅ /팀짜기 명령어
@tree.command(name="팀짜기", description="음성 채널 팀 나누기", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(team_size="팀당 인원 수")
@app_commands.choices(team_size=[
    app_commands.Choice(name="2명", value=2),
    app_commands.Choice(name="3명", value=3),
    app_commands.Choice(name="4명", value=4),
])
async def 팀짜기(interaction: discord.Interaction, team_size: app_commands.Choice[int]):
    vc = interaction.user.voice.channel if interaction.user.voice else None
    if not vc:
        await interaction.response.send_message("❌ 음성 채널에 먼저 들어가 주세요!", ephemeral=True)
        return

    members = [m for m in vc.members if not m.bot]
    if len(members) < team_size.value + 1:
        await interaction.response.send_message("❌ 팀을 나누기엔 인원이 부족합니다.", ephemeral=True)
        return

    random.shuffle(members)
    teams = [members[i:i + team_size.value] for i in range(0, len(members), team_size.value)]

    guild = interaction.guild
    empty_channels = [
        ch for ch in guild.voice_channels
        if ch.name.startswith("일반") and len(ch.members) == 0 and ch != vc
    ]

    if len(empty_channels) < len(teams) - 1:
        await interaction.response.send_message("❌ 빈 채널이 부족합니다.", ephemeral=True)
        return

    msg = f"🎲 **팀 나누기 완료!**\n\n**팀 1 (현재 채널):** {', '.join(m.display_name for m in teams[0])}\n"
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


import os
import json
import asyncio
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import commands

# ✅ 봇 인스턴스, GUILD_ID, tree 정의 필요 (기존 코드에 있음)
failed_members = []
KST = timezone(timedelta(hours=9))

# ✅ 실패 기록 불러오기
if os.path.exists("failed_members.json"):
    with open("failed_members.json", "r", encoding="utf-8") as f:
        try:
            failed_members = json.load(f)
        except Exception:
            failed_members = []

# ✅ slash command: 저장 실패한 유저 확인
@tree.command(name="저장실패", description="저장에 실패한 멤버들을 조회합니다.", guild=discord.Object(id=GUILD_ID))
async def 저장실패(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)  # ⏳ 먼저 응답 예약

    if not failed_members:
        await interaction.followup.send("✅ 현재 저장에 실패한 멤버는 없습니다.", ephemeral=False)
        return

    mentions = []
    for m in failed_members:
        try:
            user = await bot.fetch_user(m["discord_id"])
            mentions.append(f"{user.mention} (`{m['name']}`)")
        except:
            mentions.append(f"`{m['name']}` (ID: {m['discord_id']})")

    embed = discord.Embed(
        title="❌ 저장 실패한 멤버 리스트",
        description="\n".join(mentions),
        color=discord.Color.red()
    )
    await interaction.followup.send(embed=embed, ephemeral=False)  # ⏱ 후속 응답


# ✅ 자동 수집 메인 루프
async def start_pubg_collection():
    await bot.wait_until_ready()
    while True:
        now = datetime.now(KST)
        target = now.replace(hour=4, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        print(f"🕓 {target.strftime('%Y-%m-%d %H:%M')}까지 대기 ({wait_seconds/60:.1f}분)")
        await asyncio.sleep(wait_seconds)

        # ✅ 수집 시작
        try:
            if not os.path.exists("valid_pubg_ids.json"):
                with open("valid_pubg_ids.json", "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=2)

            with open("valid_pubg_ids.json", "r", encoding="utf-8") as f:
                members = json.load(f)

            valid_members = [
                m for m in members if m.get("game_id") and "(게스트)" not in m.get("name", "")
            ]

            if not valid_members:
                print("⚠️ 유효한 배그 닉네임이 없습니다.")
                continue

            channel = discord.utils.get(bot.get_all_channels(), name="자동수집")
            today_str = datetime.now(KST).strftime("%Y-%m-%d")

            for m in valid_members:
                nickname = m["game_id"].strip()
                try:
                    if not can_make_request():
                        await asyncio.sleep(60)
                        continue

                    register_request()
                    player_id = get_player_id(nickname)
                    season_id = get_season_id()
                    stats = get_player_stats(player_id, season_id)
                    ranked_stats = get_player_ranked_stats(player_id, season_id)
                    squad_metrics, _ = extract_squad_metrics(stats)
                    save_player_stats_to_file(nickname, squad_metrics, ranked_stats, stats, discord_id=m["discord_id"], source="자동갱신")

                    print(f"✅ 저장 성공: {nickname}")
                    failed_members[:] = [fm for fm in failed_members if fm["discord_id"] != m["discord_id"]]

                    if channel:
                        embed = discord.Embed(
                            title="📦 전적 자동 저장 완료!",
                            description=f"{m['name']}님의 전적 데이터가 저장되었습니다!",
                            color=discord.Color.green()
                        )
                        embed.add_field(name="배그 닉네임", value=nickname, inline=True)
                        embed.set_footer(text="※ 오덕봇 자동 수집 기능")

                        try:
                            user = await bot.fetch_user(m["discord_id"])
                            await channel.send(content=f"{user.mention}", embed=embed)
                        except Exception as e:
                            print(f"❌ 유저 멘션 실패: {e}")

                except Exception as e:
                    print(f"❌ 저장 실패: {nickname} | 이유: {e}")
                    if not any(fm["discord_id"] == m["discord_id"] for fm in failed_members):
                        failed_members.append(m)
                        with open("failed_members.json", "w", encoding="utf-8") as f:
                            json.dump(failed_members, f, ensure_ascii=False, indent=2)

                await asyncio.sleep(60)  # 1분 간격 처리

            if channel:
                await channel.send(f"✅ `{today_str}` 기준, 총 {len(valid_members)}명의 전적 수집이 완료되었습니다.")

        except Exception as e:
            print(f"auto_collect_pubg_stats 함수 에러: {e}")


import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone, timedelta
import json
import os
import asyncio

# 🕰️ 한국 시간대
KST = timezone(timedelta(hours=9))

# 📁 저장 파일 경로
DAILY_CLAIMS_FILE = "daily_claims.json"
WEEKLY_CLAIMS_FILE = "weekly_claims.json"

DAILY_REWARD = 5000
WEEKLY_REWARD = 50000


# ✅ 잔액 관련 함수 (예시로 기본구조 제공 — 실제 구현은 사용중인 balance 시스템으로 대체)
def get_balance(user_id):
    with open("balance.json", "r", encoding="utf-8") as f:
        balances = json.load(f)
    return balances.get(str(user_id), {}).get("amount", 0)

def add_balance(user_id, amount):
    with open("balance.json", "r", encoding="utf-8") as f:
        balances = json.load(f)
    user_data = balances.get(str(user_id), {"amount": 0})
    user_data["amount"] += amount
    balances[str(user_id)] = user_data
    with open("balance.json", "w", encoding="utf-8") as f:
        json.dump(balances, f, indent=2, ensure_ascii=False)

# ✅ 일일 수령 기록 로드/저장
def load_daily_claims():
    if not os.path.exists(DAILY_CLAIMS_FILE):
        with open(DAILY_CLAIMS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    with open(DAILY_CLAIMS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_daily_claims(data):
    with open(DAILY_CLAIMS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ✅ 주간 수령 기록 로드/저장
def load_weekly_claims():
    if not os.path.exists(WEEKLY_CLAIMS_FILE):
        with open(WEEKLY_CLAIMS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    with open(WEEKLY_CLAIMS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_weekly_claims(data):
    with open(WEEKLY_CLAIMS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ✅ 최초 로딩
daily_claims = load_daily_claims()
weekly_claims = load_weekly_claims()


# ✅ /돈줘 명령어
@tree.command(name="돈줘", description="하루 1회 보상 + 주 1회 보상을 지급받습니다", guild=discord.Object(id=GUILD_ID))
async def 돈줘(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = datetime.now(KST)
    today = now.date().isoformat()
    current_week = now.strftime("%Y-%W")  # ex: 2025-29

    daily_given = daily_claims.get(user_id) == today
    weekly_given = weekly_claims.get(user_id) == current_week

    if daily_given and weekly_given:
        embed = discord.Embed(
            title="❌ 이미 수령 완료",
            description="오늘과 이번 주 보상을 모두 수령하셨습니다.\n내일 또는 다음 주에 다시 이용해주세요.",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    reward_msgs = []

    if not daily_given:
        add_balance(user_id, DAILY_REWARD)
        daily_claims[user_id] = today
        reward_msgs.append(f"📅 **일일 보상 {DAILY_REWARD:,}원 지급 완료!**")

    if not weekly_given:
        add_balance(user_id, WEEKLY_REWARD)
        weekly_claims[user_id] = current_week
        reward_msgs.append(f"🗓 **주간 보상 {WEEKLY_REWARD:,}원 지급 완료!**")

    save_daily_claims(daily_claims)
    save_weekly_claims(weekly_claims)

    embed = discord.Embed(
        title="💰 돈이 지급되었습니다!",
        description="\n".join(reward_msgs),
        color=discord.Color.green()
    )
    embed.set_footer(text=f"현재 잔액: {get_balance(user_id):,}원")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ⏰ 자정마다 daily_claims 초기화
@tasks.loop(hours=24)
async def reset_daily_claims():
    global daily_claims
    daily_claims = {}
    save_daily_claims(daily_claims)
    print("✅ daily_claims 초기화 완료 (한국 시 기준 자정)")

# ⏱️ 루프 시작 전: 자정까지 대기
@reset_daily_claims.before_loop
async def before_reset():
    await bot.wait_until_ready()
    now = datetime.now(KST)
    next_midnight = datetime.combine(now.date(), datetime.min.time(), tzinfo=KST) + timedelta(days=1)
    wait_seconds = (next_midnight - now).total_seconds()
    print(f"⏳ 자정까지 {int(wait_seconds)}초 대기 후 daily_claims 초기화 시작")
    await asyncio.sleep(wait_seconds)



from discord import app_commands
import discord

# ✅ /돈줘기록 – 본인의 수령 상태 확인
@tree.command(name="돈줘기록", description="내가 돈을 마지막으로 언제 받았는지 확인합니다.", guild=discord.Object(id=GUILD_ID))
async def 돈줘기록(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now = datetime.now(KST)
    today = now.date().isoformat()
    current_week = now.strftime("%Y-%W")

    last_daily = daily_claims.get(user_id)
    last_weekly = weekly_claims.get(user_id)

    daily_status = f"✅ 오늘({today}) 수령함" if last_daily == today else "❌ 오늘 아직 수령 안 함"
    weekly_status = f"✅ 이번 주({current_week}) 수령함" if last_weekly == current_week else "❌ 이번 주 아직 수령 안 함"

    embed = discord.Embed(title="📋 돈줘 수령 기록", color=discord.Color.blue())
    embed.add_field(name="📅 일일 보상", value=daily_status, inline=False)
    embed.add_field(name="🗓 주간 보상", value=weekly_status, inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)




# ✅ /돈줘초기화 – 개별 또는 전체 초기화 (채널관리자 전용)
@tree.command(name="돈줘초기화", description="돈줘 수령 기록을 초기화합니다 (관리자 전용)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(
    대상="기록을 초기화할 유저 (미입력 시 전체 초기화)"
)
async def 돈줘초기화(interaction: discord.Interaction, 대상: discord.User = None):
    # ✅ 권한 확인
    role_names = [role.name for role in interaction.user.roles]
    if "채널관리자" not in role_names:
        return await interaction.response.send_message(
            embed=create_embed("❌ 권한 없음", "**채널관리자** 역할만 사용 가능합니다.", discord.Color.red()),
            ephemeral=True
        )

    global daily_claims, weekly_claims
    updated_count = 0

    if 대상:
        uid = str(대상.id)
        if uid in daily_claims:
            daily_claims.pop(uid)
        if uid in weekly_claims:
            weekly_claims.pop(uid)
        save_daily_claims(daily_claims)
        save_weekly_claims(weekly_claims)

        embed = discord.Embed(
            title="✅ 개별 초기화 완료",
            description=f"{대상.mention}님의 수령 기록이 초기화되었습니다.",
            color=discord.Color.green()
        )
    else:
        daily_claims.clear()
        weekly_claims.clear()
        save_daily_claims(daily_claims)
        save_weekly_claims(weekly_claims)

        embed = discord.Embed(
            title="✅ 전체 초기화 완료",
            description="모든 유저의 돈줘 수령 기록이 초기화되었습니다.",
            color=discord.Color.green()
        )

    await interaction.response.send_message(embed=embed, ephemeral=False)



@tree.command(name="돈줘설정", description="일일 및 주간 보상 금액을 설정합니다 (관리자 전용)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(일일지급액="1회 지급되는 일일 보상 금액", 주간지급액="1회 지급되는 주간 보상 금액")
async def 돈줘설정(interaction: discord.Interaction, 일일지급액: int, 주간지급액: int):
    # ✅ 권한 확인
    role_names = [role.name for role in interaction.user.roles]
    if "채널관리자" not in role_names:
        return await interaction.response.send_message(
            embed=create_embed("❌ 권한 없음", "이 명령어는 **채널관리자**만 사용할 수 있습니다.", discord.Color.red()),
            ephemeral=True
        )

    global DAILY_REWARD, WEEKLY_REWARD
    DAILY_REWARD = 일일지급액
    WEEKLY_REWARD = 주간지급액

    embed = discord.Embed(
        title="⚙️ 돈줘 설정 변경 완료",
        description=f"📅 일일 보상: **{일일지급액:,}원**\n🗓 주간 보상: **{주간지급액:,}원**",
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed, ephemeral=False)


@tree.command(name="돈줘통계", description="일일 및 주간 보상 수령 인원을 확인합니다 (관리자 전용)", guild=discord.Object(id=GUILD_ID))
async def 돈줘통계(interaction: discord.Interaction):
    # ✅ 권한 확인
    role_names = [role.name for role in interaction.user.roles]
    if "채널관리자" not in role_names:
        return await interaction.response.send_message(
            embed=create_embed("❌ 권한 없음", "이 명령어는 **채널관리자**만 사용할 수 있습니다.", discord.Color.red()),
            ephemeral=True
        )

    now = datetime.now(KST)
    today = now.date().isoformat()
    current_week = now.strftime("%Y-%W")

    daily_count = sum(1 for date in daily_claims.values() if date == today)
    weekly_count = sum(1 for week in weekly_claims.values() if week == current_week)

    embed = discord.Embed(
        title="📊 돈줘 수령 통계",
        description=(
            f"📅 오늘 수령한 유저 수: **{daily_count}명**\n"
            f"🗓 이번 주 수령한 유저 수: **{weekly_count}명**"
        ),
        color=discord.Color.purple()
    )
    await interaction.response.send_message(embed=embed, ephemeral=False)












# ✅ 잔액
@tree.command(name="잔액", description="유저의 현재 보유 금액을 확인합니다", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(대상="조회할 유저 (선택사항)")
async def 잔액(interaction: discord.Interaction, 대상: discord.User = None):
    user = 대상 or interaction.user
    balance = get_balance(user.id)

    embed = discord.Embed(
        title="💵 잔액 확인",
        description=f"{user.mention}님의 현재 잔액은\n**{balance:,}원**입니다.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, ephemeral=False)




@tree.command(name="도박", description="도박 성공 시 2배 획득 (성공확률 30~70%)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(베팅액="최소 100원부터 도박 가능")
async def 도박(interaction: discord.Interaction, 베팅액: int):
    # ✅ 오덕도박장 채널 ID
    if interaction.channel.id != 1394331814642057418:
        return await interaction.response.send_message(
            "❌ 이 명령어는 **#오덕도박장** 채널에서만 사용할 수 있습니다.",
            ephemeral=True
        )

    user_id = str(interaction.user.id)
    balance = get_balance(user_id)

    # 최소 베팅, 잔액 부족 체크
    if 베팅액 < 100:
        return await interaction.response.send_message(
            embed=create_embed("❌ 베팅 실패", "최소 베팅 금액은 **100원**입니다.", discord.Color.red()),
            ephemeral=True
        )
    if balance < 베팅액:
        return await interaction.response.send_message(
            embed=create_embed("💸 잔액 부족", f"현재 잔액: **{balance:,}원**", discord.Color.red()),
            ephemeral=True
        )

    # 잔액 차감
    add_balance(user_id, -베팅액)

    # 도박 실행
    success_chance = random.randint(30, 70)
    roll = random.randint(1, 100)

    # ✅ 시각화 막대 (width=20, 마커 포함)
    def create_graph_bar(chance: int, roll: int, width: int = 20) -> str:
        success_pos = round(chance / 100 * width)
        roll_pos = round(roll / 100 * width)
        bar = ""
        for i in range(width):
            if i == roll_pos:
                bar += "⚡" if roll <= chance else "❌"
            else:
                bar += "■" if i < success_pos else "·"
        return f"[{bar}]"

    bar = create_graph_bar(success_chance, roll)

    # 성공
    if roll <= success_chance:
        is_jackpot = random.random() < 0.01
        multiplier = 4 if is_jackpot else 2
        reward = 베팅액 * multiplier
        add_balance(user_id, reward)
        final_balance = get_balance(user_id)

        # ✅ 기록 반영
        record_gamble_result(user_id, success=True)
        title = get_gamble_title(user_id, success=True)

        jackpot_msg = "💥 **🎉 잭팟! 4배 당첨!** 💥\n" if is_jackpot else ""
        embed = create_embed(
            "🎉 도박 성공!",
            f"{jackpot_msg}"
            f"(확률: {success_chance}%, 값: {roll})\n{bar}\n"
            f"+{reward:,}원 획득!\n💰 잔액: {final_balance:,}원\n\n"
            f"🏅 칭호: {title}",
            discord.Color.gold() if is_jackpot else discord.Color.green(),
            user_id
        )

    # 실패
    else:
        add_oduk_pool(베팅액)
        pool_amt = get_oduk_pool_amount()

        # ✅ 기록 반영
        record_gamble_result(user_id, success=False)
        title = get_gamble_title(user_id, success=False)

        embed = create_embed(
            "💀 도박 실패!",
            (
                f"(확률: {success_chance}%, 값: {roll})\n{bar}\n"
                f"-{베팅액:,}원 손실...\n"
                f"🍜 오덕 로또 상금: **{pool_amt:,}원** 적립됨!\n"
                f"🎟️ `/오덕로또참여`로 도전하세요!\n\n"
                f"🏅 칭호: {title}"
            ),
            discord.Color.red(),
            user_id
        )

    await interaction.response.send_message(embed=embed)


@도박.autocomplete("베팅액")
async def 베팅액_자동완성(interaction: discord.Interaction, current: str):
    from discord import app_commands

    balances = load_balances()
    user_id = str(interaction.user.id)
    balance = balances.get(user_id, {}).get("amount", 0)

    if balance < 100:
        return [app_commands.Choice(name="❌ 최소 베팅금 부족", value="0")]

    half = balance // 2
    allin = balance

    return [
        app_commands.Choice(name=f"🔥 전액 배팅 ({allin:,}원)", value=str(allin)),
        app_commands.Choice(name=f"💸 절반 배팅 ({half:,}원)", value=str(half)),
    ]








# ✅ 송금
@tree.command(name="송금", description="다른 유저에게 금액을 보냅니다", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(대상="금액을 보낼 유저", 금액="최소 100원 이상")
async def 송금(interaction: discord.Interaction, 대상: discord.User, 금액: int):
    보낸이 = str(interaction.user.id)
    받는이 = str(대상.id)

    if 보낸이 == 받는이:
        embed = discord.Embed(
            title="❌ 송금 실패",
            description="자기 자신에게는 송금할 수 없습니다.",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=False)

    if 금액 < 100:
        embed = discord.Embed(
            title="❌ 송금 실패",
            description="최소 송금 금액은 **100원**입니다.",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=False)

    if get_balance(보낸이) < 금액:
        embed = discord.Embed(
            title="💸 잔액 부족",
            description="송금할 만큼의 잔액이 부족합니다.",
            color=discord.Color.red()
        )
        return await interaction.response.send_message(embed=embed, ephemeral=False)

    add_balance(보낸이, -금액)
    add_balance(받는이, 금액)
    log_transfer(보낸이, 받는이, 금액)  # ✅ 이 줄 추가!

    embed = discord.Embed(
        title="✅ 송금 완료",
        description=f"{대상.mention}님에게 **{금액:,}원**을 송금했습니다.",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"보낸 사람 잔액: {get_balance(보낸이):,}원")
    await interaction.response.send_message(embed=embed, ephemeral=False)


from discord.ui import View, Button
import random
import discord

# 🎯 복권 버튼
class LotteryButton(Button):
    def __init__(self, label, correct_slot, 베팅액, user_id):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.correct_slot = correct_slot
        self.베팅액 = 베팅액
        self.user_id = str(user_id)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != int(self.user_id):
            return await interaction.response.send_message("❌ 본인만 참여할 수 있습니다.", ephemeral=True)
        if self.view.stopped:
            return await interaction.response.send_message("❌ 이미 복권이 종료되었습니다.", ephemeral=True)

        self.view.stop()

        try:
            if self.label == self.correct_slot:
                # 성공 처리
                reward = self.베팅액 * 3
                add_balance(self.user_id, reward)
                record_gamble_result(self.user_id, True)
                titles = get_gamble_title(self.user_id, True)
                title_str = "\n🏅 칭호: " + ", ".join(titles) if titles else ""
                title = "🎉 당첨!"
                desc = (
                    f"축하합니다! **{reward:,}원**을 획득했습니다!"
                    f"\n💰 잔액: **{get_balance(self.user_id):,}원**"
                    f"{title_str}"
                )
                color = discord.Color.green()

            else:
                # 실패 처리
                add_oduk_pool(self.베팅액)
                record_gamble_result(self.user_id, False)
                pool_amt = get_oduk_pool_amount()
                titles = get_gamble_title(self.user_id, False)
                title_str = "\n🏅 칭호: " + ", ".join(titles) if titles else ""
                title = "💔 꽝!"
                desc = (
                    f"아쉽지만 탈락입니다.\n**{self.베팅액:,}원**을 잃었습니다.\n\n"
                    f"🍜 오덕 로또 상금: **{pool_amt:,}원** 적립됨!\n"
                    f"🎟️ `/오덕로또참여`로 참여하세요!"
                    f"{title_str}"
                )
                color = discord.Color.red()

            await interaction.response.edit_message(
                embed=create_embed(title, desc, color, self.user_id),
                view=None
            )

        except Exception as e:
            print(f"❌ 복권 버튼 오류: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("⚠️ 오류가 발생했습니다.", ephemeral=True)



# 🎯 복권 인터페이스 (버튼 3개)
class LotteryView(View):
    def __init__(self, user_id, 베팅액):
        super().__init__(timeout=30)
        self.stopped = False
        correct = random.choice(["🎯", "🍀", "🎲"])
        for symbol in ["🎯", "🍀", "🎲"]:
            self.add_item(LotteryButton(label=symbol, correct_slot=correct, 베팅액=베팅액, user_id=user_id))

    def stop(self):
        self.stopped = True
        return super().stop()


# 🎯 복권 명령어 슬래시 커맨드
@tree.command(name="복권", description="복권 3개 중 하나를 선택해보세요", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(베팅액="최소 1000원 이상")
async def 복권(interaction: discord.Interaction, 베팅액: int):
    # ✅ 허용된 채널: 오덕도박장, 오덕코인
    if interaction.channel.id not in [1394331814642057418, 1394519744463245543]:
        return await interaction.response.send_message(
            "❌ 이 명령어는 **#오덕도박장** 또는 **#오덕코인** 채널에서만 사용할 수 있습니다.",
            ephemeral=True
        )

    user_id = str(interaction.user.id)


    if 베팅액 < 1000:
        return await interaction.response.send_message(
            embed=create_embed("❌ 베팅 실패", "최소 베팅 금액은 **1,000원**입니다.", discord.Color.red()),
            ephemeral=False
        )

    if get_balance(user_id) < 베팅액:
        return await interaction.response.send_message(
            embed=create_embed("💸 잔액 부족", f"잔액: **{get_balance(user_id):,}원**", discord.Color.red()),
            ephemeral=False
        )

    add_balance(user_id, -베팅액)
    view = LotteryView(user_id=interaction.user.id, 베팅액=베팅액)

    await interaction.response.send_message(
        embed=create_embed(
            "🎟 복권 게임 시작!",
            "3개의 이모지 중 하나를 선택해주세요.\n당첨되면 **3배 보상!**",
            discord.Color.blue()
        ),
        view=view,
        ephemeral=False
    )

@복권.autocomplete("베팅액")
async def 복권_배팅액_자동완성(interaction: discord.Interaction, current: str):
    from discord import app_commands

    balances = load_balances()
    user_id = str(interaction.user.id)
    balance = balances.get(user_id, {}).get("amount", 0)

    if balance < 1000:
        return [app_commands.Choice(name="❌ 최소 베팅금 부족", value="0")]

    half = balance // 2
    allin = balance

    choices = [
        app_commands.Choice(name=f"🔥 전액 배팅 ({allin:,}원)", value=str(allin)),
        app_commands.Choice(name=f"💸 절반 배팅 ({half:,}원)", value=str(half)),
    ]

    return choices






@tree.command(name="슬롯", description="애니메이션 슬롯머신 게임!", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(베팅액="최소 1000원 이상")
async def 슬롯(interaction: discord.Interaction, 베팅액: int):
    # ✅ 허용된 채널: 오덕도박장, 오덕코인
    if interaction.channel.id not in [1394331814642057418, 1394519744463245543]:
        return await interaction.response.send_message(
            "❌ 이 명령어는 **#오덕도박장** 또는 **#오덕코인** 채널에서만 사용할 수 있습니다.",
            ephemeral=True
        )

    user_id = str(interaction.user.id)
    symbols = ["🍒", "🍋", "🍇", "🍉", "💎"]
    balance = get_balance(user_id)

    if 베팅액 < 1000:
        return await interaction.response.send_message(
            embed=create_embed("❌ 베팅 실패", "최소 베팅 금액은 **1,000원**입니다.", discord.Color.red()), ephemeral=False)

    if balance < 베팅액:
        return await interaction.response.send_message(
            embed=create_embed("💸 잔액 부족", f"현재 잔액: **{balance:,}원**", discord.Color.red()), ephemeral=False)

    # 💸 잔액 차감
    add_balance(user_id, -베팅액)

    # 🎰 슬롯머신 연출
    await interaction.response.defer()
    message = await interaction.followup.send("🎰 슬롯머신 작동 중...", wait=True)

    result = []
    for i in range(5):
        result.append(random.choice(symbols))
        display = " | ".join(result + ["⬜"] * (5 - len(result)))
        await message.edit(content=f"🎰 **슬롯머신 작동 중...**\n| {display} |")
        await asyncio.sleep(0.7)

    result_str = " | ".join(result)

    # 🎯 최대 연속 일치 계산
    max_streak = 1
    cur_streak = 1
    for i in range(1, len(result)):
        if result[i] == result[i - 1]:
            cur_streak += 1
            max_streak = max(max_streak, cur_streak)
        else:
            cur_streak = 1

    # 🎉 성공
    if max_streak == 5:
        winnings = 베팅액 * 10
        add_balance(user_id, winnings)
        record_gamble_result(user_id, True)
        titles = get_gamble_title(user_id, True)
        title_str = "\n🏅 칭호: " + ", ".join(titles) if titles else ""
        outcome = f"🎉 **5개 연속 일치! +{winnings:,}원 획득!**{title_str}"
        color = discord.Color.green()

    elif max_streak >= 3:
        winnings = 베팅액 * 4
        add_balance(user_id, winnings)
        record_gamble_result(user_id, True)
        titles = get_gamble_title(user_id, True)
        title_str = "\n🏅 칭호: " + ", ".join(titles) if titles else ""
        outcome = f"✨ **{max_streak}개 연속 일치! +{winnings:,}원 획득!**{title_str}"
        color = discord.Color.green()

    # 💀 실패
    else:
        add_oduk_pool(베팅액)
        record_gamble_result(user_id, False)
        pool_amt = get_oduk_pool_amount()
        titles = get_gamble_title(user_id, False)
        title_str = "\n🏅 칭호: " + ", ".join(titles) if titles else ""
        outcome = (
            f"😢 **꽝! 다음 기회를 노려보세요.\n-{베팅액:,}원 손실**\n\n"
            f"🍜 오덕 로또 상금: **{pool_amt:,}원** 적립됨!\n"
            f"🎟️ `/오덕로또참여`로 참여하세요!"
            f"{title_str}"
        )
        color = discord.Color.red()

    await message.edit(
        content=(
            f"🎰 **슬롯머신 결과**\n| {result_str} |\n\n"
            f"{outcome}\n💵 현재 잔액: {get_balance(user_id):,}원"
        )
    )



@슬롯.autocomplete("베팅액")
async def 슬롯_배팅액_자동완성(interaction: discord.Interaction, current: str):
    from discord import app_commands

    balances = load_balances()
    user_id = str(interaction.user.id)
    balance = balances.get(user_id, {}).get("amount", 0)

    if balance < 1000:
        return [app_commands.Choice(name="❌ 최소 베팅금 부족", value="0")]

    half = balance // 2
    allin = balance

    choices = [
        app_commands.Choice(name=f"🔥 전액 배팅 ({allin:,}원)", value=str(allin)),
        app_commands.Choice(name=f"💸 절반 배팅 ({half:,}원)", value=str(half)),
    ]

    return choices




@tree.command(name="도박왕", description="도박 잔액 순위 TOP 10", guild=discord.Object(id=GUILD_ID))
async def 도박왕(interaction: discord.Interaction):
    await interaction.response.defer()

    data = load_balances()
    sorted_list = sorted(data.items(), key=lambda x: x[1].get("amount", 0), reverse=True)[:10]

    embed = discord.Embed(
        title="💰 도박 순위 TOP 10",
        description="상위 10명의 도박 잔액 현황입니다.",
        color=discord.Color.gold()
    )

    for rank, (uid, info) in enumerate(sorted_list, start=1):
        try:
            member = await interaction.guild.fetch_member(int(uid))
            name = member.display_name  # ✅ 서버 내 별명
        except Exception:
            try:
                user = await bot.fetch_user(int(uid))
                name = user.name  # fallback
            except:
                name = f"Unknown ({uid})"

        balance = info.get("amount", 0)
        embed.add_field(
            name=f"{rank}위 - {name}",
            value=f"{balance:,}원",
            inline=False
        )

    await interaction.followup.send(embed=embed)

def create_embed(title: str, description: str, color: discord.Color, user_id: str = None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    if user_id:
        
        embed.set_footer(text=f"현재 잔액: {get_balance(user_id):,}원")
    return embed




# ✅ 배틀 기록 유틸리티
BATTLE_STATS_FILE = "battle_stats.json"
PAIR_STATS_FILE = "pair_stats.json"

def load_battle_stats():
    if not os.path.exists(BATTLE_STATS_FILE):
        with open(BATTLE_STATS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(BATTLE_STATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_battle_stats(data):
    with open(BATTLE_STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def add_battle_result(user_id, wins, losses, profit):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    data = load_battle_stats()
    if user_id not in data:
        data[user_id] = []
    data[user_id].append({"date": today, "wins": wins, "losses": losses, "profit": profit})
    save_battle_stats(data)

def summarize_last_month(data):
    cutoff = datetime.utcnow() - timedelta(days=30)
    result = {}
    for uid, records in data.items():
        wins = losses = profit = 0
        new_records = []
        for r in records:
            try:
                date = datetime.fromisoformat(r["date"])
            except:
                continue
            if date >= cutoff:
                wins += r.get("wins", 0)
                losses += r.get("losses", 0)
                profit += r.get("profit", 0)
                new_records.append(r)
        if wins + losses > 0:
            result[uid] = {"wins": wins, "losses": losses, "profit": profit}
        data[uid] = new_records
    save_battle_stats(data)
    return result

def load_pair_stats():
    if not os.path.exists(PAIR_STATS_FILE):
        with open(PAIR_STATS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(PAIR_STATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_pair_stats(data):
    with open(PAIR_STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ✅ 도박 배틀 명령어
@tree.command(name="도박배틀", description="특정 유저와 1:1 도박 배틀을 시작합니다", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(대상="도전할 유저", 배팅금액="서로 걸 금액")
async def 도박배틀(interaction: discord.Interaction, 대상: discord.Member, 배팅금액: int):
    호출자 = interaction.user

    allowed_channel_ids = [1394331814642057418, 1394519744463245543]
    if interaction.channel.id not in allowed_channel_ids:
        return await interaction.response.send_message(
            "❌ 이 명령어는 **#오덕도박장** 또는 **#오덕코인** 채널에서만 사용할 수 있습니다.",
            ephemeral=True
        )
    if 호출자.id == 대상.id:
        return await interaction.response.send_message("❌ 자신과는 배틀할 수 없습니다.", ephemeral=True)

    caller_id = str(호출자.id)
    target_id = str(대상.id)

    balances = load_balances()
    if caller_id not in balances or balances[caller_id]["amount"] < 배팅금액:
        return await interaction.response.send_message("❌ 배팅할 충분한 잔액이 없습니다.", ephemeral=True)
    if target_id not in balances or balances[target_id]["amount"] < 배팅금액:
        return await interaction.response.send_message("❌ 상대 유저가 배팅금액을 감당할 수 없습니다.", ephemeral=True)

    class BattleConfirmView(discord.ui.View):
        def __init__(self, caller, target, amount):
            super().__init__(timeout=10)
            self.caller = caller
            self.target = target
            self.amount = amount
            self.message = None

        async def on_timeout(self):
            for child in self.children:
                child.disabled = True
            try:
                if self.message:
                    await self.message.edit(content="⏱️ 시간 초과로 배틀이 자동 취소되었습니다.", view=self)
            except:
                pass

        @discord.ui.button(label="도전 수락", style=discord.ButtonStyle.success)
        async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.target.id:
                return await interaction.response.send_message("❌ 이 버튼은 도전 대상만 누를 수 있습니다.", ephemeral=True)

            balances = load_balances()

            # ✅ 다시 잔액 확인 후 양측 선차감
            if balances.get(str(self.caller.id), {}).get("amount", 0) < self.amount or \
               balances.get(str(self.target.id), {}).get("amount", 0) < self.amount:
                self.stop()
                await interaction.response.send_message("❌ 한쪽 유저의 잔액이 부족해 배틀이 취소되었습니다.", ephemeral=True)
                try:
                    await self.message.edit(content="🚫 잔액 부족으로 배틀이 취소되었습니다.", view=None)
                except:
                    pass
                return

            balances[str(self.caller.id)]["amount"] -= self.amount
            balances[str(self.target.id)]["amount"] -= self.amount

            # ✅ 승자 결정
            winner = random.choice([self.caller, self.target])
            loser = self.target if winner == self.caller else self.caller

            # ✅ 세금 및 지급 처리
            total_bet = self.amount * 2
            tax = int(total_bet * 0.1)
            net_gain = total_bet - tax
            add_oduk_pool(tax)

            balances[str(winner.id)]["amount"] += net_gain
            save_balances(balances)

            # ✅ 전적 기록
            add_battle_result(str(winner.id), 1, 0, self.amount)
            add_battle_result(str(loser.id), 0, 1, -self.amount)

            # ✅ 도박 전적 기록 추가 (칭호용)
            record_gamble_result(str(winner.id), True)
            record_gamble_result(str(loser.id), False)

            # ✅ 칭호
            winner_titles = get_gamble_title(str(winner.id), True)
            loser_titles = get_gamble_title(str(loser.id), False)

            # ✅ 개인간 전적 기록
            pair_stats = load_pair_stats()
            uid1, uid2 = sorted([str(self.caller.id), str(self.target.id)])
            key = f"{uid1}_{uid2}"
            if key not in pair_stats:
                pair_stats[key] = {uid1: 0, uid2: 0}
            pair_stats[key][str(winner.id)] += 1
            save_pair_stats(pair_stats)

            total = pair_stats[key][uid1] + pair_stats[key][uid2]
            caller_wins = pair_stats[key][str(self.caller.id)]
            target_wins = pair_stats[key][str(self.target.id)]
            winrate = round((caller_wins / total) * 100, 1) if total > 0 else 0

            oduk_pool = load_oduk_pool()
            pool_amount = oduk_pool.get("amount", 0)

            self.stop()
            try:
                await self.message.edit(view=None)
            except:
                pass

            # ✅ 현재 잔액 조회
            caller_amount = balances.get(str(self.caller.id), {}).get("amount", 0)
            target_amount = balances.get(str(self.target.id), {}).get("amount", 0)

            await interaction.channel.send(
                f"🎲 도박 배틀 결과: {self.caller.mention} vs {self.target.mention}\n"
                f"🏆 승자: **{winner.mention}**님! **{net_gain:,}원** 획득! "
                f"(세금 {tax:,}원 → 오덕로또 적립)\n\n"
                f"📊 전체 전적 ({self.caller.display_name} vs {self.target.display_name}): "
                f"{caller_wins}승 {target_wins}패 (승률 {winrate}%)\n"
                f"🏅 {winner.display_name} 칭호: {winner_titles or '없음'}\n"
                f"💀 {loser.display_name} 칭호: {loser_titles or '없음'}\n\n"
                f"💰 현재 잔액:\n"
                f"  {self.caller.display_name}: **{caller_amount:,}원**\n"
                f"  {self.target.display_name}: **{target_amount:,}원**\n"
                f"🎟️ `/오덕로또참여`로 오늘의 운도 시험해보세요!"
            )


        @discord.ui.button(label="거절", style=discord.ButtonStyle.danger)
        async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.target.id:
                return await interaction.response.send_message("❌ 이 버튼은 도전 대상만 누를 수 있습니다.", ephemeral=True)
            self.stop()
            try:
                await self.message.edit(content="🚫 배틀이 거절되었습니다.", view=None)
            except:
                pass

    view = BattleConfirmView(호출자, 대상, 배팅금액)
    await interaction.response.send_message(
        f"⚔️ {대상.mention}, {호출자.mention}님이 **{배팅금액:,}원** 걸고 1:1 도박 배틀을 요청했습니다!",
        view=view
    )
    view.message = await interaction.original_response()


@도박배틀.autocomplete("배팅금액")
async def 배팅금액_자동완성(
    interaction: discord.Interaction,
    current: str
):
    from discord import app_commands

    balances = load_balances()
    caller_id = str(interaction.user.id)
    caller_bal = balances.get(caller_id, {}).get("amount", 0)

    # 안전하게 대상 유저 불러오기
    target_member = getattr(interaction.namespace, "대상", None)
    if target_member is None:
        return [
            app_commands.Choice(name="⚠️ 먼저 대상을 선택하세요.", value="0")
        ]

    target_id = str(target_member.id)
    target_bal = balances.get(target_id, {}).get("amount", 0)

    # 두 사람 중 더 적은 잔액을 기준으로 최대 가능 금액 설정
    max_bet = min(caller_bal, target_bal)
    if max_bet <= 0:
        return [app_commands.Choice(name="❌ 배팅 가능 금액 없음", value="0")]

    return [
        app_commands.Choice(
            name=f"{max_bet:,}원 (최대 가능 금액)",
            value=str(max_bet)
        )
    ]
















@tree.command(name="배틀왕", description="배틀 승률 기준 시즌 누적 랭킹을 확인합니다", guild=discord.Object(id=GUILD_ID))
async def 배틀왕(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    data = load_battle_stats()
    recent_stats = summarize_last_month(data)

    ranking = []
    for uid, record in recent_stats.items():
        wins = record.get("wins", 0)
        losses = record.get("losses", 0)
        profit = record.get("profit", 0)
        total = wins + losses
        if total == 0:
            continue
        winrate = round((wins / total) * 100, 1)
        ranking.append({
            "user_id": uid,
            "wins": wins,
            "losses": losses,
            "winrate": winrate,
            "profit": profit
        })

    ranking.sort(key=lambda x: (-x["winrate"], -x["wins"], x["user_id"]))

    lines = ["🏆 **배틀왕 랭킹 (최근 1달 기준)**\n"]
    for i, r in enumerate(ranking[:10], start=1):
        try:
            user = await bot.fetch_user(int(r["user_id"]))
            mention = user.mention
        except:
            mention = f"<@{r['user_id']}>"
        lines.append(
            f"**{i}위. {mention}** – {r['wins']}승 {r['losses']}패 "
            f"(승률 {r['winrate']}%) | 수익: {'+' if r['profit'] > 0 else ''}{r['profit']:,}원"
        )

    lines.append("\n※ 위 통계는 최근 1달 기준입니다.")
    await interaction.followup.send("\n".join(lines))































@tree.command(name="일괄지급", description="서버 내 모든 유저에게 일정 금액을 지급합니다", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(금액="지급할 금액 (1원 이상)")
async def 일괄지급(interaction: discord.Interaction, 금액: int):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            embed=create_embed("❌ 권한 없음", "이 명령어는 관리자만 사용할 수 있습니다.", discord.Color.red()),
            ephemeral=True
        )

    if 금액 <= 0:
        return await interaction.response.send_message(
            embed=create_embed("❌ 잘못된 금액", "1원 이상만 지급할 수 있습니다.", discord.Color.red()),
            ephemeral=True
        )

    await interaction.response.defer(thinking=True)

    guild = interaction.guild
    count = 0

    async for member in guild.fetch_members(limit=None):
        if member.bot:
            continue
        add_balance(str(member.id), 금액)
        count += 1

    embed = create_embed(
        "💸 일괄 지급 완료",
        f"총 **{count}명**에게 **{금액:,}원**씩 지급했습니다.",
        discord.Color.green()
    )
    await interaction.followup.send(embed=embed)












@tree.command(name="돈지급", description="관리자가 유저에게 돈을 지급합니다", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(대상="돈을 지급할 유저", 금액="지급할 금액")
async def 돈지급(interaction: discord.Interaction, 대상: discord.User, 금액: int):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            embed=create_embed("❌ 권한 없음", "이 명령어는 관리자만 사용할 수 있습니다.", discord.Color.red()),
            ephemeral=False)

    if 금액 <= 0:
        return await interaction.response.send_message(
            embed=create_embed("❌ 잘못된 금액", "1원 이상만 지급할 수 있습니다.", discord.Color.red()),
            ephemeral=False)

    add_balance(str(대상.id), 금액)
    await interaction.response.send_message(
        embed=create_embed("💸 돈 지급 완료", f"{대상.mention}님에게 **{금액:,}원**을 지급했습니다.", discord.Color.green(), 대상.id))

@tree.command(name="투자종목", description="투자 가능한 종목과 현재 1주당 가격을 확인합니다", guild=discord.Object(id=GUILD_ID))
async def 투자종목(interaction: discord.Interaction):
    stocks = load_stocks()
    embeds = []
    embed = discord.Embed(title="📈 투자 종목 리스트", color=discord.Color.gold())
    count = 0

    for name, info in stocks.items():
        embed.add_field(
            name=name,
            value=f"💵 1주 가격: {info['price']:,}원",
            inline=True
        )
        count += 1
        if count == 25:
            embeds.append(embed)
            embed = discord.Embed(color=discord.Color.gold())
            count = 0

    if count > 0:
        embeds.append(embed)

    await interaction.response.send_message(embeds=embeds)





# ✅ 필요한 모듈
import os
import json
import random
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import tasks
from dateutil.parser import isoparse  # ⬅️ 추가됨

# ✅ 파일 저장 및 불러오기 함수들
def save_last_chart_time(dt: datetime):
    with open("last_chart_time.json", "w", encoding="utf-8") as f:
        json.dump({"last_updated": dt.isoformat()}, f)

def load_last_chart_time() -> datetime:
    if not os.path.exists("last_chart_time.json"):
        return datetime.min.replace(tzinfo=timezone.utc)  # ⬅️ timezone-aware로 변경
    with open("last_chart_time.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        return isoparse(data.get("last_updated", "1970-01-01T00:00:00+00:00"))  # ⬅️ 항상 timezone 포함

def save_investment_history(history):
    file = "investment_history.json"
    if not os.path.exists(file):
        with open(file, "w", encoding="utf-8") as f:
            json.dump([], f)
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.extend(history)
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)






@tree.command(name="투자", description="종목을 선택하고 몇 주를 살지 정합니다", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(종목="투자할 종목 이름", 수량="구매할 주식 수 (최소 1주)")
async def 투자(interaction: discord.Interaction, 종목: str, 수량: int):
    # ✅ 허용된 채널: 오덕도박장, 오덕코인
    if interaction.channel.id not in [1394331814642057418, 1394519744463245543]:
        return await interaction.response.send_message(
            "❌ 이 명령어는 **#오덕도박장** 또는 **#오덕코인** 채널에서만 사용할 수 있습니다.",
            ephemeral=True
        )

    user_id = str(interaction.user.id)
    종목 = 종목.strip()
    stocks = load_stocks()
    purchase_fee_rate = 0.01  # ✅ 수수료 1%


    if 종목 not in stocks:
        return await interaction.response.send_message(
            embed=create_embed("❌ 종목 오류", f"'{종목}'은 존재하지 않는 종목입니다.", discord.Color.red()), ephemeral=False)

    if 수량 < 1:
        return await interaction.response.send_message(
            embed=create_embed("❌ 수량 오류", "최소 **1주** 이상 구매해야 합니다.", discord.Color.red()), ephemeral=False)

    단가 = stocks[종목]["price"]
    실단가 = int(단가 * (1 + purchase_fee_rate))  # ✅ 수수료 포함 단가
    총액 = 실단가 * 수량
    실제구매가 = 단가 * 수량
    수수료 = 총액 - 실제구매가

    if get_balance(user_id) < 총액:
        return await interaction.response.send_message(
            embed=create_embed("💸 잔액 부족", f"보유 잔액: **{get_balance(user_id):,}원**\n필요 금액 (수수료 포함): **{총액:,}원**", discord.Color.red()), ephemeral=False)

    # ✅ 수수료 적립
    add_oduk_pool(수수료)
    oduk_amount = get_oduk_pool_amount()

    # ✅ 잔액 차감 및 투자 저장
    add_balance(user_id, -총액)
    investments = load_investments()
    investments.append({
        "user_id": user_id,
        "stock": 종목,
        "shares": 수량,
        "price_per_share": 단가,
        "timestamp": datetime.now().isoformat()
    })
    save_investments(investments)

    # ✅ 메시지 전송
    await interaction.response.send_message(
        embed=create_embed(
            "📥 투자 완료",
            (
                f"**{종목}** {수량}주 구매 완료!\n"
                f"총 투자금 (수수료 포함): **{총액:,}원**\n"
                f"💸 적립된 수수료: **{수수료:,}원**\n"
                f"🏦 현재 오덕잔고: **{oduk_amount:,}원**"
            ),
            discord.Color.blue(),
            user_id
        )
    )



# ✅ 종목 자동완성
@투자.autocomplete("종목")
async def 종목_자동완성(interaction: discord.Interaction, current: str):
    stocks = load_stocks()
    current_lower = current.lower()

    return [
        app_commands.Choice(name=name, value=name)
        for name in stocks
        if current_lower in name.lower()
    ][:25]


# ✅ 수량 자동완성 (수수료 반영)
@투자.autocomplete("수량")
async def 수량_자동완성(interaction: discord.Interaction, current: int):
    user_id = str(interaction.user.id)
    stocks = load_stocks()

    selected_stock = interaction.namespace.종목
    if not selected_stock or selected_stock not in stocks:
        return []

    단가 = stocks[selected_stock]["price"]
    수수료율 = 0.01  # ✅ 수수료 반영
    실단가 = int(단가 * (1 + 수수료율))
    잔액 = get_balance(user_id)

    최대_수량 = 잔액 // 실단가
    if 최대_수량 < 1:
        return [app_commands.Choice(name="❌ 잔액 부족: 수수료 포함 구매 불가", value=0)]

    return [
        app_commands.Choice(
            name=f"📈 최대 구매 가능: {최대_수량}주 (수수료 포함 {최대_수량 * 실단가:,}원)",
            value=최대_수량
        )
    ]




@tree.command(name="자동투자", description="무작위 종목에 입력한 금액 내에서 자동 분산 투자", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(금액="투자할 총 금액 (최소 1,000원)")
async def 자동투자(interaction: discord.Interaction, 금액: int):
    await interaction.response.defer(thinking=True)

    if interaction.channel.id not in [1394331814642057418, 1394519744463245543]:
        return await interaction.followup.send(
            "❌ 이 명령어는 **#오덕도박장** 또는 **#오덕코인** 채널에서만 사용할 수 있습니다.",
            ephemeral=True
        )

    user_id = str(interaction.user.id)
    balance = get_balance(user_id)

    if 금액 < 1000:
        return await interaction.followup.send(
            embed=create_embed("❌ 금액 오류", "최소 **1,000원** 이상만 가능합니다.", discord.Color.red()),
            ephemeral=True
        )

    if balance < 금액:
        return await interaction.followup.send(
            embed=create_embed("💸 잔액 부족", f"현재 잔액: **{balance:,}원**", discord.Color.red()),
            ephemeral=True
        )

    stocks = load_stocks()
    종목_전체 = list(stocks.keys())
    random.shuffle(종목_전체)

    # ✅ 매수 가능한 종목 필터링
    매수가능종목 = []
    for 종목 in 종목_전체:
        단가 = stocks[종목]["price"]
        실단가 = int(단가 * 1.01)
        if 실단가 <= 금액:
            매수가능종목.append((종목, 실단가, 단가))

    if len(매수가능종목) < 1:
        return await interaction.response.send_message(
            embed=create_embed("🤷 자동투자 실패", "입력 금액으로는 매수 가능한 종목이 없습니다.", discord.Color.orange()), ephemeral=False)

    # ✅ 종목 선택
    if len(매수가능종목) >= 5:
        선택개수 = random.randint(5, min(30, len(매수가능종목)))
        선택된종목들 = random.sample(매수가능종목, 선택개수)
    else:
        선택된종목들 = 매수가능종목

    남은금액 = 금액
    매수기록 = {}
    수수료총합 = 0
    총사용액 = 0

    while True:
        매수성공 = False
        for 종목, 실단가, 원단가 in 선택된종목들:
            if 남은금액 < 실단가:
                continue

            shares_to_buy = random.randint(1, 5)
            가능한수량 = 남은금액 // 실단가
            매수수량 = min(shares_to_buy, 가능한수량)

            if 매수수량 <= 0:
                continue

            매수성공 = True
            총사용액 += 실단가 * 매수수량
            수수료총합 += (실단가 - 원단가) * 매수수량
            남은금액 -= 실단가 * 매수수량

            if 종목 in 매수기록:
                매수기록[종목]["shares"] += 매수수량
                매수기록[종목]["total_price"] += 실단가 * 매수수량
                매수기록[종목]["fee"] += (실단가 - 원단가) * 매수수량
            else:
                매수기록[종목] = {
                    "shares": 매수수량,
                    "price_per_share": 원단가,
                    "total_price": 실단가 * 매수수량,
                    "fee": (실단가 - 원단가) * 매수수량
                }

        if not 매수성공 or 남은금액 < 1000:
            break

    if not 매수기록:
        return await interaction.response.send_message(
            embed=create_embed("🤷 자동투자 실패", "입력 금액으로는 매수 가능한 종목이 없습니다.", discord.Color.orange()), ephemeral=False)

    # ✅ 잔액 일괄 차감
    add_balance(user_id, -총사용액)

    # ✅ 투자 저장
    investments = load_investments()
    투자결과 = []
    for 종목, data in 매수기록.items():
        investments.append({
            "user_id": user_id,
            "stock": 종목,
            "shares": data["shares"],
            "price_per_share": data["price_per_share"],
            "timestamp": datetime.now().isoformat()
        })
        투자결과.append(f"📈 **{종목}** {data['shares']}주 (총 {data['total_price']:,}원)")

    save_investments(investments)

    # ✅ 수수료 로또 적립
    add_oduk_pool(수수료총합)
    oduk_amount = get_oduk_pool_amount()

    # ✅ 출력
    await interaction.followup.send(
        embed=create_embed(
            "🎯 라운드로빈 자동투자 완료",
            (
                f"총 입력금액: **{금액:,}원** 중 사용: **{총사용액:,}원**\n"
                f"💸 수수료 적립: **{수수료총합:,}원** → 오덕잔고 적립 완료\n"
                f"🏦 현재 오덕잔고: **{oduk_amount:,}원**\n\n" +
                "\n".join(투자결과)
            ),
            discord.Color.teal(),
            user_id
        )
    )




# ✅ 자동완성 함수 (잔액 자동 표시)
@자동투자.autocomplete("금액")
async def 자동투자_금액_자동완성(interaction: discord.Interaction, current: int):
    user_id = str(interaction.user.id)
    잔액 = get_balance(user_id)

    if 잔액 < 1000:
        return [
            app_commands.Choice(name="❌ 잔액 부족: 최소 1,000원 필요", value=0)
        ]

    return [
        app_commands.Choice(name=f"💰 전체 잔액 사용: {잔액:,}원", value=잔액),
        app_commands.Choice(name=f"🔟 10,000원만 투자", value=10000),
        app_commands.Choice(name=f"💯 100,000원만 투자", value=100000)
    ]


@tree.command(name="내투자", description="현재 보유 중인 투자 내역을 확인합니다", guild=discord.Object(id=GUILD_ID))
async def 내투자(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    investments = load_investments()
    my_investments = [inv for inv in investments if inv["user_id"] == user_id]

    if not my_investments:
        return await interaction.response.send_message(
            embed=create_embed("📭 투자 내역 없음", "현재 보유 중인 투자 내역이 없습니다.", discord.Color.light_grey()),
            ephemeral=True
        )

    # ✅ 모든 내역을 문자열로 묶음
    text = ""
    for inv in my_investments:
        종목 = inv["stock"]
        수량 = inv["shares"]
        단가 = inv["price_per_share"]
        시각 = inv["timestamp"].replace("T", " ")[:16]
        text += f"📈 **{종목}** | {수량}주 | {단가:,}원 | {시각}\n"

    embed = discord.Embed(
        title="📊 나의 투자 내역",
        description=text[:4000],  # Discord 메시지 제한 보호용 (최대 4096자)
        color=discord.Color.blue()
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)



@tree.command(name="투자왕", description="지금까지 가장 많은 수익을 낸 유저 랭킹", guild=discord.Object(id=GUILD_ID))
async def 투자왕(interaction: discord.Interaction):
    file_path = "investment_history.json"

    if not os.path.exists(file_path):
        return await interaction.response.send_message(
            embed=create_embed("📭 랭킹 없음", "아직 수익이 기록된 유저가 없습니다.", discord.Color.light_grey()),
            ephemeral=True
        )

    with open(file_path, "r", encoding="utf-8") as f:
        try:
            history = json.load(f)
        except json.JSONDecodeError:
            return await interaction.response.send_message(
                embed=create_embed("⚠️ 오류 발생", "수익 기록 파일을 읽을 수 없습니다.", discord.Color.red()),
                ephemeral=True
            )

    if not isinstance(history, list) or not history:
        return await interaction.response.send_message(
            embed=create_embed("📭 랭킹 없음", "아직 수익이 기록된 유저가 없습니다.", discord.Color.light_grey()),
            ephemeral=True
        )

    # ✅ 누적 수익 계산
    profits = {}
    for entry in history:
        uid = entry["user_id"]
        profits[uid] = profits.get(uid, 0) + entry.get("profit", 0)

    if not profits:
        return await interaction.response.send_message(
            embed=create_embed("📭 랭킹 없음", "아직 수익이 기록된 유저가 없습니다.", discord.Color.light_grey()),
            ephemeral=True
        )

    # ✅ 상위 10명 / 하위 3명
    top_users = sorted(profits.items(), key=lambda x: x[1], reverse=True)[:10]
    bottom_users = sorted(profits.items(), key=lambda x: x[1])[:3]

    embed = discord.Embed(title="👑 투자왕 랭킹", color=discord.Color.gold())
    guild = interaction.guild

    # 🥇 상위 10명
    embed.add_field(name="📈 상위 TOP 10", value="⠀", inline=False)
    for rank, (user_id, total_profit) in enumerate(top_users, 1):
        name = f"Unknown ({user_id})"
        try:
            member = guild.get_member(int(user_id)) or await guild.fetch_member(int(user_id))
            name = member.nick or member.name if member else name
        except Exception as e:
            print(f"❌ 사용자 정보 조회 실패: {user_id} / {e}")

        embed.add_field(
            name=f"{rank}위 - {name}",
            value=f"누적 수익: **{total_profit:,}원**",
            inline=False
        )

    # 📉 하위 3명
    embed.add_field(name="📉 하위 TOP 3 (손해왕)", value="⠀", inline=False)
    for rank, (user_id, total_profit) in enumerate(bottom_users, 1):
        name = f"Unknown ({user_id})"
        try:
            member = guild.get_member(int(user_id)) or await guild.fetch_member(int(user_id))
            name = member.nick or member.name if member else name
        except Exception as e:
            print(f"❌ 사용자 정보 조회 실패: {user_id} / {e}")

        embed.add_field(
            name=f"하위 {rank}위 - {name}",
            value=f"누적 손익: **{total_profit:,}원**",
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=False)



# ✅ 유저에게 투자 정산 결과를 DM으로 보내는 함수 (정산된 내역 기반)
async def send_investment_summary(user: discord.User, user_id: str, history: list):
    # 이 유저의 정산된 투자 내역만 필터링
    user_history = [h for h in history if h["user_id"] == user_id]

    if not user_history:
        return

    # 📉 너무 많은 종목 보유 시 상위 40개까지만 표시
    too_many = False
    if len(user_history) > 40:
        user_history = user_history[:40]
        too_many = True

    total_invested = sum(h["buy_price"] * h["shares"] for h in user_history)
    total_returned = sum(h["sell_price"] * h["shares"] for h in user_history)
    total_profit = total_returned - total_invested
    total_sign = "+" if total_profit > 0 else ""
    total_emoji = "📈" if total_profit >= 0 else "📉"

    # 전체 요약 Embed
    summary_embed = discord.Embed(
        title="📊 투자 정산 요약",
        description=(
            f"💼 총 투자금: {total_invested:,}원\n"
            f"💵 총 정산금: {total_returned:,}원\n"
            f"{total_emoji} 총 손익: {total_sign}{total_profit:,}원"
        ),
        color=discord.Color.green() if total_profit >= 0 else discord.Color.red()
    )

    # 개별 종목 정산 내역
    embeds = [summary_embed]
    current_embed = discord.Embed(title="📈 개별 종목 정산", color=discord.Color.teal())

    for i, h in enumerate(user_history):
        stock = h["stock"]
        shares = h["shares"]
        buy_price = h["buy_price"]
        sell_price = h["sell_price"]
        invested = buy_price * shares
        returned = sell_price * shares
        profit = returned - invested

        # 🧮 손익률 계산 (0 나눗셈 방지)
        if buy_price == 0:
            rate = 0.0
        else:
            rate = round((sell_price - buy_price) / buy_price * 100, 2)

        sign = "+" if profit > 0 else ""
        emoji = "🟢📈" if profit >= 0 else "🔴📉"

        # 💬 급등/급락 멘트 추가
        funny_comment = ""
        # 💬 급등/급락 멘트 추가 (rate 기준)
        if rate == 200.0:
            funny_comment = "\n🚀 *이건 그냥 로켓 아닙니까? 200% 수익이라니...*"
        elif rate == 100.0:
            funny_comment = "\n🔥 *내부자 아니죠? 100% 급등은 너무했잖아요!*"
        elif rate >= 50.0:
            funny_comment = "\n📈 *이 정도면 투자 천재 아닙니까?*"
        elif rate <= -50.0 and rate > -100.0:
            funny_comment = "\n⚠️ *이 손실은 좀... 눈물 납니다.*"
        elif rate == -100.0:
            funny_comment = "\n💣 *텅장 완료... 투자금이 증발했습니다. 🙃*"


        current_embed.add_field(
            name=f"{emoji} [{stock}] {sign}{rate}%",
            value=(
                f"🪙 보유: {shares}주\n"
                f"💰 매입가 총액: {invested:,}원\n"
                f"💵 정산 금액: {returned:,}원\n"
                f"📊 손익: {sign}{profit:,}원"
                f"{funny_comment}"
            ),
            inline=False
        )

        # 24개마다 새 Embed로 분할
        if (i + 1) % 24 == 0:
            embeds.append(current_embed)
            current_embed = discord.Embed(title="📈 개별 종목 정산 (계속)", color=discord.Color.teal())

    if len(current_embed.fields) > 0:
        if too_many:
            current_embed.set_footer(text="※ 종목이 많아 상위 40개까지만 표시됩니다.")
        embeds.append(current_embed)

    # DM 전송
    try:
        for embed in embeds:
            await user.send(embed=embed)
    except discord.Forbidden:
        print(f"❌ {user.name}님에게 DM 전송 실패 (권한 없음)")
    except discord.HTTPException as e:
        print(f"❌ {user.name}님에게 DM 전송 실패 (HTTP 오류): {e}")











def get_mention(user_id):
    return f"<@{user_id}>"

def split_message_chunks(message: str, max_length: int = 1900):
    lines = message.splitlines(keepends=True)
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) > max_length:
            chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks

MAX_STOCKS = 30  # 종목 유지 개수

def create_new_stock(stocks: dict) -> str:
    for _ in range(30):
        name = generate_random_stock_name()
        if name not in stocks:
            stocks[name] = {
                "price": random.randint(1000, 5000),
                "change": 0
            }
            return name
    return None

async def start_random_investment_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        wait_minutes = random.randint(5, 30)
        try:
            await process_investments(wait_minutes)
        except Exception as e:
            print(f"❌ process_investments 에러: {e}")

        print(f"⌛ 다음 정산은 {wait_minutes}분 후 예정")
        await asyncio.sleep(wait_minutes * 60)
        
async def process_investments(wait_minutes: int = None):
    stocks = load_stocks()
    investments = load_investments()
    new_list = []

    KST = timezone(timedelta(hours=9))
    last_chart_time = load_last_chart_time().astimezone(KST)
    now = datetime.now(KST)

    report = f"📊 [30분 주기 투자 종목 변동 - {now.strftime('%m/%d %H:%M')}]\n\n"
    split_report = ""
    total_fees_collected = 0

    purchase_fee_rate = 0.01
    sell_fee_rate = 0.01

    delisted_stocks = set()
    price_changes = {}
    change_records = {200: {}, 100: {}, 50: {}, -50: {}, -100: {}}

    for name, stock in stocks.items():
        change = generate_change()
        old_price = stock["price"]
        new_price = int(old_price * (1 + change / 100))
        price_changes[name] = (old_price, change, new_price)

    history = []
    updated_users = set()

    for inv in investments:
        user_id = inv["user_id"]
        stock = inv["stock"]
        shares = inv["shares"]
        old_price = inv["price_per_share"]
        timestamp = isoparse(inv["timestamp"]).astimezone(KST)

        if timestamp < last_chart_time:
            continue

        if timestamp < now:
            if stock in price_changes:
                prev_price, change, new_price = price_changes[stock]
                real_new_price = int(old_price * (1 + change / 100))
                if real_new_price < 1:
                    real_new_price = 1
            else:
                real_new_price = stocks[stock]["price"]

            buy_cost_per_share = int(old_price * (1 + purchase_fee_rate))
            invested = buy_cost_per_share * shares
            fee_on_buy = (buy_cost_per_share - old_price) * shares
            total_fees_collected += fee_on_buy

            sell_total = real_new_price * shares
            gross_profit = sell_total - invested
            fee_on_sell = 0
            if gross_profit > 0:
                fee_on_sell = int(sell_total * sell_fee_rate)
                sell_total -= fee_on_sell
                total_fees_collected += fee_on_sell

            profit = sell_total - invested
            add_balance(user_id, sell_total)

            if stock in price_changes:
                _, change, _ = price_changes[stock]
                if change in change_records:
                    change_records[change].setdefault(stock, []).append((user_id, profit))

            history.append({
                "user_id": user_id,
                "stock": stock,
                "shares": shares,
                "buy_price": old_price,
                "sell_price": real_new_price,
                "profit": profit,
                "timestamp": now.isoformat()
            })
            updated_users.add(user_id)
        else:
            new_list.append(inv)

    for name in list(stocks.keys()):
        if name not in price_changes:
            continue

        old_price, change, new_price = price_changes[name]

        symbol = "📈" if change > 0 else ("📉" if change < 0 else "💥" if change in [-100, 100] else "➖")
        report += f"{symbol} {name}: {change:+}% → {new_price:,}원\n"

        if change == 200:
            report += f"🚀 [{name}]이 상한가 두 배! 슈퍼급등으로 투자자 환호!\n"
        elif change == 100:
            report += f"🔥 [{name}] 급등! 내부자 냄새가 나는 100% 상승입니다!\n"
        elif change == 50:
            report += f"⏫ [{name}] 강한 상승! 50%나 뛰었습니다!\n"
        elif change == 30:
            report += f"📈 [{name}] 좋은 흐름! 안정적인 30% 상승.\n"
        elif change == -30:
            report += f"📉 [{name}] 불안한 하락세... -30% 손실.\n"
        elif change == -50:
            report += f"⚠️ [{name}] 심상치 않다... -50% 급락!\n"
        elif change == -100:
            report += f"💣 [{name}] 폭락! -100% 손실, 이제 이 주식은 기억 속으로...\n"

        if new_price < 100:
            delisted_stocks.add(name)
            del stocks[name]
            report += f"💀 [{name}] 상장폐지 (가격 < 100원)\n"
            new_name = create_new_stock(stocks)
            if new_name:
                report += f"✨ 신규 종목 상장: [{new_name}] (랜덤 생성) → {stocks[new_name]['price']:,}원\n"
        else:
            if new_price > 30_000:
                new_price = new_price // 10
                split_report += f"📣 [{name}] 주식 분할: 1주 → 10주, 가격 ↓ {old_price:,} → {new_price:,}원\n"
            stocks[name]["price"] = new_price
            stocks[name]["change"] = change

    while len(stocks) < MAX_STOCKS:
        create_new_stock(stocks)

    save_stocks(stocks)
    save_investments(new_list)
    if history:
        save_investment_history(history)

    def add_oduk_pool(amount):
        try:
            with open("oduk_pool.json", "r", encoding="utf-8") as f:
                pool = json.load(f)
        except:
            pool = {"amount": 0}
        pool["amount"] = pool.get("amount", 0) + amount
        with open("oduk_pool.json", "w", encoding="utf-8") as f:
            json.dump(pool, f, indent=2)

    add_oduk_pool(total_fees_collected)

    try:
        with open("oduk_pool.json", "r", encoding="utf-8") as f:
            pool = json.load(f)
        oduk_amount = pool.get("amount", 0)
    except:
        oduk_amount = total_fees_collected

    report += f"\n💰 이번 정산 수수료 수익: {total_fees_collected:,}원 적립\n🏦 현재 오덕잔고: {oduk_amount:,}원\n"

    if wait_minutes:
        next_time = (now + timedelta(minutes=wait_minutes)).strftime('%H:%M')
        report += f"🕓 다음 정산은 약 {wait_minutes}분 후, **{next_time}** 예정입니다.\n"
    else:
        report += "🕓 다음 정산은 **5~30분 이내 무작위 시점**에 다시 진행됩니다.\n"


    for chg in [200, 100, 50, -50, -100]:
        for stock, records in change_records[chg].items():
            label = {
                200: "🚀 [{stock}] +200% 슈퍼급등 수익자 명단",
                100: "🤑 [{stock}] +100% 상승 수익자 명단",
                50: "📈 [{stock}] +50% 상승 수익자 명단",
                -50: "😰 [{stock}] -50% 급락 손실자 명단",
                -100: "😭 [{stock}] -100% 폭락 손실자 명단"
            }[chg].format(stock=stock)
            report += f"\n{label}\n"
            for user_id, profit in records:
                sign = "+" if profit >= 0 else ""
                report += f"  {get_mention(user_id)}: {sign}{profit:,}원 {'수익' if profit >= 0 else '손실'}\n"

    if split_report:
        report += f"\n{split_report}"

    for chunk in split_message_chunks(report):
        for guild in bot.guilds:
            ch = discord.utils.get(guild.text_channels, name="오덕코인")
            if ch:
                try:
                    await ch.send(chunk)
                except Exception as e:
                    print(f"❌ 오덕코인 채널 전송 실패: {e}")

    for user_id in updated_users:
        try:
            user = await bot.fetch_user(int(user_id))
            await send_investment_summary(user, user_id, history)
        except Exception as e:
            print(f"❌ {user_id}님에게 정산 DM 전송 실패: {e}")

    save_last_chart_time(now)

# ✅ 투자 시스템 초기화 및 루프 시작
def initialize_investment_system():
    ensure_stocks_filled()

    if not os.path.exists(INVESTMENT_FILE):
        with open(INVESTMENT_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

    # ✅ 정산 루프 비동기 실행
    asyncio.create_task(start_random_investment_loop())
    print("📈 투자 정산 루프 시작됨")






def generate_change():
    r = random.random()
    if r < 0.01:
        return 200
    elif r < 0.03:
        return 100
    elif r < 0.06:
        return 50
    elif r < 0.10:
        return -100
    elif r < 0.14:
        return -50
    elif r < 0.20:
        return 30
    elif r < 0.28:
        return -30
    else:
        return random.randint(-15, 15)



@tree.command(name="오덕잔고설정", description="오덕로또 상금을 수동으로 설정합니다 (채널관리자 전용)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(금액="설정할 오덕로또 상금 금액 (0 이상)")
async def 오덕잔고설정(interaction: discord.Interaction, 금액: int):
    # ✅ 채널관리자 권한 확인
    role_names = [role.name for role in interaction.user.roles]
    if "채널관리자" not in role_names:
        return await interaction.response.send_message(
            embed=create_embed("❌ 권한 없음", "이 명령어는 **'채널관리자' 역할**만 사용할 수 있습니다.", discord.Color.red()),
            ephemeral=True
        )

    # ✅ 유효성 검사
    if 금액 < 0:
        return await interaction.response.send_message(
            embed=create_embed("⚠️ 잘못된 금액", "금액은 **0 이상**이어야 합니다.", discord.Color.orange()),
            ephemeral=True
        )

    # ✅ 오덕 로또 잔고 설정
    global oduk_pool_cache
    oduk_pool_cache = load_oduk_pool()
    oduk_pool_cache["amount"] = 금액
    save_oduk_pool(oduk_pool_cache)

    await interaction.response.send_message(
        embed=create_embed(
            "✅ 오덕잔고 설정 완료",
            f"오덕로또 상금이 **{금액:,}원**으로 설정되었습니다.",
            discord.Color.blue()
        ),
        ephemeral=False
    )






@tree.command(name="초기화", description="모든 유저의 잔액 및 기록을 초기화합니다 (채널관리자 전용)", guild=discord.Object(id=GUILD_ID))
async def 초기화(interaction: discord.Interaction):
    # ✅ 채널관리자 권한 확인
    role_names = [role.name for role in interaction.user.roles]
    if "채널관리자" not in role_names:
        return await interaction.response.send_message(
            embed=create_embed("❌ 권한 없음", "이 명령어는 **'채널관리자' 역할**만 사용할 수 있습니다.", discord.Color.red()),
            ephemeral=True
        )

    # ✅ 1. 도박 잔액 초기화
    balances = load_balances()
    for uid in balances:
        balances[uid]["amount"] = 0
        balances[uid]["last_updated"] = datetime.utcnow().isoformat()
    save_balances(balances)

    # ✅ 2. 오덕로또 데이터 초기화
    global oduk_pool_cache
    oduk_pool_cache = {
        "amount": 0,
        "last_lotto_date": "",
        "last_winner": ""
    }
    save_oduk_pool(oduk_pool_cache)
    save_oduk_lotto_entries({})

    # ✅ 3. 투자 데이터 초기화 (종목은 유지)
    save_investments([])  # 보유 주식 초기화
    save_last_chart_time(datetime.utcnow())  # 주가 갱신 기준 초기화

    # ✅ 3-1. 투자 수익 히스토리 초기화 (투자왕 기록 포함)
    with open("investment_history.json", "w", encoding="utf-8") as f:
        json.dump([], f, indent=4)

    # ✅ 4. 송금 기록 초기화
    with open("transfer_log.json", "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)

    # ✅ 5. 도박 배틀 전적 초기화
    with open("battle_stats.json", "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

    # ✅ 6. 1:1 배틀 전적 초기화
    with open("pair_stats.json", "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

    # ✅ 7. 알바 기록 초기화
    with open(ALBA_RECORD_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2)

    # ✅ 8. 은행 예금 기록 초기화
    with open("bank.json", "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2)

    # ✅ 9. 대출 기록 초기화
    with open("loan.json", "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2)

    # ✅ 10. 신용등급 및 채무 이력 초기화
    with open("loan_history.json", "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2)

    await interaction.response.send_message(
        embed=create_embed(
            "✅ 초기화 완료",
            f"총 {len(balances)}명의 잔액, 오덕로또, 투자 기록, **송금 내역**, **배틀 전적**, **알바 기록**, **은행 예금**, **대출 및 채무 기록**이 초기화되었습니다.\n※ 투자 종목은 유지됩니다.",
            discord.Color.green()
        ),
        ephemeral=False
    )





ODUK_LOTTO_ENTRIES_FILE = "oduk_lotto_entries.json"

def load_oduk_lotto_entries():
    if not os.path.exists(ODUK_LOTTO_ENTRIES_FILE):
        with open(ODUK_LOTTO_ENTRIES_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)  # ✅ 리스트로 초기화

    with open(ODUK_LOTTO_ENTRIES_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            if isinstance(data, dict):  # 혹시 이전에 dict로 잘못 저장된 경우
                print("⚠️ 잘못된 형식 감지 → 빈 리스트로 초기화됨")
                return []
            return data
        except json.JSONDecodeError:
            print("⚠️ JSON 파싱 실패 → 빈 리스트로 초기화됨")
            return []

def save_oduk_lotto_entries(data):
    with open(ODUK_LOTTO_ENTRIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)






# ✅ 자동 오덕로또 추첨 함수 (5개 일치 시 전체 몰수 처리 포함)
async def auto_oduk_lotto(force: bool = False):
    now = datetime.now(KST)
    draw_start = now - timedelta(days=1)
    draw_end = now

    all_entries = load_oduk_lotto_entries()
    filtered_entries = {}
    for record in all_entries:
        timestamp = datetime.fromisoformat(record["timestamp"])
        if draw_start <= timestamp < draw_end:
            uid = record["user_id"]
            combo = record["combo"]
            filtered_entries.setdefault(uid, []).append(combo)

    if not force and oduk_pool_cache.get("last_lotto_date") == now.date().isoformat():
        print("🟨 이미 오늘의 로또 추첨이 완료됨")
        return

    result_str = ""

    if not filtered_entries:
        result_str = "😢 오늘은 로또에 참여한 유저가 없어 상금이 이월됩니다."
    else:
        answer = sorted(random.sample(range(1, 46), 5))
        bonus = random.sample([n for n in range(1, 46) if n not in answer], 2)
        tier_super, tier1, tier2, tier3 = [], [], [], []

        for uid, combos in filtered_entries.items():
            for combo in combos:
                matched = set(combo) & set(answer)
                match = len(matched)
                has_bonus = any(b in combo for b in bonus)

                if match == 5:
                    tier_super.append(uid)
                elif match == 4:
                    tier1.append(uid)
                elif match == 3 and has_bonus:
                    tier2.append(uid)
                elif match == 3 or (match == 2 and has_bonus):
                    tier3.append(uid)

        result_str = f"🎯 정답 번호: {', '.join(map(str, answer))} + 보너스({', '.join(map(str, bonus))})\n\n"
        amount = get_oduk_pool_amount()
        lines = []
        notified_users = set()
        leftover = 0
        total_paid = 0  # ✅ 지급된 전체 금액 합산용

        guild = bot.guilds[0]

        def get_mention(uid):
            member = guild.get_member(int(uid))
            return member.mention if member else f"<@{uid}>"

        # ✅ 슈퍼 당첨자 처리 (5개 전부 맞춘 경우)
        if tier_super:
            share = amount // len(tier_super)
            leftover = amount % len(tier_super)
            total_paid = share * len(tier_super)

            for uid in tier_super:
                add_balance(uid, share)
                try:
                    user = await bot.fetch_user(int(uid))
                    await user.send(
                        f"👑 오덕로또 **5개 전부 맞춤!**\n"
                        f"정답 번호: {', '.join(map(str, answer))} + 보너스({', '.join(map(str, bonus))})\n"
                        f"💰 상금: **{share:,}원** (전액 몰수!)\n🎉 축하드립니다!"
                    )
                except:
                    pass
                notified_users.add(uid)

            mentions = ", ".join([get_mention(uid) for uid in tier_super])
            lines.append(f"👑 **전체 정답자 {len(tier_super)}명! 상금 전액 몰수!**\n  {mentions}")
            result_str += "\n".join(lines)
            result_str += f"\n\n💰 남은 이월 상금: {leftover:,}원"

        else:
            tier2_pool = int(amount * 0.2)
            tier1_pool = int(amount * 0.8)

            # ✅ 1등
            if tier1:
                share = tier1_pool // len(tier1)
                for uid in tier1:
                    add_balance(uid, share)
                    try:
                        user = await bot.fetch_user(int(uid))
                        await user.send(
                            f"🏆🎉 오덕로또 **1등** 당첨!\n"
                            f"정답 번호: {', '.join(map(str, answer))} + 보너스({', '.join(map(str, bonus))})\n"
                            f"🏆 상금: **{share:,}원**\n축하드립니다!"
                        )
                    except:
                        pass
                    notified_users.add(uid)

                leftover += tier1_pool % len(tier1)
                total_paid += share * len(tier1)

                mentions = ", ".join([get_mention(uid) for uid in tier1])
                lines.append(f"🏆 **1등** {len(tier1)}명 (4개 일치) → **1인당 {share:,}원**\n  {mentions}")
            else:
                leftover += tier1_pool
                lines.append("🏆 **1등 당첨자 없음 → 상금 이월**")

            # ✅ 2등
            if tier2:
                share = tier2_pool // len(tier2)
                for uid in tier2:
                    add_balance(uid, share)
                    try:
                        user = await bot.fetch_user(int(uid))
                        await user.send(
                            f"🥈 오덕로또 2등 당첨!\n"
                            f"정답 번호: {', '.join(map(str, answer))} + 보너스({', '.join(map(str, bonus))})\n"
                            f"🥈 상금: {share:,}원\n축하드립니다!"
                        )
                    except:
                        pass
                    notified_users.add(uid)

                leftover += tier2_pool % len(tier2)
                total_paid += share * len(tier2)

                mentions = ", ".join([get_mention(uid) for uid in tier2])
                lines.append(f"🥈 2등 {len(tier2)}명 (3개 + 보너스) → 1인당 {share:,}원\n  {mentions}")
            else:
                leftover += tier2_pool
                lines.append("🥈 2등 당첨자 없음 → 상금 이월")

            # ✅ 3등
            if tier3:
                from collections import Counter
                count_by_uid = Counter(tier3)

                for uid, count in count_by_uid.items():
                    add_balance(uid, 5000 * count)
                    total_paid += 5000 * count

                def format_mentions(counter):
                    mentions = []
                    for uid, count in counter.items():
                        mention = get_mention(uid)
                        if count > 1:
                            mentions.append(f"{mention} × {count}회")
                        else:
                            mentions.append(f"{mention}")
                    return ", ".join(mentions)

                lines.append(
                    f"🥉 3등 {len(tier3)}명 (3개 일치 또는 2개+보너스) → 1인당 5,000원\n  {format_mentions(count_by_uid)}"
                )
            else:
                lines.append("🥉 3등 당첨자 없음 → 상금 없음")

            result_str += "\n".join(lines)
            result_str += f"\n\n💰 이월된 상금: {leftover:,}원"

        # ✅ 오덕잔고에서 지급된 총금액 차감
        oduk_pool_cache["amount"] -= total_paid
        oduk_pool_cache["amount"] = max(0, oduk_pool_cache["amount"])  # 음수 방지

    if not force:
        oduk_pool_cache["last_lotto_date"] = now.date().isoformat()

    save_oduk_pool(oduk_pool_cache)
    save_oduk_lotto_entries([])

    embed_title = "📢 오덕로또 추첨 결과" if not force else "📢 [수동] 오덕로또 추첨 결과"
    embed = discord.Embed(
        title=embed_title,
        description=result_str,
        color=discord.Color.gold() if not force else discord.Color.purple()
    )

    for guild in bot.guilds:
        channel = discord.utils.get(guild.text_channels, name="오덕도박장")
        if channel:
            try:
                tag = "@everyone 오늘의 오덕로또 결과입니다!" if not force else "@everyone 테스트용 수동추첨 결과입니다!"
                await channel.send(tag, embed=embed)

                if tier_super or tier1 or tier2 or tier3:
                    fun_msg = "😎 저의 행운이 당신에게 닿았군요...\n오덕봇의 행운의 키스를! 👏👏"
                    luck_embed = discord.Embed()
                    luck_embed.set_image(url="https://raw.githubusercontent.com/Na-seunghyun/my-discord-bot/main/midium.gif")
                    await channel.send(content=fun_msg, embed=luck_embed)

            except Exception as e:
                print(f"❌ 로또 결과 전송 실패: {e}")

    print(f"✅ 오덕로또 추첨 완료됨! 정답: {answer} + 보너스({bonus})")
    print(f"👑 슈퍼당첨: {len(tier_super)}명 | 🥇 1등: {len(tier1)} | 🥈 2등: {len(tier2)} | 🥉 3등: {len(tier3)}")
    print(f"💰 이월된 상금: {leftover:,}원" + (" (수동)" if force else ""))









@tree.command(name="로또참여현황", description="오늘의 오덕로또 참여 현황을 확인합니다", guild=discord.Object(id=GUILD_ID))
async def 로또참여현황(interaction: discord.Interaction):
    now = datetime.now(KST)

    today_9am = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if now < today_9am:
        draw_end = today_9am
        draw_start = draw_end - timedelta(days=1)
    else:
        draw_start = today_9am
        draw_end = draw_start + timedelta(days=1)

    # ⏰ 남은 시간 계산
    remaining = draw_end - now
    total_minutes = remaining.total_seconds() // 60
    hours = int(total_minutes // 60)
    minutes = int(total_minutes % 60)
    time_left_str = f"{hours}시간 {minutes}분"

    all_entries = load_oduk_lotto_entries()
    filtered_entries = {}
    for record in all_entries:
        timestamp = datetime.fromisoformat(record["timestamp"])
        if draw_start <= timestamp < draw_end:
            uid = record["user_id"]
            combo = record["combo"]
            filtered_entries.setdefault(uid, []).append(combo)

    if not filtered_entries:
        return await interaction.response.send_message(
            embed=discord.Embed(
                title="📭 참여자 없음",
                description="이번 회차 로또에 아직 아무도 참여하지 않았습니다.",
                color=discord.Color.orange()),
            ephemeral=False
        )

    max_embeds = 10
    max_fields_per_embed = 25
    embeds = []
    pool_amt = get_oduk_pool_amount()
    tier1_pool = int(pool_amt * 0.8)
    tier2_pool = int(pool_amt * 0.2)

    current_embed = discord.Embed(
        title=f"🎯 오덕로또 참여 현황\n({draw_start.strftime('%m/%d %H:%M')} ~ {draw_end.strftime('%m/%d %H:%M')})",
        description=(
            "현재 회차에 참여한 유저 목록입니다.\n\n"
            f"🏆 1등 당첨 시 예상 상금: **{tier1_pool:,}원** (당첨자 1명 기준)\n"
            f"🥈 2등 당첨 시 예상 상금: **{tier2_pool:,}원** (당첨자 1명 기준)"
        ),
        color=discord.Color.teal()
    )
    field_count = 0
    embed_count = 1

    guild = interaction.guild
    total_displayed_users = 0

    for uid, combos in filtered_entries.items():
        if embed_count > max_embeds:
            break  # ❗️더 이상 embed 생성 안 함

        try:
            member = guild.get_member(int(uid))
            username = member.display_name if member else f"Unknown({uid})"
        except:
            username = f"Unknown({uid})"

        combo_count = len(combos)
        field_value = f"총 {combo_count}개 조합 참여"

        current_embed.add_field(
            name=f"👤 {username} ({combo_count}개 조합)",
            value=field_value,
            inline=False
        )
        field_count += 1
        total_displayed_users += 1

        if field_count >= max_fields_per_embed:
            current_embed.set_footer(text=f"🕘 다음 추첨까지 남은 시간: {time_left_str}")
            embeds.append(current_embed)
            current_embed = discord.Embed(color=discord.Color.teal())
            field_count = 0
            embed_count += 1

    # 마지막 embed 처리
    if field_count > 0 and embed_count <= max_embeds:
        current_embed.set_footer(text=f"🕘 다음 추첨까지 남은 시간: {time_left_str}")
        embeds.append(current_embed)

    for embed in embeds:
        await interaction.channel.send(embed=embed)

    desc_text = f"총 {len(filtered_entries)}명 참여.\n"
    if total_displayed_users < len(filtered_entries):
        desc_text += f"⚠️ 참여 인원이 많아 상위 {total_displayed_users}명까지만 표시되었습니다."

    await interaction.response.send_message(
        embed=discord.Embed(
            title="📊 참여 현황 출력됨",
            description=desc_text,
            color=discord.Color.green()
        ),
        ephemeral=True
    )











@tree.command(name="오덕로또참여", description="오덕로또에 참여합니다 (1조합당 2,000원)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(수량="1~50개의 조합 수량 선택", 수동번호들="자동 또는 6개 숫자 (예: 3,5,12,19,22,41)")
async def 오덕로또참여(interaction: discord.Interaction, 수량: int, 수동번호들: str):
    # ✅ 허용된 채널: 오덕도박장, 오덕코인
    if interaction.channel.id not in [1394331814642057418, 1394519744463245543]:
        return await interaction.response.send_message(
            "❌ 이 명령어는 **#오덕도박장** 또는 **#오덕코인** 채널에서만 사용할 수 있습니다.",
            ephemeral=True
        )

    user_id = str(interaction.user.id)
    now = datetime.now(KST)

    # ✅ 회차 계산 (오전 9시 기준)
    draw_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if now < draw_start:
        draw_start -= timedelta(days=1)
    draw_end = draw_start + timedelta(days=1)
    next_reset = draw_end

    data = load_oduk_lotto_entries()
    user_entries_today = [
        r for r in data
        if r["user_id"] == user_id and draw_start <= datetime.fromisoformat(r["timestamp"]) < draw_end
    ]

    if len(user_entries_today) + 수량 > 50:
        return await interaction.response.send_message(
            content=(
                f"❌ 참여 초과: 이번 회차에는 최대 **50조합**까지만 참여할 수 있습니다.\n"
                f"현재 {len(user_entries_today)}조합 참여 중이며, 이번 요청으로 {수량}조합은 초과됩니다.\n"
                f"⏰ 제한은 <t:{int(next_reset.timestamp())}:R>에 초기화됩니다."
            ),
            ephemeral=True
        )

    if 수량 < 1 or 수량 > 50:
        return await interaction.response.send_message(
            content="❌ 1~50개의 조합만 한 번에 참여할 수 있습니다.",
            ephemeral=True
        )

    cost = 수량 * 2000
    if get_balance(user_id) < cost:
        return await interaction.response.send_message(
            content=f"💸 잔액 부족: {수량}조합 × 2,000원 = **{cost:,}원** 필요",
            ephemeral=True
        )

    entries = []
    for _ in range(수량):
        if 수동번호들.strip().lower() == "자동":
            combo = sorted(random.sample(range(1, 46), 6))
        else:
            try:
                parts = [int(n.strip()) for n in 수동번호들.split(",")]
                if len(parts) != 6 or not all(1 <= n <= 45 for n in parts):
                    raise ValueError
                combo = sorted(parts)
            except:
                return await interaction.response.send_message(
                    content="❌ 번호 오류: 수동 입력 시 1~45 사이의 **6개 숫자**를 쉼표로 입력해주세요.",
                    ephemeral=True
                )
        entries.append(combo)

    # ✅ 처리
    add_balance(user_id, -cost)
    add_oduk_pool(cost)
    pool_amt = get_oduk_pool_amount()
    tier1_pool = int(pool_amt * 0.8)
    tier2_pool = int(pool_amt * 0.2)
    timestamp = now.isoformat()
    for combo in entries:
        data.append({
            "user_id": user_id,
            "combo": combo,
            "timestamp": timestamp
        })
    save_oduk_lotto_entries(data)

    # ✅ 일반 텍스트 메시지로 출력
    joined = "\n".join([f"🎟️ 조합 {i+1}: {', '.join(map(str, combo))}" for i, combo in enumerate(entries)])
    desc = (
        f"{수량}조합 참여 완료! 총 **{cost:,}원** 차감되었습니다.\n\n"
        f"{joined}\n\n"
        f"🍜 오덕 로또 상금: **{pool_amt:,}원** 적립됨!\n"
        f"👑 **5개 전부 일치 시 전체 상금 독식!**\n"
        f"🏆 1등(4개): **{tier1_pool:,}원**, 🥈 2등(3+보너스): **{tier2_pool:,}원**\n"
        f"🥉 3등(3개 or 2+보너스): **5,000원 고정 지급**\n"
        f"⏰ 다음 추첨: <t:{int(draw_end.timestamp())}:F>\n"
        f"🕓 제한 초기화까지: <t:{int(draw_end.timestamp())}:R>\n"
        f"🎯 매일 오전 9시에 자동 추첨됩니다!\n"
        f"\n💰 현재 잔액: {get_balance(user_id):,}원"
    )


    # ✅ 기존 참여 결과 텍스트 메시지 전송
    await interaction.response.send_message(content=desc)

    # ✅ 행운 메시지 + GIF 이미지 추가 전송
    embed = discord.Embed()
    embed.set_image(url="https://raw.githubusercontent.com/Na-seunghyun/my-discord-bot/main/midium.gif")
    await interaction.followup.send(
        content="당신에게 행운이 닿기를 🍀",
        embed=embed
    )







@tree.command(name="수동추첨", description="오덕로또를 수동으로 즉시 추첨합니다 (관리자 전용)", guild=discord.Object(id=GUILD_ID))
async def 수동추첨(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message(
            "❌ 이 명령어는 서버 관리자만 사용할 수 있습니다.",
            ephemeral=True
        )

    await interaction.response.send_message("🔁 수동 추첨을 시작합니다...", ephemeral=True)

    now = datetime.now(KST)
    draw_start = now - timedelta(days=1)
    draw_end = now

    all_entries = load_oduk_lotto_entries()
    filtered_entries = {}
    for record in all_entries:
        timestamp = datetime.fromisoformat(record["timestamp"])
        if draw_start <= timestamp < draw_end:
            uid = record["user_id"]
            combo = record["combo"]
            filtered_entries.setdefault(uid, []).append(combo)

    if not filtered_entries:
        return await interaction.followup.send("😢 참여자가 없어 수동추첨을 실행할 수 없습니다.", ephemeral=True)

    # ✅ 당첨번호 5개 + 보너스 2개
    answer = sorted(random.sample(range(1, 46), 5))
    bonus = random.sample([n for n in range(1, 46) if n not in answer], 2)
    tier_super, tier1, tier2, tier3 = [], [], [], []

    for uid, combos in filtered_entries.items():
        for combo in combos:
            matched = set(combo) & set(answer)
            match = len(matched)
            has_bonus = any(b in combo for b in bonus)

            if match == 5:
                tier_super.append(uid)
            elif match == 4:
                tier1.append(uid)
            elif match == 3 and has_bonus:
                tier2.append(uid)
            elif match == 3 or (match == 2 and has_bonus):
                tier3.append(uid)

    result_str = f"🎯 정답 번호: {', '.join(map(str, answer))} + 보너스({', '.join(map(str, bonus))})\n\n"
    amount = get_oduk_pool_amount()
    lines = []
    notified_users = set()
    leftover = 0

    guild = interaction.guild

    def get_mention(uid):
        member = guild.get_member(int(uid))
        return member.mention if member else f"<@{uid}>"

    if tier_super:
        # ✅ 슈퍼 당첨자 → 전액 몰수
        share = amount // len(tier_super)
        leftover = amount % len(tier_super)
        for uid in tier_super:
            add_balance(uid, share)
            try:
                user = await bot.fetch_user(int(uid))
                await user.send(
                    f"👑 [수동추첨] 오덕로또 **5개 전부 맞춤!**\n"
                    f"정답 번호: {', '.join(map(str, answer))} + 보너스({', '.join(map(str, bonus))})\n"
                    f"💰 상금: **{share:,}원** (전액 몰수!)\n🎉 축하드립니다!"
                )
            except:
                pass
            notified_users.add(uid)
        mentions = ", ".join([get_mention(uid) for uid in tier_super])
        lines.append(f"👑 **전체 정답자 {len(tier_super)}명! 상금 전액 몰수!**\n  {mentions}")

    else:
        tier1_pool = int(amount * 0.8)
        tier2_pool = int(amount * 0.2)

        # ✅ 1등
        if tier1:
            share = tier1_pool // len(tier1)
            for uid in tier1:
                add_balance(uid, share)
                try:
                    user = await bot.fetch_user(int(uid))
                    await user.send(
                        f"🏆🎉 [수동추첨] 오덕로또 **1등** 당첨!\n"
                        f"정답 번호: {', '.join(map(str, answer))} + 보너스({', '.join(map(str, bonus))})\n"
                        f"🏆 상금: **{share:,}원**\n축하드립니다!"
                    )
                except:
                    pass
                notified_users.add(uid)
            leftover += tier1_pool % len(tier1)
            mentions = ", ".join([get_mention(uid) for uid in tier1])
            lines.append(f"🏆 **1등** {len(tier1)}명 (4개 일치) → **1인당 {share:,}원**\n  {mentions}")
        else:
            leftover += tier1_pool
            lines.append("🏆 **1등 당첨자 없음 → 상금 이월**")

        # ✅ 2등
        if tier2:
            share = tier2_pool // len(tier2)
            for uid in tier2:
                add_balance(uid, share)
                try:
                    user = await bot.fetch_user(int(uid))
                    await user.send(
                        f"🥈 [수동추첨] 오덕로또 2등 당첨!\n"
                        f"정답 번호: {', '.join(map(str, answer))} + 보너스({', '.join(map(str, bonus))})\n"
                        f"🥈 상금: {share:,}원\n축하드립니다!"
                    )
                except:
                    pass
                notified_users.add(uid)
            leftover += tier2_pool % len(tier2)
            mentions = ", ".join([get_mention(uid) for uid in tier2])
            lines.append(f"🥈 2등 {len(tier2)}명 (3개 + 보너스) → 1인당 {share:,}원\n  {mentions}")
        else:
            leftover += tier2_pool
            lines.append("🥈 2등 당첨자 없음 → 상금 이월")

        # ✅ 3등
        if tier3:
            from collections import Counter
            counts = Counter(tier3)
            for uid, count in counts.items():
                add_balance(uid, 5000 * count)

            formatted_mentions = []
            for uid, count in counts.items():
                mention = get_mention(uid)
                if count > 1:
                    formatted_mentions.append(f"{mention} × {count}회")
                else:
                    formatted_mentions.append(mention)

            lines.append(f"🥉 3등 {len(tier3)}건 (3개 또는 2개+보너스) → 1인당 5,000원\n  {', '.join(formatted_mentions)}")
        else:
            lines.append("🥉 3등 당첨자 없음 → 상금 없음")

    result_str += "\n".join(lines)
    result_str += f"\n\n💰 이월된 상금: {leftover:,}원"

    # ✅ 저장 (날짜 저장 안 함)
    oduk_pool_cache["amount"] = leftover
    save_oduk_pool(oduk_pool_cache)
    save_oduk_lotto_entries([])

    embed = discord.Embed(
        title="📢 [수동] 오덕로또 추첨 결과",
        description=result_str,
        color=discord.Color.purple()
    )

    for guild in bot.guilds:
        channel = discord.utils.get(guild.text_channels, name="오덕도박장")
        if channel:
            try:
                await channel.send("@everyone 테스트용 수동추첨 결과입니다!", embed=embed)
            except Exception as e:
                print(f"❌ 수동추첨 결과 전송 실패: {e}")

    print("✅ 수동추첨 완료됨")





from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))

@tree.command(name="추첨확인", description="다음 오덕로또 추첨까지 남은 시간을 확인합니다", guild=discord.Object(id=GUILD_ID))
async def 추첨확인(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    now = datetime.now(KST)

    # 🕘 다음 추첨 시각 계산
    next_draw = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if now >= next_draw:
        next_draw += timedelta(days=1)
    prev_draw = next_draw - timedelta(days=1)

    unix_ts = int(next_draw.timestamp())

    # 🎟️ 참여 기록 불러오기
    data = load_oduk_lotto_entries()
    participant_ids = {
        record["user_id"]
        for record in data
        if "timestamp" in record
        and prev_draw <= datetime.fromisoformat(record["timestamp"]) < next_draw
    }

    count = len(participant_ids)
    status = "✅ 정상 진행 예정 (참여자 있음)" if count > 0 else "⚠️ 참여자가 없어 추첨이 생략될 수 있습니다."

    # 💰 오덕로또 잔고 불러오기
    oduk_pool = load_oduk_pool()
    current_pool = oduk_pool.get("amount", 0)

    embed = discord.Embed(
        title="🎯 오덕로또 추첨 상태 확인",
        description=(
            f"⏰ **다음 추첨 예정**: <t:{unix_ts}:F> | ⏳ <t:{unix_ts}:R>\n"
            f"{status}\n"
            f"👥 이번 회차 참여 인원 수: {count}명\n"
            f"💰 현재 오덕로또 상금: **{current_pool:,}원**"
        ),
        color=discord.Color.orange()
    )

    await interaction.followup.send(embed=embed)





from discord.ext import tasks
from datetime import datetime

# 📡 핑 모니터링 경고 기준 (ms 단위)
PING_WARNING = 230
PING_CRITICAL = 400

# ⏱️ 각각의 알림 시간 (중복 방지용)
last_warning_alert_time = None
last_critical_alert_time = None

@tasks.loop(seconds=60)  # 매 1분마다 확인
async def monitor_discord_ping():
    global last_warning_alert_time, last_critical_alert_time

    ping_ms = round(bot.latency * 1000)
    now = datetime.utcnow()

    # 230ms 미만이면 정상 → 아무것도 안 함
    if ping_ms < PING_WARNING:
        return

    # 🚨 심각 경고
    if ping_ms >= PING_CRITICAL:
        if last_critical_alert_time and (now - last_critical_alert_time).total_seconds() < 1800:
            return  # 30분 내 중복 차단
        last_critical_alert_time = now
        level = "🚨 **심각**"
        color = discord.Color.red()

    # ⚠️ 주의 경고
    elif ping_ms >= PING_WARNING:
        if last_warning_alert_time and (now - last_warning_alert_time).total_seconds() < 1800:
            return  # 30분 내 중복 차단
        last_warning_alert_time = now
        level = "⚠️ **주의**"
        color = discord.Color.orange()

    # 📢 자유채팅방에 메시지 전송
    for guild in bot.guilds:
        channel = discord.utils.get(guild.text_channels, name="봇알림")
        if channel:
            embed = discord.Embed(
                title=f"{level} 디스코드 핑 지연 감지",
                description=(
                    f"현재 서버의 디스코드 API 핑이 **{ping_ms}ms**로 지연되고 있습니다.\n\n"
                    "명령어 반응 지연 또는 음성 끊김 현상이 발생할 수 있습니다.\n"
                    "잠시 후 다시 정상화될 수 있어요!, 토끼록끼는 핑에 예민해요"
                ),
                color=color
            )
            embed.set_footer(text="🛰️ 오덕봇 자동 모니터링 시스템")
            await channel.send(embed=embed)
            

TRANSFER_LOG_FILE = "transfer_log.json"

def load_transfer_logs():
    if not os.path.exists(TRANSFER_LOG_FILE):
        with open(TRANSFER_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)  # ✅ 빈 리스트로 초기화
    with open(TRANSFER_LOG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_transfer_logs(data):
    with open(TRANSFER_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def log_transfer(sender_id, receiver_id, amount):
    logs = load_transfer_logs()

    now = datetime.now(timezone(timedelta(hours=9)))
    cutoff = now - timedelta(days=10)

    # 🔥 오래된 기록 제거 (10일 이전)
    logs = [
        log for log in logs
        if datetime.fromisoformat(log["timestamp"]) >= cutoff
    ]

    # 🆕 새로운 기록 추가
    logs.append({
        "sender": str(sender_id),
        "receiver": str(receiver_id),
        "amount": amount,
        "timestamp": now.isoformat()
    })

    save_transfer_logs(logs)


@tree.command(name="송금확인", description="해당 유저의 송금 내역을 확인합니다", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(대상="송금 기록을 확인할 유저")
async def 송금확인(interaction: discord.Interaction, 대상: discord.User):
    target_id = str(대상.id)
    logs = load_transfer_logs()

    now = datetime.now(timezone(timedelta(hours=9)))
    summary = {}
    recent = []

    for record in logs:
        if record["sender"] == target_id:
            receiver = record["receiver"]
            amount = record["amount"]
            ts = datetime.fromisoformat(record["timestamp"])

            # 총합 누적
            summary[receiver] = summary.get(receiver, 0) + amount

            # 최근 5일 이내 로그 누적
            if now - ts <= timedelta(days=5):
                recent.append((receiver, amount, ts))

    if not summary:
        return await interaction.response.send_message(
            embed=discord.Embed(
                title="📭 송금 기록 없음",
                description=f"{대상.mention}님의 송금 기록이 없습니다.",
                color=discord.Color.light_grey()
            ), ephemeral=True
        )

    # ⬆️ 총합 파트
    desc = f"📤 {대상.mention}님의 송금 기록 요약\n\n"
    for uid, total in summary.items():
        desc += f"👤 <@{uid}>님에게 총 {total:,}원\n"

    # ⬇️ 최근 5일간 로그 파트
    if recent:
        desc += f"\n📅 최근 5일간 송금 내역:\n"
        recent_sorted = sorted(recent, key=lambda x: x[2], reverse=True)
        for uid, amount, ts in recent_sorted:
            desc += f"- <@{uid}>님에게 {amount:,}원 | {ts.strftime('%Y-%m-%d %H:%M')}\n"

    # 길이 초과 방지
    chunks = split_message_chunks(desc)
    for i, chunk in enumerate(chunks):
        if i == 0:
            await interaction.response.send_message(chunk)  # ✅ 공개
        else:
            await interaction.followup.send(chunk)          # ✅ 공개


ALBA_RECORD_FILE = "job_record.json"


TYPING_PHRASES = [
    "디스코드는 전세계 게이머를 위한 최고의 음성채팅 서비스입니다.",
    "성공은 작은 노력이 반복될 때 이루어집니다.",
    "우리는 모두 자신의 삶의 주인공입니다.",
    "파이썬은 간결하고 읽기 쉬운 문법으로 많은 사랑을 받고 있습니다.",
    "아침에 일어나서 차 한잔의 여유를 즐기는 것이 삶의 행복입니다.",
    "프로그래밍은 논리와 창의력을 동시에 요구하는 멋진 작업입니다.",
    "햇살 좋은 날에는 산책을 나가 마음의 여유를 가져보세요.",
    "책 한 권이 인생을 바꿀 수도 있습니다.",
    "노력은 배신하지 않는다는 말은 진리입니다.",
    "건강은 가장 소중한 자산입니다.",
    "꾸준함은 천재를 이깁니다.",
    "자신을 믿는 것이 성공의 첫걸음입니다.",
    "모든 일에는 때가 있습니다.",
    "실패는 성공의 어머니입니다.",
    "행복은 멀리 있지 않고 마음속에 있습니다.",
    "친절한 말 한마디가 큰 위로가 됩니다.",
    "꿈을 이루기 위해서는 행동이 필요합니다.",
    "오늘의 선택이 내일의 나를 만듭니다.",
    "시간은 누구에게나 공평하게 주어집니다.",
    "정직은 최고의 전략입니다.",
    "아무리 바빠도 가족을 챙기는 마음이 중요합니다.",
    "하루에 한 번은 자신을 칭찬해 주세요.",
    "삶은 짧고 예술은 길다.",
    "언제나 배우는 자세를 유지해야 합니다.",
    "감정은 통제할 수 있어야 합니다.",
    "자연은 위대한 스승입니다.",
    "기회는 준비된 자에게 찾아옵니다.",
    "지금 이 순간을 즐기세요.",
    "완벽보다 성장이 중요합니다.",
    "가끔은 아무것도 하지 않는 것도 필요합니다."
]
# ✅ 현재 주차 태그 (KST 기준)
def get_current_week_tag():
    now = datetime.now(KST)
    year, week, _ = now.isocalendar()
    return f"{year}-W{week}"

# ✅ 기록 로딩/저장
def load_job_records():
    if not os.path.exists(ALBA_RECORD_FILE):
        return {}
    with open(ALBA_RECORD_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_job_records(data):
    with open(ALBA_RECORD_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ✅ 기록 업데이트 함수 (성공/실패/초과근무 포함)
def update_job_record(user_id: str, reward: int, job_type: str = "default", *, success: bool = True, over_limit: bool = False):
    now = datetime.now(KST)
    current_week = get_current_week_tag()
    today = now.date().isoformat()
    data = load_job_records()

    record = data.get(user_id, {
        "week": current_week,
        "count": 0,
        "failures": 0,
        "limit_exceeded": 0,
        "attempts": 0,
        "total_earned": 0,
        "last_time": "",
        "daily": {},
        "types": {}
    })

    if record.get("week") != current_week:
        record = {
            "week": current_week,
            "count": 0,
            "failures": 0,
            "limit_exceeded": 0,
            "attempts": 0,
            "total_earned": 0,
            "last_time": "",
            "daily": {},
            "types": {}
        }

    record["attempts"] += 1

    if job_type not in record["types"]:
        record["types"][job_type] = {"success": 0, "fail": 0}

    # ✅ 오늘 횟수 확인
    today_count = record.get("daily", {}).get(today, 0)
    if success and not over_limit:
        if today_count >= 5:
            # ✅ 초과근무로 간주하고 False 반환
            return False

        # ✅ 정상 성공 기록
        record["count"] += 1
        record["total_earned"] += reward
        record["last_time"] = now.isoformat()

        daily = record.get("daily", {})
        daily[today] = today_count + 1
        record["daily"] = daily

        record["types"][job_type]["success"] += 1

    elif over_limit:
        record["limit_exceeded"] += 1
        record["types"][job_type]["fail"] += 1

    else:
        record["failures"] += 1
        record["types"][job_type]["fail"] += 1

    data[user_id] = record
    save_job_records(data)

    return success and not over_limit





# ✅ 잔액 함수는 네 기존 코드 사용
def add_balance(user_id, amount):
    current = get_balance(user_id)
    set_balance(user_id, current + amount)


# ✅ /타자알바 명령어
@tree.command(name="타자알바", description="문장을 빠르게 입력해 돈을 벌어보세요!", guild=discord.Object(id=GUILD_ID))
async def 타자알바(interaction: discord.Interaction):
    if interaction.channel.id not in [1394331814642057418, 1394519744463245543]:
        return await interaction.response.send_message(
            "❌ 이 명령어는 **#오덕도박장** 또는 **#오덕코인** 채널에서만 사용할 수 있습니다.",
            ephemeral=True
        )

    user_id = str(interaction.user.id)
    today = datetime.now(KST).date().isoformat()
    phrase = random.choice(TYPING_PHRASES)

    await interaction.response.send_message(
        f"📋 다음 문장을 **정확히** 입력해주세요. (20초 제한)\n\n```{phrase}```",
        ephemeral=True
    )

    def check(m: discord.Message):
        return m.author.id == interaction.user.id and m.channel == interaction.channel

    try:
        start_time = datetime.now(KST)
        msg = await bot.wait_for("message", timeout=20.0, check=check)
        end_time = datetime.now(KST)

        if msg.content.strip() != phrase:
            update_job_record(user_id, 0, job_type="default", success=False)  # ✅ 실패 기록
            await msg.reply("❌ 문장이 틀렸습니다. 알바 실패!", mention_author=False)
            return

        elapsed = (end_time - start_time).total_seconds()
        base_reward = 1200
        penalty = int(elapsed * 60)
        reward = max(120, base_reward - penalty)

        if random.random() < 0.01:
            reward *= 3
            is_jackpot = True
        else:
            is_jackpot = False

        # ✅ 초과근무 여부 기록
        success = update_job_record(user_id, reward, job_type="default")
        if not success:
            update_job_record(user_id, reward, job_type="default", over_limit=True)

            add_oduk_pool(reward)
            pool_amount = get_oduk_pool_amount()

            if random.random() < 0.4:
                compensation = reward // 2
                add_balance(user_id, compensation)
                return await msg.reply(
                    f"💢 초과근무를 했지만 악덕 오덕사장이 알바비 **{reward:,}원**을 가로채려 했습니다...\n"
                    f"⚖️ 하지만 고용노동부에 **신고에 성공하여**, 알바비 절반인 **{compensation:,}원**을 되찾았습니다!\n"
                    f"💼 노동자의 정당한 권리는 반드시 지켜져야 합니다!",
                    mention_author=False
                )

            return await msg.reply(
                f"💢 초과근무를 했지만 악덕 오덕사장이 알바비 **{reward:,}원**을 가로챘습니다...\n"
                f"💰 알바비는 모두 **오덕로또 상금 풀**에 적립되었습니다.\n"
                f"🏦 현재 오덕잔고: **{pool_amount:,}원**\n"
                f"🎟️ `/오덕로또참여`로 복수의 기회를 노려보세요!",
                mention_author=False
            )

        add_balance(user_id, reward)

        record = load_job_records().get(user_id, {})
        today_used = record.get("daily", {}).get(today, 0)
        remaining = max(0, 5 - today_used)

        message = (
            f"✅ **{elapsed:.1f}초** 만에 성공!\n"
            f"💰 **{reward:,}원**을 획득했습니다."
        )
        if is_jackpot:
            message += "\n🎉 **성실 알바생 임명! 사장님의 은혜로 알바비를 3배 지급합니다.** 🎉"
        message += f"\n📌 오늘 남은 알바 가능 횟수: **{remaining}회** (총 5회 중)"

        await msg.reply(message, mention_author=False)

    except asyncio.TimeoutError:
        update_job_record(user_id, 0, job_type="default", success=False)  # ✅ 시간 초과 실패 기록
        await interaction.followup.send("⌛️ 시간이 초과되었습니다. 알바 실패!", ephemeral=True)







# ✅ /알바기록 명령어
@tree.command(name="알바기록", description="이번 주의 알바 참여 기록을 확인합니다.", guild=discord.Object(id=GUILD_ID))
async def 알바기록(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    current_week = get_current_week_tag()
    data = load_job_records()
    record = data.get(user_id)

    if not record or record.get("week") != current_week:
        return await interaction.response.send_message("🙅 이번 주 알바 기록이 없습니다.")

    last_time = datetime.fromisoformat(record["last_time"]).astimezone(KST)
    time_str = last_time.strftime("%Y-%m-%d %H:%M:%S")

    type_lines = []
    for job_type, stat in record.get("types", {}).items():
        name = {
            "default": "타자알바",
            "box": "박스알바"
        }.get(job_type, job_type)

        s = stat.get("success", 0)
        f = stat.get("fail", 0)
        type_lines.append(f"- {name}: 시도 {s + f}회 (✅ {s} / ❌ {f})")

    type_summary = "\n".join(type_lines) or "- 없음"

    await interaction.response.send_message(
        f"📝 **{interaction.user.display_name}님의 이번 주 알바 기록**\n"
        f"📆 주차: {record['week']}\n"
        f"- 총 시도 횟수: {record.get('attempts', 0)}회\n"
        f"- 성공: ✅ {record.get('count', 0)}회\n"
        f"- 실패: ❌ {record.get('failures', 0)}회\n"
        f"- 제한 초과 시도: 🚫 {record.get('limit_exceeded', 0)}회\n"
        f"{type_summary}\n"
        f"- 누적 수익: 💰 {record['total_earned']:,}원\n"
        f"- 마지막 알바: {time_str} (KST)",
        ephemeral=False  # 전체 공개
    )



@tree.command(name="초대기록", description="현재 초대 코드 기록을 확인합니다.", guild=discord.Object(id=GUILD_ID))
async def 초대기록(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    guild_id = str(interaction.guild.id)
    cache = invites_cache.get(guild_id)

    if not cache:
        return await interaction.followup.send("❌ 현재 이 서버에 저장된 초대 기록이 없습니다.", ephemeral=True)

    lines = []
    for code, data in cache.items():
        uses = data.get("uses", 0)
        inviter_id = data.get("inviter_id")
        inviter = get_mention(inviter_id) if inviter_id else "알 수 없음"
        lines.append(f"🔗 코드 `{code}`: {uses}회 사용됨 / 초대자: {inviter}")

    msg = "\n".join(lines)
    chunks = split_message_chunks(msg)

    for part in chunks:
        await interaction.followup.send(part, ephemeral=True)



# ✅ 이스터에그 파일 초기화
EASTER_EGG_FILE = "easter_eggs.json"
EASTER_EGG_DEFS_FILE = "easter_egg_defs.json"


default_easter_egg_data = {}
default_easter_egg_defs = {
    "reaction_god": ["⚡ 반사신경의 신", "1초 내 정답 클릭"],
    "slow_but_accurate": ["🐢 느림의 미학", "7초 이상 후 정답 클릭"],
    "midnight_worker": ["🌙 자정근무자", "00시~00시10분 사이에 알바 성공"],
    "cat_finder": ["🐱 냥이탐지자", "🐱이 포함된 화면에서 성공"],
    "bomb_defuser": ["💣 폭탄처리반", "💣이 포함된 화면에서 성공"],
    "perfect_luck": ["🍀 행운의 신", "잭팟 성공"],
    "999_clicks": ["🧱 한계돌파", "누적 박스알바 999회 달성"],
    "suffer_master": ["🔥 고통에 익숙한 자", "50회 이상 시도 / 성공률 10% 이하"],
    "perfect_day": ["🎯 마침표의 미학", "하루 5회 알바 성공 완료"],
    "bomb_expert": ["💥 위기관리 전문가", "💣 4개 이상 포함된 화면에서 성공"]
}

def load_easter_egg_data():
    if not os.path.exists(EASTER_EGG_FILE):
        return {}
    with open(EASTER_EGG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_easter_egg_data(data):
    with open(EASTER_EGG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def check_box_job_easter_eggs(user_id, is_jackpot, view_buttons, reward, click_time, start_time):
    earned = []
    data = load_easter_egg_data()
    user_data = data.setdefault(user_id, {"eggs": [], "current_title": None})

    def earn(egg_id):
        if egg_id not in user_data["eggs"]:
            user_data["eggs"].append(egg_id)
            earned.append(egg_id)

    # ✅ 1초 이내 반응
    if (click_time - start_time).total_seconds() <= 1:
        earn("reaction_god")

    # ✅ 7초 이상 반응
    if (click_time - start_time).total_seconds() >= 7:
        earn("slow_but_accurate")

    # ✅ 자정 근무자
    if click_time.hour == 0 and click_time.minute < 10:
        earn("midnight_worker")

    # ✅ 화면에 🐱 있고 성공
    if "🐱" in view_buttons:
        earn("cat_finder")

    # ✅ 화면에 💣 있고 성공
    if "💣" in view_buttons:
        earn("bomb_defuser")

    # ✅ 💣이 4개 이상이면 폭탄전문가
    if view_buttons.count("💣") >= 4:
        earn("bomb_expert")

    # ✅ 잭팟 성공
    if is_jackpot:
        earn("perfect_luck")

    # ✅ 누적 999회 시도
    records = load_job_records().get(user_id, {})
    if records.get("weekly", {}).get("box", {}).get("total", 0) >= 999:
        earn("999_clicks")

    # ✅ 50회 이상 시도, 성공률 10% 이하
    job_data = records.get("weekly", {}).get("box", {})
    if job_data.get("total", 0) >= 50 and job_data.get("success", 0) / job_data["total"] <= 0.1:
        earn("suffer_master")

    # ✅ 하루 5회 성공
    today = datetime.now(KST).date().isoformat()
    if records.get("daily_success", {}).get(today, 0) >= 5:
        earn("perfect_day")

    save_easter_egg_data(data)

    
    return earned





# ✅ 파일이 없을 때만 생성
if not os.path.exists(EASTER_EGG_FILE):
    with open(EASTER_EGG_FILE, "w", encoding="utf-8") as f:
        json.dump(default_easter_egg_data, f, indent=2, ensure_ascii=False)

if not os.path.exists(EASTER_EGG_DEFS_FILE):
    with open(EASTER_EGG_DEFS_FILE, "w", encoding="utf-8") as f:
        json.dump(default_easter_egg_defs, f, indent=2, ensure_ascii=False)

def initialize_easter_egg_files():
    if not os.path.exists(EASTER_EGG_FILE):
        with open(EASTER_EGG_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2, ensure_ascii=False)

    if not os.path.exists(EASTER_EGG_DEFS_FILE):
        with open(EASTER_EGG_DEFS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_easter_egg_defs, f, indent=2, ensure_ascii=False)

# 봇 실행 시 한 번만 호출
initialize_easter_egg_files()




# ✅ 박스알바 버튼 정의
class BoxButton(discord.ui.Button):
    def __init__(self, label, is_correct):
        super().__init__(style=discord.ButtonStyle.primary, label=label)
        self.is_correct = is_correct

    async def callback(self, interaction: discord.Interaction):
        view: discord.ui.View = self.view
        if view.already_clicked:
            return await interaction.response.send_message("⛔ 이미 누른 버튼입니다!", ephemeral=True)

        view.already_clicked = True
        user_id = str(interaction.user.id)

        # ❌ 오답 처리
        if not self.is_correct:
            update_job_record(user_id, 0, job_type="box", success=False)
            return await interaction.response.edit_message(
                content="💥 오답! 박스가 아닌 걸 치웠어요...\n❌ 알바 실패!",
                view=None
            )

        # ✅ 정답 처리
        reward = random.randint(500, 1500)
        is_jackpot = False
        if random.random() < 0.05:
            reward *= 2
            is_jackpot = True

        success = update_job_record(user_id, reward, job_type="box")
        click_time = datetime.now(KST)
        view_buttons = [btn.label for btn in view.children if isinstance(btn, BoxButton)]
        easter_eggs = check_box_job_easter_eggs(
            user_id=user_id,
            is_jackpot=is_jackpot,
            view_buttons=view_buttons,
            reward=reward,
            click_time=click_time,
            start_time=getattr(view, "start_time", datetime.now(KST))
        )

        # ✅ 초과근무 처리
        if not success:
            update_job_record(user_id, reward, job_type="box", over_limit=True)
            add_oduk_pool(reward)
            pool_amount = get_oduk_pool_amount()

            if random.random() < 0.8:
                compensation = int(reward * 0.8)
                add_balance(user_id, compensation)
                msg = (
                    f"💢 초과근무를 했지만 악덕 오덕사장이 알바비 **{reward:,}원**을 가로챘습니다...\n"
                    f"⚖️ 고용노동부 신고 성공! **{compensation:,}원**을 되찾았습니다!\n"
                    f"🏦 현재 오덕잔고: **{pool_amount:,}원**\n"
                    f"🎟️ `/오덕로또참여`로 복수의 기회를 노려보세요!"
                )
            else:
                msg = (
                    f"💢 초과근무를 했지만 악덕 오덕사장이 알바비 **{reward:,}원**을 가로챘습니다...\n"
                    f"💰 알바비는 모두 **오덕로또 상금 풀**에 적립되었습니다.\n"
                    f"🏦 현재 오덕잔고: **{pool_amount:,}원**\n"
                    f"🎟️ `/오덕로또참여`로 복수의 기회를 노려보세요!"
                )

        else:
            # ✅ 정상 보상
            add_balance(user_id, reward)
            msg = f"📦 박스를 정확히 치웠습니다! 💰 **{reward:,}원** 획득!"
            if is_jackpot:
                msg += "\n🎉 **우수 알바생! 보너스 지급으로 2배 보상!** 🎉"

        # ✅ 공통 메시지: 알바 가능 횟수
        today = datetime.now(KST).date().isoformat()
        record = load_job_records().get(user_id, {})
        today_used = record.get("daily", {}).get(today, 0)
        remaining = max(0, 5 - today_used)
        msg += f"\n📌 오늘 남은 알바 가능 횟수: **{remaining}회** (총 5회 중)"

        # ✅ 이스터에그 칭호 메시지 추가
        if easter_eggs:
            msg += "\n\n🥚 **이스터에그 발견!**"
            for egg in easter_eggs:
                match egg:
                    case "reaction_god":
                        msg += "\n⚡ 반사신경의 신: 1초 내 클릭!"
                    case "slow_but_accurate":
                        msg += "\n🐢 느림의 미학: 느리지만 정확한 클릭!"
                    case "midnight_worker":
                        msg += "\n🌙 자정근무자: 00시의 성실한 알바!"
                    case "cat_finder":
                        msg += "\n🐱 냥이탐지자: 고양이도 함께 일했습니다!"
                    case "bomb_defuser":
                        msg += "\n💣 폭탄처리반: 위험 속의 승리!"
                    case "perfect_luck":
                        msg += "\n🍀 행운의 신: 잭팟까지 터졌습니다!"
                    case "999_clicks":
                        msg += "\n🧱 한계돌파: 999회 도달!"
                    case "suffer_master":
                        msg += "\n🔥 고통에 익숙한 자: 실패 속의 성공!"
                    case "perfect_day":
                        msg += "\n🎯 마침표의 미학: 완벽한 하루 알바 마감!"
                    case "bomb_expert":
                        msg += "\n💥 위기관리 전문가: 💣 4개 속에서도 정답!"

        await interaction.response.edit_message(content=msg, view=None)




# ✅ 박스알바 UI View 정의
class BoxJobView(discord.ui.View):
    def __init__(self, interaction):
        super().__init__(timeout=10)
        self.already_clicked = False
        self.interaction = interaction  # ✅ 저장

        self.start_time = datetime.now(KST)  # ✅ 클릭 타이밍 분석용 (반응속도 측정용)

        items = [
            ("📦", True),
            ("🗑️", False),
            ("💣", False),
            ("📦", True),
            ("🐱", False),
            ("🧽", False)
        ]
        random.shuffle(items)
        for emoji, correct in items[:5]:
            self.add_item(BoxButton(label=emoji, is_correct=correct))


    async def on_timeout(self):
        if not self.already_clicked:
            user_id = str(self.interaction.user.id)
            update_job_record(user_id, 0, job_type="box", success=False)
            await self.message.edit(content="⌛️ 시간 초과! 알바 실패!", view=None)



# ✅ 박스알바 명령어 등록
@tree.command(name="박스알바", description="박스를 정확히 클릭해 알바비를 벌어보세요!", guild=discord.Object(id=GUILD_ID))
async def 박스알바(interaction: discord.Interaction):
    if interaction.channel.id not in [1394331814642057418, 1394519744463245543]:
        return await interaction.response.send_message(
            "❌ 이 명령어는 **#오덕도박장** 또는 **#오덕코인** 채널에서만 사용할 수 있습니다.",
            ephemeral=True
        )

    view = BoxJobView(interaction)  # ✅ 전달

    await interaction.response.send_message(
        "📦 **박스를 치워주세요!** (10초 이내, 실수하면 실패!)", view=view, ephemeral=True
    )
    view.message = await interaction.original_response()








import os
import json
from datetime import datetime, timedelta, timezone

# ✅ 설정
BANK_FILE = "bank.json"
KST = timezone(timedelta(hours=9))

# ✅ 은행 데이터 로드
def load_bank_data():
    if not os.path.exists(BANK_FILE):
        return {}
    try:
        with open(BANK_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("⚠️ bank.json이 손상되었습니다. 빈 구조로 복구합니다.")
        return {}

# ✅ 은행 데이터 저장
def save_bank_data(data):
    with open(BANK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# ✅ 전체 은행 잔고 계산 (사용되지 않은 총합)
def get_total_bank_balance(user_id):
    bank = load_bank_data()
    user_data = bank.get(str(user_id), {"deposits": []})
    return sum(d["amount"] - d.get("used", 0) for d in user_data.get("deposits", []))


def reset_bank_deposits(user_id):
    bank = load_bank_data()
    if str(user_id) in bank:
        del bank[str(user_id)]
        save_bank_data(bank)




# ✅ 예금 추가
def add_bank_deposit(user_id, amount):
    bank = load_bank_data()
    uid = str(user_id)
    deposit = {
        "amount": amount,
        "timestamp": datetime.utcnow().isoformat(),
        "used": 0
    }
    if uid not in bank:
        bank[uid] = {"deposits": []}
    bank[uid]["deposits"].append(deposit)
    save_bank_data(bank)

# ✅ 출금 처리 및 이자 계산
def process_bank_withdraw(user_id, amount):
    bank = load_bank_data()
    uid = str(user_id)
    deposits = bank.get(uid, {}).get("deposits", [])
    remaining = amount
    interest_total = 0
    now = datetime.utcnow()

    updated_deposits = []

    for d in deposits:
        available = d["amount"] - d.get("used", 0)
        if available <= 0:
            updated_deposits.append(d)
            continue

        take = min(available, remaining)
        d["used"] = d.get("used", 0) + take
        remaining -= take

        deposit_time = datetime.fromisoformat(d["timestamp"])
        if now - deposit_time >= timedelta(hours=3):
            interest = int(take * 0.02)
            interest_total += interest

        updated_deposits.append(d)

        if remaining <= 0:
            continue  # 🔄 기존 break → continue로 수정

    # 사용되지 않은 예금만 유지
    bank[uid]["deposits"] = [
        d for d in updated_deposits if (d["amount"] - d.get("used", 0)) > 0
    ]
    save_bank_data(bank)

    # 이자 한도 및 세금
    interest_total = min(interest_total, 500_000)
    tax = int(interest_total * 0.1)
    net_interest = interest_total - tax
    return net_interest, tax

# ✅ 대출 상환용 출금 처리 (이자 계산 없음)
def withdraw_from_bank(user_id, amount):
    bank = load_bank_data()
    uid = str(user_id)
    deposits = bank.get(uid, {}).get("deposits", [])
    remaining = amount

    updated_deposits = []

    for d in deposits:
        available = d["amount"] - d.get("used", 0)
        if available <= 0:
            updated_deposits.append(d)
            continue

        take = min(available, remaining)
        d["used"] = d.get("used", 0) + take
        remaining -= take
        updated_deposits.append(d)

        if remaining <= 0:
            break

    # 사용된 예금 제거
    bank[uid]["deposits"] = [
        d for d in updated_deposits if (d["amount"] - d.get("used", 0)) > 0
    ]
    save_bank_data(bank)



# ✅ 가장 빠른 이자 수령 가능 시각 반환 (KST 기준)
def get_next_interest_time(user_id):
    bank = load_bank_data()
    uid = str(user_id)
    deposits = bank.get(uid, {}).get("deposits", [])
    next_times = []
    for d in deposits:
        available = d["amount"] - d.get("used", 0)
        if available > 0:
            ts = datetime.fromisoformat(d["timestamp"]).replace(tzinfo=timezone.utc).astimezone(KST)
            next_times.append(ts + timedelta(hours=3))
    if not next_times:
        return None
    return min(next_times)

async def apply_bank_depreciation(bot):
    bank = load_bank_data()
    updated = False
    total_cut = 0
    affected_users = []

    for user_id, user_data in bank.items():
        total_balance = sum(d["amount"] - d.get("used", 0) for d in user_data.get("deposits", []))

        if total_balance > 5_000_000:
            # ✅ 초과분의 절반만 감가, 최소 5백 만 원 보장
            excess = total_balance - 5_000_000
            to_cut = int(excess * 0.2)  # ✅ 20% 감가
            target_after_cut = total_balance - to_cut

            remaining_cut = to_cut
            updated_deposits = []

            for deposit in sorted(user_data["deposits"], key=lambda d: d["timestamp"]):
                available = deposit["amount"] - deposit.get("used", 0)
                if available <= 0:
                    updated_deposits.append(deposit)
                    continue

                reduce = min(available, remaining_cut)
                deposit["used"] = deposit.get("used", 0) + reduce
                remaining_cut -= reduce

                updated_deposits.append(deposit)
                if remaining_cut <= 0:
                    break

            bank[user_id]["deposits"] = [
                d for d in updated_deposits if (d["amount"] - d.get("used", 0)) > 0
            ]
            updated = True
            total_cut += to_cut
            affected_users.append((user_id, to_cut))
            print(f"🏦 감가 적용: {user_id} → {to_cut:,}원 차감됨")

    if updated:
        save_bank_data(bank)

        # ✅ 알림 채널로 메시지 전송
        channel = discord.utils.get(bot.get_all_channels(), name="오덕도박장")
        if channel:
            lines = [f"🏦 **은행 감가 정산 결과**"]
            for uid, cut in affected_users:
                user = await fetch_user_safe(uid)
                name = user.display_name if user else f"ID:{uid}"
                lines.append(f"- {name}님: **{cut:,}원** 차감됨")
            lines.append(f"\n📉 총 차감액: **{total_cut:,}원**")
            await channel.send("\n".join(lines))

@tasks.loop(hours=6)
async def auto_apply_maintenance():
    print("🕓 자산 유지비 정산 시작")
    await apply_maintenance_costs(bot)           # ✅ await 추가!
    await apply_bank_depreciation(bot)           # 이미 정상 처리
    print("✅ 자산 유지비 정산 완료")




# ✅ /예금 커맨드
@tree.command(name="예금", description="지갑에서 은행으로 돈을 예금합니다.", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(금액="예금할 금액")
async def 예금(interaction: discord.Interaction, 금액: int):
    user_id = str(interaction.user.id)
    wallet = get_balance(user_id)

    if 금액 <= 0 or 금액 > wallet:
        return await interaction.response.send_message(
            f"❌ 예금 금액이 잘못되었거나 잔액이 부족합니다.\n💰 현재 지갑 잔액: **{wallet:,}원**",
            ephemeral=True
        )

    add_balance(user_id, -금액)
    add_bank_deposit(user_id, 금액)

    bank_balance = get_total_bank_balance(user_id)
    next_time = get_next_interest_time(user_id)
    next_time_str = next_time.strftime("%Y-%m-%d %H:%M:%S") if next_time else "없음"

    await interaction.response.send_message(embed=create_embed(
        "🏦 예금 완료",
        (
            f"💸 지갑 → 은행: **{금액:,}원** 예금됨\n"
            f"💰 현재 지갑 잔액: **{get_balance(user_id):,}원**\n"
            f"🏛️ 현재 은행 잔고: **{bank_balance:,}원**\n"
            f"⏰ 가장 빠른 이자 수령 가능 시각 (KST): {next_time_str}"
        ),
        discord.Color.blue(),
        user_id
    ))

# ✅ 예금 자동완성
@예금.autocomplete("금액")
async def 예금_자동완성(interaction: discord.Interaction, current: str):
    user_id = str(interaction.user.id)
    balance = get_balance(user_id)

    if balance <= 0:
        return [app_commands.Choice(name="❌ 예금 가능한 금액 없음", value="0")]

    return [
        app_commands.Choice(name=f"💰 전액 예금 ({balance:,}원)", value=str(balance)),
        app_commands.Choice(name=f"🌓 절반 예금 ({balance // 2:,}원)", value=str(balance // 2))
    ]

# ✅ /출금 커맨드
@tree.command(name="출금", description="은행에서 지갑으로 돈을 출금합니다.", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(금액="출금할 금액")
async def 출금(interaction: discord.Interaction, 금액: int):
    user_id = str(interaction.user.id)
    bank_balance = get_total_bank_balance(user_id)

    if 금액 <= 0 or 금액 > bank_balance:
        return await interaction.response.send_message(
            f"❌ 출금 금액이 잘못되었거나 은행 잔고가 부족합니다.\n🏛️ 현재 은행 잔고: **{bank_balance:,}원**",
            ephemeral=True
        )

    # ✅ 출금 처리 및 이자 계산
    net_interest, tax = process_bank_withdraw(user_id, 금액)
    original_interest = net_interest + tax  # 세전 이자

    add_balance(user_id, 금액 + net_interest)

    if tax > 0:
        add_oduk_pool(tax)

    pool_amt = get_oduk_pool_amount()

    # ✅ 이자 한도 초과 안내 (500,000원 이상 → 컷팅됨)
    if original_interest > 500_000:
        await interaction.channel.send(
            f"⚠️ **이자 지급 한도 초과 안내**\n"
            f"원래 계산된 이자는 **{original_interest:,}원**이었지만,\n"
            f"시스템 상 하루 최대 이자 지급 한도는 **500,000원**입니다.\n"
            f"따라서 실제 지급된 이자는 세금 차감 후 **{net_interest:,}원**입니다.",
            ephemeral=True
        )

    await interaction.response.send_message(embed=create_embed(
        "🏧 출금 완료",
        (
            f"🏛️ 은행 → 지갑: **{금액:,}원** 출금됨\n"
            f"💵 순이자 지급: **{net_interest:,}원** (세금 {tax:,}원 → 오덕로또 적립)\n"
            f"💰 현재 지갑 잔액: **{get_balance(user_id):,}원**\n"
            f"🏦 남은 은행 잔고: **{get_total_bank_balance(user_id):,}원**\n\n"
            f"🎯 현재 오덕로또 상금: **{pool_amt:,}원**\n"
            f"🎟️ `/오덕로또참여`로 오늘의 행운에 도전해보세요!"
        ),
        discord.Color.green(),
        user_id
    ))


# ✅ 출금 자동완성
@출금.autocomplete("금액")
async def 출금_자동완성(interaction: discord.Interaction, current: str):
    user_id = str(interaction.user.id)
    bank_balance = get_total_bank_balance(user_id)

    if bank_balance <= 0:
        return [app_commands.Choice(name="❌ 출금 가능한 잔고 없음", value="0")]

    return [
        app_commands.Choice(name=f"💰 전액 출금 ({bank_balance:,}원)", value=str(bank_balance)),
        app_commands.Choice(name=f"🌓 절반 출금 ({bank_balance // 2:,}원)", value=str(bank_balance // 2))
    ]

# ✅ /은행잔고 커맨드
@tree.command(name="은행잔고", description="지정한 유저의 은행 잔고를 확인합니다 (본인은 이자 시간도 표시)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(대상="은행 잔고를 확인할 유저 (선택)")
async def 은행잔고(interaction: discord.Interaction, 대상: discord.Member = None):
    대상 = 대상 or interaction.user
    user_id = str(대상.id)
    is_self = 대상.id == interaction.user.id

    bank_balance = get_total_bank_balance(user_id)
    next_time = get_next_interest_time(user_id) if is_self else None
    next_time_str = next_time.strftime("%Y-%m-%d %H:%M:%S") if next_time else None

    설명 = f"🏛️ {대상.display_name}님의 은행 잔고는 **{bank_balance:,}원**입니다."
    if is_self and next_time:
        설명 += f"\n⏰ 가장 빠른 이자 수령 가능 시각 (KST): {next_time_str}"
    elif is_self:
        설명 += "\n⏰ 아직 이자 수령 가능한 예금이 없습니다."

    await interaction.response.send_message(embed=create_embed(
        "🏦 은행 잔고 확인",
        설명,
        discord.Color.teal(),
        user_id
    ))



import os
import json
import random
from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands, ui, Interaction, ButtonStyle

# ✅ 시군구 포함된 지역 200개
ALL_REGIONS = [
    "서울 강남구", "서울 서초구", "서울 송파구", "서울 종로구", "서울 마포구", "서울 동작구", "서울 강서구", "서울 성동구", "서울 노원구", "서울 중랑구",
    "부산 해운대구", "부산 수영구", "부산 동래구", "부산 사하구", "부산 금정구", "부산 남구", "부산 연제구", "부산 북구", "부산 중구", "부산 서구",
    "대구 수성구", "대구 달서구", "대구 중구", "대구 동구", "대구 북구", "대구 서구", "대구 남구", "대구 달성군",
    "인천 연수구", "인천 부평구", "인천 계양구", "인천 남동구", "인천 미추홀구", "인천 서구", "인천 중구", "인천 동구",
    "광주 북구", "광주 남구", "광주 동구", "광주 서구", "광주 광산구",
    "대전 유성구", "대전 서구", "대전 중구", "대전 동구", "대전 대덕구",
    "울산 남구", "울산 북구", "울산 동구", "울산 중구", "울산 울주군",
    "세종 조치원읍", "세종 한솔동", "세종 도담동", "세종 아름동", "세종 고운동",
    "경기 수원시", "경기 성남시", "경기 고양시", "경기 용인시", "경기 부천시", "경기 안양시", "경기 평택시", "경기 시흥시", "경기 김포시", "경기 광주시",
    "경기 군포시", "경기 의정부시", "경기 하남시", "경기 파주시", "경기 남양주시", "경기 오산시", "경기 이천시", "경기 안성시", "경기 여주시", "경기 양주시",
    "강원 춘천시", "강원 원주시", "강원 강릉시", "강원 동해시", "강원 속초시", "강원 삼척시", "강원 태백시", "강원 홍천군", "강원 횡성군", "강원 평창군",
    "충북 청주시", "충북 충주시", "충북 제천시", "충북 음성군", "충북 진천군", "충북 괴산군", "충북 보은군", "충북 옥천군", "충북 단양군", "충북 영동군",
    "충남 천안시", "충남 아산시", "충남 공주시", "충남 보령시", "충남 서산시", "충남 논산시", "충남 계룡시", "충남 당진시", "충남 서천군", "충남 금산군",
    "전북 전주시", "전북 익산시", "전북 군산시", "전북 정읍시", "전북 남원시", "전북 김제시", "전북 완주군", "전북 부안군", "전북 고창군", "전북 진안군",
    "전남 목포시", "전남 여수시", "전남 순천시", "전남 나주시", "전남 광양시", "전남 담양군", "전남 곡성군", "전남 구례군", "전남 보성군", "전남 고흥군",
    "경북 포항시", "경북 경주시", "경북 김천시", "경북 안동시", "경북 구미시", "경북 영주시", "경북 영천시", "경북 상주시", "경북 문경시", "경북 경산시",
    "경남 창원시", "경남 진주시", "경남 통영시", "경남 사천시", "경남 김해시", "경남 밀양시", "경남 거제시", "경남 양산시", "경남 의령군", "경남 함안군",
    "제주 제주시", "제주 서귀포시", "제주 애월읍", "제주 조천읍", "제주 구좌읍", "제주 성산읍", "제주 표선면", "제주 한림읍", "제주 한경면", "제주 대정읍"
]

KST = timezone(timedelta(hours=9))

REALESTATE_USAGE_FILE = "real_estate_usage.json"
REALESTATE_PROFIT_FILE = "real_estate_profit.json"

# ✅ 투자 횟수 추적
def load_real_estate_usage():
    if not os.path.exists(REALESTATE_USAGE_FILE):
        return {}
    with open(REALESTATE_USAGE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_real_estate_usage(data):
    with open(REALESTATE_USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_today_real_estate_count(user_id: str):
    today = datetime.now(KST).date().isoformat()
    data = load_real_estate_usage()
    entry = data.get(user_id, {"date": today, "count": 0})
    if entry["date"] != today:
        entry = {"date": today, "count": 0}
    return entry["count"]

def increment_real_estate_count(user_id: str):
    today = datetime.now(KST).date().isoformat()
    data = load_real_estate_usage()
    entry = data.get(user_id, {"date": today, "count": 0})
    if entry["date"] != today:
        entry = {"date": today, "count": 0}
    entry["count"] += 1
    data[user_id] = entry
    save_real_estate_usage(data)

# ✅ 수익 랭킹 기록
def load_real_estate_profits():
    if not os.path.exists(REALESTATE_PROFIT_FILE):
        return {}
    with open(REALESTATE_PROFIT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_real_estate_profits(data):
    with open(REALESTATE_PROFIT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def add_real_estate_profit(user_id: str, amount: int):
    today = datetime.now(KST).date().isoformat()
    data = load_real_estate_profits()
    data.setdefault(today, {})
    data[today][user_id] = data[today].get(user_id, 0) + amount
    save_real_estate_profits(data)

# ✅ 투자 버튼 뷰
class RealEstateView(ui.View):
    def __init__(self, user: discord.User, 투자금: int):
        super().__init__(timeout=30)
        self.user = user
        self.invest_amount = 투자금
        self.disabled_regions = set()
        sampled_regions = random.sample(ALL_REGIONS, 25)
        for region in sampled_regions:
            button = ui.Button(label=region, style=ButtonStyle.primary, custom_id=f"region_{region}")
            button.callback = self.make_callback(region)
            self.add_item(button)

    def make_callback(self, region: str):
        async def callback(interaction: Interaction):
            if interaction.user.id != self.user.id:
                return await interaction.response.send_message("❌ 본인만 사용할 수 있습니다.", ephemeral=True)
            if region in self.disabled_regions:
                return await interaction.response.send_message("이미 선택한 지역입니다.", ephemeral=True)

            balance = get_balance(self.user.id)
            if balance < self.invest_amount:
                return await interaction.response.send_message(f"❌ 잔액 부족\n현재 잔액: **{balance:,}원**", ephemeral=True)

            # ✅ 투자 횟수 기반 손실 배율
            user_id = str(self.user.id)
            count = get_today_real_estate_count(user_id)
            if count < 3: loss_multiplier = 1.0
            elif count < 6: loss_multiplier = 1.2
            elif count < 10: loss_multiplier = 1.5
            else: loss_multiplier = 2.0

            rocket_up = False
            bonus_boost = False
            if random.random() < 0.01:
                profit_rate = 300
                rocket_up = True
            else:
                profit_rate = random.randint(-100, 50)
                if profit_rate < 0:
                    profit_rate = int(profit_rate * loss_multiplier)
                    profit_rate = max(profit_rate, -100)  # 🔧 이 줄 추가!

            if not rocket_up and random.random() < 0.03:
                bonus_boost = True
                profit_rate += 50

            profit_amount = int(self.invest_amount * (profit_rate / 100))
            tax = int(profit_amount * 0.1) if profit_amount > 0 else 0
            net_gain = profit_amount - tax
            receive = self.invest_amount + net_gain

            add_balance(user_id, receive - self.invest_amount)
            final_balance = get_balance(user_id)
            if tax > 0:
                add_oduk_pool(tax)
            elif profit_amount < 0:
                add_oduk_pool(int(abs(profit_amount) * 0.05))

            add_real_estate_profit(user_id, net_gain)
            increment_real_estate_count(user_id)

            # 연출 메시지
            if rocket_up: effect_text = "💥 지역 개발 대박! 재개발 호재!"
            elif profit_rate >= 40: effect_text = "📊 재건축 발표로 급등!"
            elif profit_rate > 10: effect_text = "📈 집값 상승세로 이익 발생"
            elif profit_rate > 0: effect_text = "📦 소폭 수익 발생"
            elif profit_rate == 0: effect_text = "😐 부동산 시장 조용함 (본전)"
            elif profit_rate > -30: effect_text = "🏚️ 거래 침체로 손실..."
            elif profit_rate > -70: effect_text = "🔥 하락장! 큰 손해 발생"
            else: effect_text = "💀 부동산 사기! 전액 손실..."

            title_badge = "🚀 로켓 캐처" if rocket_up else \
                          "💼 투자 귀재" if profit_rate >= 40 else \
                          "💀 투기의 귀재" if profit_rate <= -70 else None

            # 칭호/보너스 줄 문자열 미리 정의
            title_line = f"🎖️ 칭호: {title_badge}\n" if title_badge else ""
            bonus_line = "✨ 보너스 수익률 +50%\n" if bonus_boost else ""

            embed = discord.Embed(
                title="🚀 대박 투자 성공!" if profit_amount >= 0 else "📉 투자 실패...",
                description=(
                    f"👤 투자자: {interaction.user.mention}\n"
                    f"📍 투자 지역: **{region}**\n"
                    f"{title_line}"
                    f"{bonus_line}"
                    f"💬 {effect_text}\n\n"
                    f"💵 투자금: {self.invest_amount:,}원\n"
                    f"📊 수익률: {profit_rate:+}%\n"
                    f"💰 수익: {profit_amount:,}원\n"
                    f"🧾 세금: {tax:,}원\n"
                    f"💼 회수 금액: {receive:,}원\n"
                    f"💰 최종 잔액: {final_balance:,}원"
                ),
                color=discord.Color.green() if profit_amount >= 0 else discord.Color.red()
            )

            if loss_multiplier >= 1.5:
                embed.add_field(
                    name="⚠️ 투자 과열 경고",
                    value=f"오늘 {count}회 투자 → 손실률 {loss_multiplier}배",
                    inline=False
                )

            await interaction.response.send_message(embed=embed)
            self.disabled_regions.add(region)
        return callback

# ✅ 부동산투자 명령어
@tree.command(name="부동산투자", description="전국 부동산 투자! 버튼을 눌러 수익을 확인해보세요.", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(투자금="투자할 금액 (2만원 이상)")
async def 부동산투자(interaction: Interaction, 투자금: int):
    if 투자금 < 20000:
        return await interaction.response.send_message("❌ 최소 투자금은 **20,000원**입니다.", ephemeral=True)
    await interaction.response.send_message(
        f"📍 투자할 지역을 선택하세요!\n💵 투자금: **{투자금:,}원**", 
        view=RealEstateView(interaction.user, 투자금),
        ephemeral=True
    )

# ✅ 자동완성
@부동산투자.autocomplete("투자금")
async def 투자금_자동완성(interaction: Interaction, current: str):
    user_id = str(interaction.user.id)
    balance = get_balance(user_id)
    if balance < 20000:
        return [app_commands.Choice(name="❌ 최소 투자금 부족", value="20000")]

    base = [20000, 50000, 100000]
    half = (balance // 2) // 1000 * 1000
    allin = balance
    choices = [
        app_commands.Choice(name=f"🔥 전액 투자 ({allin:,}원)", value=str(allin)),
        app_commands.Choice(name=f"💸 절반 투자 ({half:,}원)", value=str(half)),
    ] + [
        app_commands.Choice(name=f"✨ 추천 {val:,}원", value=str(val)) for val in base if val < balance
    ]
    await interaction.response.autocomplete(choices[:5])

# ✅ 부동산왕 명령어
@tree.command(name="부동산왕", description="오늘의 부동산 투자 수익 랭킹", guild=discord.Object(id=GUILD_ID))
async def 부동산왕(interaction: Interaction):
    today = datetime.now(KST).date().isoformat()
    data = load_real_estate_profits().get(today, {})
    if not data:
        return await interaction.response.send_message("오늘은 아직 투자 수익 기록이 없습니다.", ephemeral=True)

    top = sorted(data.items(), key=lambda x: x[1], reverse=True)[:5]
    description = ""
    for i, (uid, profit) in enumerate(top, 1):
        user = await interaction.client.fetch_user(int(uid))
        description += f"{i}. **{user.display_name}** - {'+' if profit >=0 else ''}{profit:,}원\n"

    embed = discord.Embed(title="🏆 오늘의 부동산왕 TOP 5", description=description, color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)






import os
import json
import random
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import tasks

# ✅ 설정
LOAN_FILE = "loans.json"
KST = timezone(timedelta(hours=9))
LOAN_INTEREST_RATE = 0.05  # 30분 복리 이자율

# ✅ 신용등급 테이블
CREDIT_GRADES = {
    "S": {"name": "VVIP 고객", "limit": 150_000},
    "A": {"name": "우수 고객", "limit": 100_000},
    "B": {"name": "상위 고객", "limit": 70_000},
    "C": {"name": "일반 고객", "limit": 50_000},
    "D": {"name": "신용 불량", "limit": 30_000},
    "E": {"name": "위험 고객", "limit": 10_000},
    "F": {"name": "블랙리스트", "limit": 5_000}
}

# ✅ 메시지 템플릿
SUCCESS_MESSAGES = [
    "💸 상환 완료! 은행이 감동했습니다.",
    "💰 채권자가 눈물을 훔쳤습니다... 감동의 상환!",
    "📈 신용이 올라가는 소리가 들려요~",
    "🧾 깔끔하게 갚았습니다. 당신은 금융계의 모범!",
    "🎉 대출금 탈출! 축하드립니다!",
    "😎 이 정도면 VIP! 은행이 제안서를 보냈습니다."
]

FAILURE_MESSAGES = [
    "💀 연체 경고 1회... 채권자가 당신의 이름을 명부에 적었습니다.",
    "🔪 오늘 밤 창문을 열어두지 마세요. 회수팀이 출발했습니다.",
    "😨 이자는 돈으로만 갚는 게 아닐 수도 있습니다...",
    "🩸 발톱을 뽑힐 준비는 되셨나요?",
    "☠️ 지하금융조직이 당신의 위치를 파악 중입니다.",
    "📉 신용등급 하락 중... 뼈까지 빚으로 덮이기 일보 직전!",
    "🔫 채권자가 마지막 경고장을 보냈습니다.",
    "🧨 이제 목숨값이 이자보다 싸질 수도...",
    "👀 주변에 수상한 사람이 보이기 시작했다면... 연체 때문일지도요.",
    "💼 당신의 장기를 감정하는 중입니다. 고급 간이시군요."
]

# ✅ 파일 보장 및 로드

def ensure_loan_file():
    if not os.path.exists(LOAN_FILE):
        with open(LOAN_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

def load_loans():
    ensure_loan_file()
    with open(LOAN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_loans(data):
    with open(LOAN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ✅ 유틸

def get_user_loan(user_id):
    return load_loans().get(str(user_id))

def get_all_loan_users():
    return list(load_loans().keys())

def clear_loan(user_id):
    loans = load_loans()
    if user_id not in loans:
        return

    preserved = {
        "credit_grade": loans[user_id].get("credit_grade", "C"),
        "consecutive_successes": loans[user_id].get("consecutive_successes", 0),
        "consecutive_failures": loans[user_id].get("consecutive_failures", 0),
        "unpaid_days": loans[user_id].get("unpaid_days", 0)
    }

    # 대출 관련 필드 초기화
    loans[user_id] = {
        **preserved,
        "amount": 0,
        "created_at": "",
        "last_checked": ""
    }

    save_loans(loans)


def is_due_for_repayment(loan: dict) -> bool:
    created_at = datetime.fromisoformat(loan["created_at"])
    now = datetime.now(KST)

    elapsed = (now - created_at).total_seconds()
    if elapsed < 1800:
        return False  # ❌ 30분 미만이면 무조건 상환 불가

    # ✅ 30분 이상인 경우에만 ±60초 범위 허용
    remainder = elapsed % 1800
    return remainder <= 60 or remainder >= 1740




def calculate_loan_due(principal, created_at_str, rate, *, force_future_30min=False):
    if not created_at_str:
        raise ValueError("created_at 누락")

    created_at = datetime.fromisoformat(created_at_str)
    now = datetime.now(KST)

    elapsed = (now - created_at).total_seconds()
    intervals = max(int(elapsed // 1800) + 1, 1)  # ✅ 최소 1회차부터 시작

    if force_future_30min:
        intervals += 1  # ✅ "다음 상환 예정금"용 예고 회차

    return int(principal * ((1 + rate) ** intervals))





def is_loan_restricted(user_id):
    loan = get_user_loan(user_id)
    if not loan:
        return False
    # ❌ 연체 10회 이상인 경우만 대출 제한 (F등급 허용)
    return loan.get("consecutive_failures", 0) >= 100


def is_rejoin_suspicious(user_id):
    loan = get_user_loan(user_id)
    if not loan:
        return False
    joined = datetime.fromisoformat(loan.get("server_joined_at", loan["created_at"]))
    last_checked = datetime.fromisoformat(loan.get("last_checked", loan["created_at"]))
    return joined > last_checked


BANKRUPT_FILE = "bankrupt_log.json"

def load_bankrupt_users():
    if not os.path.exists(BANKRUPT_FILE):
        return []
    with open(BANKRUPT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def add_to_bankrupt_log(user_id):
    users = load_bankrupt_users()
    uid = str(user_id)
    if uid not in users:
        users.append(uid)
        with open(BANKRUPT_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2)



def was_bankrupted(user_id: str) -> bool:
    loans = load_loans()
    loan = loans.get(str(user_id), {})
    # ✅ 실제로 현재 등급이 F이고, 연속 성공이 0이면 파산 상태로 간주
    return loan.get("credit_grade") == "F" and loan.get("consecutive_successes", 0) == 0





# ✅ 대출 생성

def create_or_update_loan(user_id, amount, credit_grade="C"):
    loans = load_loans()
    user_id_str = str(user_id)

    # 기존 데이터 보존
    existing = loans.get(user_id_str, {})
    preserved_success = existing.get("consecutive_successes", 0)
    preserved_grade = existing.get("credit_grade", credit_grade)

    # 파산 이력이 있다면 강제 F 등급
    preserved_grade = "F" if was_bankrupted(user_id) else preserved_grade

    now = datetime.now(KST).isoformat()
    loans[user_id_str] = {
        "amount": amount,
        "created_at": now,
        "last_checked": now,
        "interest_rate": LOAN_INTEREST_RATE,
        "credit_grade": preserved_grade,
        "consecutive_failures": 0,
        "consecutive_successes": preserved_success,  # ✅ 보존된 값 사용
        "server_joined_at": now
    }
    save_loans(loans)





# ✅ 등급/연체 기반 메시지 생성

def get_failure_message(grade, fails):
    severe = [
        "💀 사채업자가 움직이기 시작했습니다.",
        "🔪 목숨을 담보로 한 대출이었나요?", 
        "📛 당신의 신용은 더 이상 존재하지 않습니다.",
        "💼 장기 매각 경매가 시작됩니다..."
    ]
    medium = [
        "💢 회수팀이 문 앞까지 도착했습니다.",
        "🧨 연체가 계속되면 골치 아파집니다...",
        "🚫 은행이 당신을 조용히 블랙리스트에 올렸습니다."
    ]
    mild = [
        "⚠️ 연체 경고! 빨리 상환해주세요!",
        "📉 신용등급 하락이 시작됐습니다.",
        "📬 채권자에게 독촉장이 날아들었습니다."
    ]
    if grade in ["E", "F"] or fails >= 3:
        return random.choice(severe)
    elif grade in ["C", "D"] or fails == 2:
        return random.choice(medium)
    else:
        return random.choice(mild)

def get_success_message(grade):
    elite = [
        "💎 금융 고수의 품격! 은행도 존경합니다.",
        "🏅 신용 사회의 귀감! 당신을 본받고 싶어요.",
        "💰 완벽한 상환! VIP 전용 금리 제안 예정."
    ]
    normal = [
        "📈 신용이 올라가는 소리가 들려요~",
        "🧾 깔끔하게 갚았습니다. 당신은 금융계의 모범!",
        "🎉 대출금 탈출! 축하드립니다!"
    ]
    casual = [
        "💸 상환 완료! 은행이 감동했습니다.",
        "💰 채권자가 눈물을 훔쳤습니다... 감동의 상환!",
        "😎 이 정도면 VIP! 은행이 제안서를 보냈습니다."
    ]
    if grade in ["S", "A"]:
        return random.choice(elite)
    elif grade in ["B", "C"]:
        return random.choice(normal)
    else:
        return random.choice(casual)

# ✅ 메시지 포맷

def format_repay_message(member, created_at_str, amount, result, grade_change=None):
    created_at = datetime.fromisoformat(created_at_str).astimezone(KST)
    lines = [
        f"💸 상환 시도 결과",
        f"📍 사용자: {member.mention}",
        f"📆 대출일: {created_at.strftime('%m/%d %H:%M')}",
        f"💰 상환금: {amount:,}원",
        result,
    ]
    if grade_change:
        lines.append(grade_change)  # ✅ "🏅 등급:" 포함된 메시지 그대로 추가
    return "\n".join(lines)



AUTO_REPAY_CHANNEL_ID = 1394331814642057418  # 오덕도박장 ID

async def process_overdue_loans_on_startup(bot):
    print("🚀 봇 시작 시 대출 상환 점검 시작")
    now = datetime.now(KST)
    loans = load_loans()

    for user_id, loan in loans.items():
        created_at_str = loan.get("created_at", "")
        if not created_at_str:
            print(f"⚠️ 유저 {user_id}의 created_at 누락됨. 건너뜁니다.")
            continue

        try:
            created = datetime.fromisoformat(created_at_str)
        except ValueError:
            print(f"❌ 유저 {user_id}의 created_at 형식 오류: {created_at_str}")
            continue

        elapsed = (now - created).total_seconds()

        if elapsed >= 1800:
            member = bot.get_user(int(user_id)) or await bot.fetch_user(int(user_id))
            if member:
                result = await try_repay(user_id, member, force=True)
                if result:
                    print(f"🔁 [시작시 상환 처리] {user_id} → {result.replace(chr(10), ' / ')}")

                    channel = bot.get_channel(AUTO_REPAY_CHANNEL_ID)
                    if channel:
                        try:
                            await channel.send(result)
                        except Exception as e:
                            print(f"❌ 채널 전송 실패: {e}")




def get_grade_recovery_message(data):
    grade = data.get("credit_grade", "F")
    success = data.get("consecutive_successes", 0)

    # 복구 기준표 (예시)
    grade_order = ["F", "E", "D", "C", "B", "A", "S"]
    recovery_required = {
        "F": 2,
        "E": 2,
        "D": 2,
        "C": 3,
        "B": 4,
        "A": 5,
    }

    if grade not in grade_order:
        return "", grade, success  # 오류 방지 기본값 반환

    required = recovery_required.get(grade, 3)

    # ✅ 디버깅 로그 추가
    print(f"[DEBUG] 등급 회복 체크: 현재등급={grade}, 성공횟수={success}, 필요횟수={required}")

    if success >= required:
        idx = grade_order.index(grade)
        if idx + 1 < len(grade_order):
            new_grade = grade_order[idx + 1]
            data["credit_grade"] = new_grade
            data["consecutive_successes"] = 0
            return f"🏅 등급: {grade} → {new_grade} 승급!", new_grade, 0
    else:
        remain = required - success
        return f"🏅 등급: 🕐 등급 회복까지 {remain}회 남음 (현재: {grade})", grade, success

    return "", grade, success








def get_user_credit_grade(user_id: str) -> str:
    loan = get_user_loan(user_id)
    if loan:
        return loan.get("credit_grade", "C")
    if was_bankrupted(user_id):
        return "F"
    return "C"








GAMBLING_CHANNEL_ID = 1394331814642057418


@tree.command(name="대출", description="신용등급에 따라 돈을 대출받습니다.", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(금액="대출할 금액 (최대 금액은 등급에 따라 다름)")
async def 대출(interaction: discord.Interaction, 금액: int):
    # ✅ 오덕도박장 외 채널 차단
    if interaction.channel.id != GAMBLING_CHANNEL_ID:
        return await interaction.response.send_message(
            "❌ 이 명령어는 **#오덕도박장** 채널에서만 사용할 수 있습니다.",
            ephemeral=True
        )

    user_id = str(interaction.user.id)

    # ❌ 대출 제한 여부 확인 (연체 or 신용불량 등)
    if is_loan_restricted(user_id):
        return await interaction.response.send_message(
            "🚫 현재 신용등급 또는 연체로 인해 대출이 제한되었습니다.",
            ephemeral=True
        )

    # ❌ 기존 대출 존재 여부 확인 (amount > 0인 경우 대출 불가)
    loan = get_user_loan(user_id)
    if loan and loan.get("amount", 0) > 0:
        return await interaction.response.send_message(
            "❌ 이미 대출이 존재합니다. 상환 후 다시 시도해주세요.",
            ephemeral=True
        )

    # ✅ 실제 유저의 신용등급 가져오기
    grade = get_user_credit_grade(user_id)
    limit = CREDIT_GRADES.get(grade, {"limit": 0})["limit"]

    if 금액 > limit or 금액 <= 0:
        return await interaction.response.send_message(
            f"❌ 대출 금액이 잘못되었거나 현재 등급에서 허용되지 않습니다.\n"
            f"📊 등급: {grade} ({CREDIT_GRADES[grade]['name']})\n"
            f"💰 최대 대출 가능액: {limit:,}원",
            ephemeral=True
        )

    # ✅ 대출 실행
    create_or_update_loan(user_id, 금액, credit_grade=grade)
    add_balance(user_id, 금액)

    return await interaction.response.send_message(
        f"🏦 대출 완료!\n💰 금액: {금액:,}원\n📊 등급: {grade} ({CREDIT_GRADES[grade]['name']})\n"
        f"📆 30분마다 이자가 복리로 적용됩니다. 늦기 전에 갚으세요!",
        ephemeral=True
    )


@대출.autocomplete("금액")
async def 대출금액_자동완성(interaction: discord.Interaction, current: str):
    from discord import app_commands

    user_id = str(interaction.user.id)
    grade = get_user_credit_grade(user_id)
    limit = CREDIT_GRADES.get(grade, {"limit": 0})["limit"]

    half = limit // 2
    suggestions = [
        app_commands.Choice(name=f"💸 최대 대출 ({limit:,}원)", value=str(limit)),
        app_commands.Choice(name=f"💰 절반 대출 ({half:,}원)", value=str(half)),
    ]
    return suggestions






@tree.command(name="대출정보", description="내 현재 대출 현황을 확인합니다.", guild=discord.Object(id=GUILD_ID))
async def 대출정보(interaction: discord.Interaction):
    if interaction.channel.id != GAMBLING_CHANNEL_ID:
        return await interaction.response.send_message(
            "❌ 이 명령어는 **#오덕도박장** 채널에서만 사용할 수 있습니다.",
            ephemeral=True
        )

    user_id = str(interaction.user.id)
    loan = get_user_loan(user_id)

    # ✅ amount가 0이면 파산 상태 → 대출 없음으로 간주
    if not loan or loan.get("amount", 0) == 0:
        return await interaction.response.send_message("✅ 현재 대출 중인 내역이 없습니다.", ephemeral=True)

    created_at = datetime.fromisoformat(loan["created_at"]).astimezone(KST)
    now = datetime.now(KST)
    elapsed_minutes = (now - created_at).total_seconds() / 60

    interest_rate = loan.get("interest_rate", 0.05)
    original = loan["amount"]
    grade = loan.get("credit_grade", "C")
    failures = loan.get("consecutive_failures", 0)

    # ✅ 현재 시점 기준 상환금 (지금 갚으면)
    due_now = calculate_loan_due(original, loan["created_at"], interest_rate, force_future_30min=False)

    # ✅ 다음 상환 타이밍 기준 상환금 (예고용)
    due_next = calculate_loan_due(original, loan["created_at"], interest_rate, force_future_30min=True)

    await interaction.response.send_message(
        f"📋 **대출 정보**\n"
        f"📆 대출일: {created_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"💵 대출원금: {original:,}원\n"
        f"📈 이자율: {interest_rate * 100:.2f}% (30분 복리)\n"
        f"📉 신용등급: {grade}\n"
        f"💣 누적 연체: {failures}회\n"
        f"⏳ 경과 시간: {elapsed_minutes:.1f}분\n"
        f"💰 현재 상환금: {due_now:,}원\n"
        f"🕒 다음 상환 예정금: {due_next:,}원",
        ephemeral=True
    )








# ✅ 채무리스트 명령어

@tree.command(name="채무리스트", description="현재 모든 대출중인 유저들의 정보를 확인합니다.", guild=discord.Object(id=GUILD_ID))
async def 채무리스트(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    loans = load_loans()
    if not loans:
        return await interaction.followup.send("✅ 현재 대출중인 유저가 없습니다.", ephemeral=True)

    lines = ["📋 **현재 채무자 목록**"]
    for uid, data in loans.items():
        try:
            member = interaction.guild.get_member(int(uid)) or await interaction.guild.fetch_member(int(uid))
            name_display = member.display_name
        except discord.NotFound:
            name_display = f"(알 수 없음 - {uid})"

        try:
            rate = data.get("interest_rate", 0.05)
            created_at = data.get("created_at", "")
            if not created_at:
                raise ValueError("created_at 누락")

            total_due = calculate_loan_due(data["amount"], created_at, rate)
            lines.append(
                f"- {name_display} ({uid}): 💰 {total_due:,}원 | 등급: {data.get('credit_grade', 'N/A')} | 연체: {data.get('consecutive_failures', 0)}회"
            )
        except Exception as e:
            lines.append(f"- ⚠️ 오류 유저: {name_display} ({uid}) → {str(e)}")

    await interaction.followup.send("\n".join(lines), ephemeral=True)






@tree.command(name="파산처리", description="특정 유저의 모든 자산, 투자, 채무를 초기화합니다.", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(유저="초기화할 대상 유저")
async def 파산처리(interaction: discord.Interaction, 유저: discord.User):
    perms = interaction.user.guild_permissions
    if not (perms.administrator or perms.manage_channels):
        return await interaction.response.send_message("🚫 이 명령어는 서버 관리자 또는 채널 관리자만 사용할 수 있습니다.", ephemeral=True)

    user_id = str(유저.id)

    # 💥 대출 완전 초기화 (clear_loan 대신 직접 지정)
    loans = load_loans()
    loans[user_id] = {
        "amount": 0,
        "credit_grade": "F",              # ✅ 강제 F등급
        "consecutive_successes": 0,       # ✅ 성공횟수 초기화
        "consecutive_failures": 0,
        "created_at": "",
        "last_checked": "",
        "unpaid_days": 0,
    }
    save_loans(loans)

    # 💥 잔고 초기화
    set_balance(user_id, 0)

    # 💥 은행 초기화
    reset_bank_deposits(user_id)

    # 💥 투자 초기화
    reset_investments(user_id)

    # 💥 파산 기록 추가
    add_to_bankrupt_log(user_id)

    await interaction.response.send_message(
        f"☠️ `{유저.name}`님의 모든 자산이 초기화되었습니다. 이제 완전히 파산 처리되었습니다."
    )



# ✅ 자동 상환

async def try_repay(user_id, member, *, force=False):
    loan = get_user_loan(user_id)
    if not loan:
        return None

    if not force and not is_due_for_repayment(loan):
        return None

    now = datetime.now(KST)
    last_checked = datetime.fromisoformat(loan.get("last_checked", loan["created_at"]))
    if (now - last_checked).total_seconds() < 1740 and not force:
        return None

    rate = loan.get("interest_rate", 0.05)
    total_due = calculate_loan_due(
        loan["amount"], loan["created_at"], rate, force_future_30min=False
    )

    if total_due <= 0:
        return None

    wallet = get_balance(user_id)
    bank = get_total_bank_balance(user_id)

    loans = load_loans()
    data = loans[user_id]
    data.setdefault("consecutive_successes", 0)
    data.setdefault("consecutive_failures", 0)
    data.setdefault("credit_grade", "C")
    data.setdefault("unpaid_days", 0)

    # ✅ 상환 성공
    if wallet >= total_due or wallet + bank >= total_due:
        if wallet >= total_due:
            add_balance(user_id, -total_due)
        else:
            add_balance(user_id, -wallet)
            withdraw_from_bank(user_id, total_due - wallet)

        data["consecutive_successes"] += 1
        data["consecutive_failures"] = 0

        # ✅ 등급 회복 메시지 (단, 반환된 success 값은 사용 안함!)
        grade_message, updated_credit_grade, _ = get_grade_recovery_message(data)

        # ✅ created_at 백업
        created_at_backup = loan["created_at"]

        # ✅ 대출 초기화
        clear_loan(user_id)

        # ✅ 최신 상태 복구 (등급은 get_grade_recovery_message에서 갱신됨)
        loans = load_loans()
        loans[user_id] = {
            "amount": 0,
            "credit_grade": updated_credit_grade,
            "consecutive_successes": data["consecutive_successes"],  # 누적된 값 유지
            "consecutive_failures": 0,
            "created_at": created_at_backup,
            "last_checked": now.isoformat(),
        }
        save_loans(loans)

        print(f"[DEBUG] 상환 성공 → 등급={updated_credit_grade}, success={data['consecutive_successes']}")
        return format_repay_message(member, created_at_backup, total_due, "✅ 결과: 상환 성공!", grade_change=grade_message)



    # ❌ 상환 실패
    data["consecutive_failures"] += 1
    data["consecutive_successes"] = 0
    data["unpaid_days"] += 1

    if data["consecutive_failures"] >= 5:
        clear_loan(user_id)

        # 🧨 파산 처리: 모든 자산 초기화
        set_balance(user_id, 0)
        reset_bank_deposits(user_id)
        reset_investments(user_id)
        add_to_bankrupt_log(user_id)

        # ✅ 파산 상태로 명확히 설정
        loans = load_loans()
        loans[user_id] = {
            "amount": 0,
            "credit_grade": "F",              # 강제 F 등급
            "consecutive_successes": 0,       # 성공 횟수 초기화
            "consecutive_failures": 0,
            "created_at": "",                 # 완전 초기화
            "last_checked": "",
            "unpaid_days": 0,
        }
        save_loans(loans)

        return (
            f"☠️ **{member.display_name}**님은 **연체 5회 초과**로 자동 파산 처리되었습니다.\n"
            f"💥 모든 자산과 채무가 초기화되며, 신용등급은 `F`로 기록됩니다."
        )


    if data["consecutive_failures"] >= 3:
        data["credit_grade"] = "F"
    elif data["consecutive_failures"] == 2:
        data["credit_grade"] = "E"

    data["last_checked"] = now.isoformat()
    loans[user_id] = data
    save_loans(loans)

    return format_repay_message(
        member,
        loan["created_at"],
        total_due,
        f"❌ 결과: 상환 실패! {get_failure_message(data['credit_grade'], data['consecutive_failures'])}\n💣 누적 연체: {data['consecutive_failures']}회"
    )




@tree.command(name="상환", description="현재 대출금을 즉시 상환 시도합니다.", guild=discord.Object(id=GUILD_ID))
async def 상환(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    member = interaction.user

    loan = get_user_loan(user_id)
    if not loan or loan.get("amount", 0) <= 0:
        return await interaction.response.send_message(
            "✅ 현재 상환할 대출금이 없습니다.",
            ephemeral=True
        )

    # 수동 상환은 언제든 시도 가능
    result = await try_repay(user_id, member, force=True)

    if result:
        await interaction.response.send_message(result)
    else:
        await interaction.response.send_message(
            "❌ 상환 실패! 잔액이 부족하거나 처리 중 오류가 발생했습니다.",
            ephemeral=True
        )










from discord.utils import get

# 반드시 고정된 채널 ID 사용 (채널 이름으로 찾는 건 불안정)
AUTO_REPAY_CHANNEL_ID = 1394331814642057418  # 오덕도박장 채널 ID로 바꿔주세요

@tasks.loop(minutes=1)
async def auto_repay_check():
    print("🕓 [대출 상환 루프 시작됨]")
    loans = load_loans()

    for user_id in loans.keys():
        try:
            member = get(bot.get_all_members(), id=int(user_id))
            if member:
                result = await try_repay(user_id, member)  # ✅ 내부에서 is_due_for_repayment 검사
                if result:
                    print(f"[상환 처리] {user_id} → {result.replace(chr(10), ' / ')}")

                    channel = bot.get_channel(AUTO_REPAY_CHANNEL_ID)
                    if channel:
                        await channel.send(result)
        except Exception as e:
            print(f"❌ 자동상환 오류 - 유저 {user_id}: {e}")





























import re
import discord
import hashlib  # ← 파일 상단에 이미 없다면 꼭 추가해주세요!
from datetime import datetime, timedelta, timezone
from discord.ext import tasks

# ✅ 설정값
ALERT_CHANNEL_NAME = "치킨알림"
ALERT_INTERVAL_SECONDS = 600
COMPARE_TOLERANCE_SECONDS = 60
DEBUG = True
CHICKEN_ALERT_COOLDOWN = 60
chicken_alerts = {}
recent_alerts = {}
# 🐔 치킨 감지 버퍼 저장소
pending_chicken_channels = {}  # {channel_name: {"start_time": datetime, "users": {user_id: discord.Member}}}

KST = timezone(timedelta(hours=9))

def log(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}")

def parse_details(details):
    match = re.match(r".*?,\s*(.+?),\s*(\d+)/(\d+)", details or "")
    if match:
        return match.group(1).strip(), int(match.group(2)), int(match.group(3))
    return None, None, None

def is_pubg_name(name):
    return name and ("pubg" in name.lower() or "battleground" in name.lower())

def parse_game_mode(state):
    if not state:
        return None
    for mode in ["Squad", "Duo", "Solo"]:
        if mode.lower() in state.lower():
            return mode
    return None

class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        self.parent[self.find(x)] = self.find(y)

    def groups(self):
        result = {}
        for item in self.parent:
            root = self.find(item)
            result.setdefault(root, set()).add(item)
        return list(result.values())


@tasks.loop(seconds=5)
async def detect_matching_pubg_users():
    now = datetime.utcnow()
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    user_data = {}

    # ✅ 모든 유저 활동 상태 확인
    for vc in guild.voice_channels:
        for member in vc.members:
            if member.bot:
                continue
            for act in member.activities:
                if act.type != discord.ActivityType.playing:
                    continue
                if not is_pubg_name(getattr(act, "name", "")):
                    continue

                details = getattr(act, "details", "")
                state = getattr(act, "state", "")
                if not details or details.lower().strip().startswith("in lobby") or "watch" in (state or "").lower():
                    continue

                game_mode = parse_game_mode(state)
                map_name, current, total = parse_details(details)
                start = getattr(act, "start", None)

                if map_name and game_mode and current and total and start:
                    user_data[member.id] = {
                        "user": member,
                        "channel": vc.name,
                        "map": map_name,
                        "mode": game_mode,
                        "current": current,
                        "total": total,
                        "start": start,
                    }

    # ✅ 유저 간 비교 (같은 경기 판단)
    groups = []
    visited = set()
    users = list(user_data.items())

    for i in range(len(users)):
        uid1, d1 = users[i]
        if uid1 in visited:
            continue
        group = [d1]
        visited.add(uid1)
        for j in range(i + 1, len(users)):
            uid2, d2 = users[j]
            if uid2 in visited:
                continue
            if d1["map"] == d2["map"] and d1["mode"] == d2["mode"] and d1["current"] == d2["current"] and d1["total"] == d2["total"]:
                if abs((d1["start"] - d2["start"]).total_seconds()) <= COMPARE_TOLERANCE_SECONDS:
                    group.append(d2)
                    visited.add(uid2)
        if len(group) >= 2:
            groups.append(group)

    for members in groups:
        # ✅ group_key: 음성채널들의 조합
        group_key = frozenset(d["channel"] for d in members)

        # ✅ 동일 음성채널 내만 있는 경우 제외
        if len(group_key) <= 1:
            continue

        # ✅ 중복 알림 방지
        if group_key in recent_alerts and (now - recent_alerts[group_key]).total_seconds() < ALERT_INTERVAL_SECONDS:
            continue

        repr_user = members[0]
        map_name = repr_user["map"]
        mode = repr_user["mode"]
        current = repr_user["current"]
        total = repr_user["total"]
        times = [d["start"] for d in members]
        max_diff = max((abs((s - t).total_seconds()) for s in times for t in times))

        # ✅ 채널별 유저 정리
        by_channel = {}
        for d in members:
            by_channel.setdefault(d["channel"], []).append(d["user"].display_name)

        desc_lines = [f"**{ch}**: {', '.join(names)}" for ch, names in by_channel.items()]
        desc = "\n".join(desc_lines)

        text_channel = discord.utils.get(guild.text_channels, name=ALERT_CHANNEL_NAME)
        if text_channel:
            embed = discord.Embed(
                title="🎯 동일한 PUBG 경기 추정!",
                description=(
                    f"{desc}\n\n"
                    f"🗺️ 맵: `{map_name}` | 모드: `{mode}`\n"
                    f"👥 인원: {current}/{total}\n"
                    f"🕒 시작 시각 오차: 약 {int(max_diff)}초"
                ),
                color=discord.Color.orange()
            )
            embed.set_footer(text="오덕봇 감지 시스템 • 중복 알림 방지 10분")
            await text_channel.send(embed=embed)

            user_tags = [f"{d['user'].display_name}@{d['channel']}" for d in members]
            log(f"🔔 알림 전송: {user_tags}")

        recent_alerts[group_key] = now

    # ✅ 음성채널별 치킨 감지 (5초간 유예 및 누적 유저 감지)
    for vc in guild.voice_channels:
        members = [m for m in vc.members if not m.bot]
        if not members:
            continue

        ch_key = vc.name
        now_detecting = pending_chicken_channels.get(ch_key)

        if ch_key in chicken_alerts and (now - chicken_alerts[ch_key]).total_seconds() < CHICKEN_ALERT_COOLDOWN:
            continue

        keywords = ["chicken", "winner", "dinner"]
        found_users = {}

        for user in members:
            for act in user.activities:
                if act.type != discord.ActivityType.playing:
                    continue

                state = getattr(act, "state", "") or ""
                details = getattr(act, "details", "") or ""
                name = getattr(act, "name", "") or ""
                large_image_text = getattr(act, "large_image_text", "") or ""
                large_image = getattr(act, "large_image", "") or ""
                small_image_text = getattr(act, "small_image_text", "") or ""

                combined = f"{state} {details} {name} {large_image_text} {large_image} {small_image_text}".lower()

                if any(k in combined for k in keywords):
                    found_users[user.id] = user
                    break

        if found_users:
            if not now_detecting:
                pending_chicken_channels[ch_key] = {
                    "start_time": now,
                    "users": found_users.copy()
                }
                log(f"⏳ 치킨 감지 버퍼 시작: {ch_key} - {[u.display_name for u in found_users.values()]}")
            else:
                pending_chicken_channels[ch_key]["users"].update(found_users)

  

    # ✅ 치킨 감지 버퍼 만료된 채널 처리
    expired_channels = []
    for ch_key, data in pending_chicken_channels.items():
        elapsed = (now - data["start_time"]).total_seconds()
        detected_users = data["users"]

        log(f"[DEBUG] 검사중: 채널={ch_key}, 경과시간={elapsed:.1f}s, 감지된 유저={len(detected_users)}명")

        # 🛡️ 일정 시간 이상 버퍼 유지 시 강제 제거
        if elapsed >= 30:
            log(f"⚠️ 치킨 버퍼 강제 제거 (30초 초과): {ch_key}")
            expired_channels.append(ch_key)
            continue

        # ⏰ 감지 시작 후 5초 경과 여부 확인
        if elapsed >= 5:
            # 🛑 감지된 유저가 아무도 없다면 실패 처리
            if not detected_users:
                log(f"❌ 치킨 감지 실패 (유저 없음): {ch_key}")
                expired_channels.append(ch_key)
                continue

            # 🧱 알림 쿨타임 중이면 생략
            last_time = chicken_alerts.get(ch_key)
            if isinstance(last_time, datetime) and (now - last_time).total_seconds() < CHICKEN_ALERT_COOLDOWN:
                log(f"⏹️ 동일 채널({ch_key}) 치킨 감지 쿨타임 중 - 생략")
                expired_channels.append(ch_key)
                continue

            # 🧍 전체 멤버 / 비감지 유저 구분
            all_members = [m for vc in guild.voice_channels if vc.name == ch_key for m in vc.members if not m.bot]
            undetected_users = [u for u in all_members if u.id not in detected_users]

            # 📢 텍스트 채널로 알림 전송
            text_channel = discord.utils.get(guild.text_channels, name=ALERT_CHANNEL_NAME)
            if text_channel:
                desc = (
                    f"**{ch_key}** 채널의 유저들이 치킨을 먹었습니다!\n\n"
                    f"👑 **감지된 유저**:\n> {', '.join(u.mention for u in detected_users.values())}\n\n"
                )
                if undetected_users:
                    desc += f"🔇 **감지되지 않은 유저** (활동 상태 비공유):\n> {', '.join(u.display_name for u in undetected_users)}"

                embed = discord.Embed(
                    title="🍗 치킨 획득 감지!",
                    description=desc,
                    color=discord.Color.gold()
                )
                embed.set_footer(text="오덕봇 감지 시스템 • 치킨 축하 메시지")
                await text_channel.send(embed=embed)
                log(f"🍗 치킨 알림 전송 (버퍼 종료): {[u.display_name for u in detected_users.values()]}")

            # ✅ 알림 발송 시간 저장
            chicken_alerts[ch_key] = now
            expired_channels.append(ch_key)

    # ✅ 버퍼 제거
    for ch_key in expired_channels:
        log(f"[DEBUG] 버퍼 제거: {ch_key}")
        pending_chicken_channels.pop(ch_key, None)








@tree.command(name="감가테스트", description="(채널 관리자 전용) 자산 유지비 감가를 수동 실행합니다.", guild=discord.Object(id=GUILD_ID))
async def 감가테스트(interaction: discord.Interaction):
    # 🔐 채널 관리자 권한 체크 (Manage Channels)
    if not interaction.user.guild_permissions.manage_channels:
        return await interaction.response.send_message(
            "❌ 이 명령어는 **채널 관리자 권한**이 있는 사용자만 실행할 수 있습니다.",
            ephemeral=True
        )

    await interaction.response.defer(thinking=True)

    await apply_maintenance_costs(bot)   # ✅ 지갑 감가
    await apply_bank_depreciation(bot)   # ✅ 은행 감가
    await decay_oduk_pool(bot)           # ✅ 오덕로또 감가

    await interaction.followup.send("✅ 감가 테스트가 완료되었습니다. 로그 또는 알림 채널을 확인하세요.")
















@bot.event
async def on_ready():
    global oduk_pool_cache
    global invites_cache

    await process_overdue_loans_on_startup(bot)
    auto_repay_check.start()
    
    print(f"🤖 봇 로그인됨: {bot.user}")


    if not auto_apply_maintenance.is_running():
        auto_apply_maintenance.start()

    if not auto_decay_oduk_pool.is_running():
        auto_decay_oduk_pool.start()

    # ✅ 기존 루프 유지
    if not monitor_discord_ping.is_running():
        monitor_discord_ping.start()
        print("📶 Discord 핑 모니터링 루프 시작됨")

    # ✅ PUBG 감지 루프 실행 (이름 수정 및 중복 방지)
    if not detect_matching_pubg_users.is_running():
        detect_matching_pubg_users.start()
        print("📡 PUBG 감지 루프 시작됨")

    await asyncio.sleep(2)

    for guild in bot.guilds:
        print(f"접속 서버: {guild.name} (ID: {guild.id})")


    try:
        synced = await tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"✅ 슬래시 명령어 {len(synced)}개 동기화됨")
    except Exception as e:
        print(f"❌ 슬래시 명령어 동기화 실패: {e}")

    if not reset_daily_claims.is_running():
        reset_daily_claims.start()

    # ✅ 오덕 캐시
    
    oduk_pool_cache = load_oduk_pool()
    if oduk_pool_cache is None:
        print("⚠️ 오덕 잔고 파일이 아직 없습니다. 처음 사용할 때 생성됩니다.")
        oduk_pool_cache = {}
    else:
        print(f"🔄 오덕 캐시 로딩됨: {oduk_pool_cache}")

    # ✅ 초대 캐시 불러오기 먼저
   
    load_invite_cache()

    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            invites_cache[str(guild.id)] = {
                invite.code: {
                    "uses": invite.uses,
                    "inviter_id": invite.inviter.id if invite.inviter else None
                }
                for invite in invites
            }
        except Exception as e:
            print(f"❌ 초대 캐시 실패 ({guild.name}): {e}")
    print("📨 초대 캐시 초기화 완료!")

    try:
        with open("invites_cache.json", "w", encoding="utf-8") as f:
            json.dump(invites_cache, f, ensure_ascii=False, indent=2)
        print("💾 초대 캐시 invites_cache.json 저장 완료!")
    except Exception as e:
        print(f"❌ 초대 캐시 저장 실패: {e}")

    try:
        auto_refresh_invites.start()
        print("⏱ 초대 캐시 자동 갱신 루프 시작됨")
    except RuntimeError:
        print("⚠️ auto_refresh_invites 루프는 이미 실행 중입니다.")


    # 자동 닉네임 검사 및 저장
    target_guild = discord.utils.get(bot.guilds, id=GUILD_ID)
    if target_guild:
        try:
            print("🔄 valid_pubg_ids.json 자동 갱신 중...")
            await update_valid_pubg_ids(target_guild)
            print("✅ valid_pubg_ids.json 자동 갱신 완료")
        except Exception as e:
            print(f"❌ 유효 닉네임 자동 갱신 실패: {e}")
    else:
        print(f"❌ GUILD_ID {GUILD_ID}에 해당하는 서버를 찾을 수 없습니다.")

    try:
        asyncio.create_task(start_pubg_collection())
        print("📦 전적 자동 수집 태스크 시작됨 (매일 새벽 4시)")
    except Exception as e:
        print(f"❌ start_pubg_collection 실행 실패: {e}")

    try:
        check_voice_channels_for_streaming.start()
    except Exception as e:
        print(f"❌ check_voice_channels_for_streaming 루프 실행 실패: {e}")

    try:
        auto_update_valid_ids.start()
    except Exception:
        print("⚠️ auto_update_valid_ids 루프는 이미 실행 중일 수 있음.")

    # ✅ 오덕로또 스케줄러 시작 (매일 오전 9시)
    try:
        async def schedule_daily_lotto():
            while True:
                now = datetime.now(KST)
                next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
                if now >= next_run:
                    next_run += timedelta(days=1)
                wait_sec = (next_run - now).total_seconds()
                print(f"🕘 다음 로또 추첨까지 {int(wait_sec)}초 대기")
                await asyncio.sleep(wait_sec)
                await auto_oduk_lotto()

        asyncio.create_task(schedule_daily_lotto())
        print("⏰ 오덕로또 추첨 스케줄러 시작됨")
    except Exception as e:
        print(f"❌ schedule_daily_lotto 실행 실패: {e}")

    # 음성 채널 자동 퇴장 타이머
    await asyncio.sleep(3)
    for guild in bot.guilds:
        bap_channel = discord.utils.get(guild.voice_channels, name="밥좀묵겠습니다")
        text_channel = discord.utils.get(guild.text_channels, name="봇알림")

        if bap_channel:
            for member in bap_channel.members:
                if member.bot:
                    continue
                if member.id in auto_disconnect_tasks:
                    continue

                try:
                    await member.send(
                        f"🍚 {member.display_name}님, '밥좀묵겠습니다' 채널에 입장 중입니다. 20분 후 자동 퇴장됩니다.")
                except Exception as e:
                    print(f"DM 전송 실패 (재시작 시): {member.display_name} - {e}")

                task = asyncio.create_task(
                    auto_disconnect_after_timeout(member, bap_channel, text_channel))
                auto_disconnect_tasks[member.id] = task
                print(f"🔄 재시작 후 타이머 적용됨: {member.display_name}")

    # ✅ 투자 시스템 초기화 및 루프 시작
    ensure_stocks_filled()

    if not os.path.exists(INVESTMENT_FILE):
        with open(INVESTMENT_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

    # ✅ 정산 루프 비동기 실행
    asyncio.create_task(start_random_investment_loop())
    print("📈 투자 정산 루프 시작됨")






keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ 환경변수 DISCORD_TOKEN이 없습니다.")
