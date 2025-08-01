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

import discord.opus
import ctypes.util

# 자동 로드가 실패했을 때, 수동으로 Opus 라이브러리를 찾아 로드
if not discord.opus.is_loaded():
    lib_path = ctypes.util.find_library('opus')  # 'opus' 라이브러리 탐색
    if lib_path:
        try:
            discord.opus.load_opus(lib_path)
            print(f"🔊 Manual Opus load with '{lib_path}':", discord.opus.is_loaded())
        except Exception as e:
            print("🔊 Manual Opus load failed:", e)
    else:
        print("🔊 Could not find opus library via ctypes.util.find_library")



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

def record_gamble_result(user_id: str, success: bool):
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


def get_gamble_title(user_data: dict, success: bool) -> str:
    stats = user_data.get("gamble", {})
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

    # 🗂️ D. 누적 시도 칭호
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
    (100_0000, 0.05),   # 100만 원 이상 → 5%
    (500_0000, 0.15),   # 500만 원 이상 → 15%
    (1000_0000, 0.50),  # 1천만 원 이상 → 50%
    (3000_0000, 0.70),  # 3천만 원 이상 → 70%
]

# 예시로 채널 ID 설정 (실제 사용 중인 ID로 교체하세요)
DOKDO_CHANNEL_ID = 1394331814642057418  # 오덕도박장


import io
import discord

# 디스코드 제한 관련 상수
DISCORD_MESSAGE_LIMIT = 2000          # 디스코드 메시지 본문 최대 길이(절대 2000 초과 금지)
EMBED_DESCRIPTION_LIMIT = 2048        # 임베드 description 권장 최대(참고용)
FILE_FALLBACK_THRESHOLD = 6000        # 이 길이를 넘으면 파일로 전달(필요시 조정)

async def send_long_message(
    channel: discord.abc.Messageable,
    lines: list[str],
    limit: int = DISCORD_MESSAGE_LIMIT
):
    """
    lines(list[str])를 메시지 길이 제한(limit)에 맞춰 여러 번 나눠서 순차 전송합니다.
    각 줄이 단독으로도 limit를 초과할 수 있으므로, 그 경우 줄 자체를 여러 조각으로 분할합니다.
    - 전체 텍스트가 너무 길면 파일로 전송으로 우회합니다.
    - 모든 전송은 try/except로 감싸 안정성을 높였습니다.
    """
    if not lines:
        return

    # 혹시 limit이 잘못 들어오면 2000 이하로 보정
    limit = min(int(limit or DISCORD_MESSAGE_LIMIT), DISCORD_MESSAGE_LIMIT)
    # 여유를 두고 싶다면 아래와 같이 살짝 낮춰도 됩니다.
    # limit = min(limit, 1990)

    # 전체 텍스트가 지나치게 길면 파일로 전송하는 우회
    full_text = "\n".join(lines)
    if len(full_text) > FILE_FALLBACK_THRESHOLD:
        fp = io.BytesIO(full_text.encode("utf-8"))
        fp.seek(0)
        try:
            await channel.send(
                content="📄 내용이 길어 파일로 전달합니다.",
                file=discord.File(fp, filename="maintenance_report.txt")
            )
        except Exception as e:
            print(f"❌ 파일 전송 실패: {e}")
        return

    chunk = ""
    for line in lines:
        # 단일 줄이 limit보다 긴 특수 케이스 처리
        if len(line) > limit:
            # 남아있던 chunk 먼저 전송
            if chunk:
                try:
                    await channel.send(chunk)
                except Exception as e:
                    print(f"❌ 메시지 전송 실패: {e} (길이: {len(chunk)})")
                chunk = ""

            # line을 limit 사이즈로 쪼개서 전송
            i = 0
            while i < len(line):
                piece = line[i:i+limit]
                try:
                    await channel.send(piece)
                except Exception as e:
                    print(f"❌ 메시지 전송 실패(쪼개진 줄): {e} (부분 길이: {len(piece)})")
                i += limit
            continue

        # 현재 줄 추가 시 제한 초과면 먼저 전송
        # +1은 개행 문자 고려
        if len(chunk) + len(line) + 1 > limit:
            if chunk:
                try:
                    await channel.send(chunk)
                except Exception as e:
                    print(f"❌ 메시지 전송 실패: {e} (길이: {len(chunk)})")
            chunk = line + "\n"
        else:
            chunk += line + "\n"

    # 마지막 남은 chunk 전송
    if chunk:
        try:
            await channel.send(chunk)
        except Exception as e:
            print(f"❌ 마지막 메시지 전송 실패: {e} (길이: {len(chunk)})")


async def apply_maintenance_costs(bot):
    """
    자산 유지비(감가)를 3시간마다 적용하고, 결과를 공지 채널(DOKDO_CHANNEL_ID)에 안내합니다.
    - MAINTENANCE_TIERS: List[Tuple[int, float]]  예) [(10000000, 0.02), (5000000, 0.015), (1000000, 0.01)]
      (threshold, rate) 형태. 큰 금액 티어부터 적용되도록 내림차순 정렬하여 사용.
    - load_balances()/save_balances(): 유저 자산 로드/저장 함수
    - fetch_user_safe(user_id): Member or User(없으면 None) 반환
    - KST: Asia/Seoul tzinfo (없으면 timezone(timedelta(hours=9)))
    """
    balances = load_balances()
    now = datetime.now(KST).isoformat() if 'KST' in globals() else datetime.now(timezone.utc).isoformat()
    changed_users: list[tuple[str, int, int, float, int, int]] = []

    # ✅ 티어는 큰 기준부터 적용되도록 내림차순 정렬
    tiers_desc = sorted(MAINTENANCE_TIERS, key=lambda x: x[0], reverse=True)
    min_threshold = tiers_desc[-1][0]  # ✅ 최저 티어 기준(예: 1,000,000)

    for user_id, info in balances.items():
        amount = int(info.get("amount", 0))

        # ✅ 최저 티어 미만은 감가 대상 아님
        if amount < min_threshold:
            continue

        # ✅ MAINTENANCE_TIERS 기준 감가율 결정(가장 높은 티어 우선)
        rate = 0.0
        applied_threshold = 0
        for threshold, r in tiers_desc:
            if amount >= threshold:
                rate = float(r)
                applied_threshold = int(threshold)
                break

        deduction = int(amount * rate)
        new_amount = amount - deduction

        # ✅ 최소 100만 원 보장
        if new_amount < 1_000_000:
            deduction = amount - 1_000_000
            new_amount = 1_000_000

        if deduction > 0:
            balances[user_id]["amount"] = new_amount
            balances[user_id]["last_updated"] = now
            changed_users.append((user_id, amount, new_amount, rate, applied_threshold, deduction))
            print(f"💸 유지비 차감: {user_id} → {deduction:,}원 (율 {int(rate*100)}%, 기준 ≥{applied_threshold:,}원)")

    save_balances(balances)

    # ✅ 안내 메시지 전송
    if not changed_users:
        return

    channel = bot.get_channel(DOKDO_CHANNEL_ID)
    if not channel:
        print(f"[apply_maintenance_costs] 채널(ID={DOKDO_CHANNEL_ID})을 찾을 수 없습니다.")
        return

    msg_lines: list[str] = ["💸 **자산 유지비 감가 정산 결과**"]

    # 각 유저 결과 라인 구성
    for uid, before, after, rate, th, cut in changed_users:
        member = await fetch_user_safe(uid)
        name = (getattr(member, "display_name", None)
                or getattr(member, "name", None)
                or f"ID:{uid}")
        msg_lines.append(
            f"• {name} → **{before:,}원 → {after:,}원** "
            f"(이번 회차 {cut:,}원 차감, 적용율 {int(rate*100)}%, 티어 ≥{th:,}원)"
        )

    # 정책 안내(주기/티어/최소 보장) — 티어 최저 기준을 자동 반영
    tier_desc = " / ".join([f"≥{t:,}원 {int(r*100)}%" for t, r in tiers_desc])
    msg_lines.append(
        f"\n📉 자산이 **{min_threshold:,}원 이상**일 경우 **3시간마다** 감가가 적용됩니다.\n"
        f"🧮 적용 티어: {tier_desc}\n"
        f"🛡️ 감가 후 최소 보장: **1,000,000원**"
    )

    # ✅ 길이 제한 안전 전송
    await send_long_message(channel, msg_lines)



@tasks.loop(hours=3)
async def auto_apply_maintenance():
    print("🕓 자산 유지비 정산 시작")
    await apply_maintenance_costs(bot)     # ✅ await + bot 전달
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
                f"📉 **오덕로또 2시간 주기 상금 감가 적용**\n"
                f"💰 기존 상금: **{current_amount:,}원** → 현재 상금: **{new_amount:,}원**\n"
                f"🧾 **100만 원 초과분의 50%**가 감가되었으며, 최소 **100만 원**은 보장됩니다.\n"
                f"🎟️ `/오덕로또참여`로 오늘의 행운에 도전해보세요!"
            )
    else:
        print("✅ 오덕로또 상금이 100만 원 이하라 감가되지 않음")


@tasks.loop(hours=2)
async def auto_decay_oduk_pool():
    print("🕓 오덕로또 감가 시작")
    await decay_oduk_pool(bot)
    print("✅ 오덕로또 감가 완료")
















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


def save_player_stats_to_file(
    nickname,
    squad_metrics,
    ranked_stats,
    stats=None,
    discord_id=None,
    pubg_id=None,
    source="기본"
):
    """
    시즌 리더보드 저장 함수 (discord_id 기준 식별)
    - 닉네임/서버별명이 바뀌어도 같은 유저로 덮어쓰기
    - pubg_id는 기록용(식별에 사용하지 않음)
    """
    import os
    import json
    import time
    from datetime import datetime

    # ─────────────────────────────────────────────────────────
    # 전역 중복저장 방지 캐시 보장
    # ─────────────────────────────────────────────────────────
    global recent_saves
    if "recent_saves" not in globals():
        recent_saves = {}

    # ─────────────────────────────────────────────────────────
    # 기본 검증
    # ─────────────────────────────────────────────────────────
    if discord_id is None:
        # 식별키가 없으면 저장 불가
        print(f"❌ 저장 실패 ({source}): {nickname} | 이유: discord_id 없음")
        return

    # ─────────────────────────────────────────────────────────
    # 중복 저장 방지 (30초 규칙) - discord_id 단일 키 사용
    # ─────────────────────────────────────────────────────────
    key = str(discord_id)
    now = time.time()
    last = recent_saves.get(key)
    if last is not None and now - last < 30:
        print(f"⏹ 중복 저장 방지: {nickname} ({source})")
        return
    recent_saves[key] = now

    # ─────────────────────────────────────────────────────────
    # 시즌 ID
    # ─────────────────────────────────────────────────────────
    try:
        season_id = get_season_id()
    except Exception as e:
        print(f"❌ 저장 실패 ({source}): {nickname} | 시즌 ID 조회 실패: {e}")
        return

    # ─────────────────────────────────────────────────────────
    # pubg_id 체크(기록용)
    # ─────────────────────────────────────────────────────────
    if not pubg_id:
        print(f"⚠️ pubg_id 누락됨: {nickname} / discord_id: {discord_id}")

    # 저장 데이터 기본 구조
    data_to_save = {
        "nickname": nickname,  # 표시용
        "discord_id": str(discord_id),  # 식별용(불변)
        "pubg_id": pubg_id.strip().lower() if pubg_id else "",
        "timestamp": datetime.now().isoformat()
    }

    # ─────────────────────────────────────────────────────────
    # 기본(일반전) 통계 파생치 계산
    # ─────────────────────────────────────────────────────────
    if stats:
        try:
            squad_stats = stats["data"]["attributes"]["gameModeStats"].get("squad", {})
        except Exception:
            squad_stats = {}

        rounds_played = int(squad_stats.get("roundsPlayed", 0) or 0)
        kills = int(squad_stats.get("kills", 0) or 0)
        top10s = int(squad_stats.get("top10s", 0) or 0)
        headshot_kills = int(squad_stats.get("headshotKills", 0) or 0)
        time_survived = float(squad_stats.get("timeSurvived", 0) or 0.0)
        longest_kill = float(squad_stats.get("longestKill", 0) or 0.0)
    else:
        rounds_played = kills = top10s = headshot_kills = 0
        time_survived = longest_kill = 0.0

    if squad_metrics:
        try:
            avg_damage, kd, win_rate = squad_metrics
        except Exception:
            # 입력 튜플 형식이 불완전한 경우 안전값
            avg_damage, kd, win_rate = 0.0, 0.0, 0.0
        top10_ratio = (top10s / rounds_played * 100) if rounds_played else 0.0
        headshot_pct = (headshot_kills / kills * 100) if kills else 0.0
        avg_survive = (time_survived / rounds_played) if rounds_played else 0.0

        data_to_save["squad"] = {
            "avg_damage": float(avg_damage),
            "kd": float(kd),
            "win_rate": float(win_rate),
            "rounds_played": rounds_played,
            "kills": kills,
            "top10_ratio": float(top10_ratio),
            "headshot_pct": float(headshot_pct),
            "avg_survive": float(avg_survive),
            "longest_kill": float(longest_kill),
        }
    else:
        data_to_save["squad"] = {
            "avg_damage": 0.0,
            "kd": 0.0,
            "win_rate": 0.0,
            "rounds_played": rounds_played,
            "kills": kills,
            "top10_ratio": 0.0,
            "headshot_pct": 0.0,
            "avg_survive": 0.0,
            "longest_kill": float(longest_kill),
        }

    # ─────────────────────────────────────────────────────────
    # 경쟁전(랭크) 통계
    # ─────────────────────────────────────────────────────────
    try:
        if ranked_stats and "data" in ranked_stats:
            ranked_modes = ranked_stats["data"]["attributes"].get("rankedGameModeStats", {})
            squad_rank = ranked_modes.get("squad")
            if squad_rank:
                data_to_save["ranked"] = {
                    "tier": squad_rank.get("currentTier", {}).get("tier", "Unranked"),
                    "subTier": squad_rank.get("currentTier", {}).get("subTier", ""),
                    "points": squad_rank.get("currentRankPoint", 0) or 0,
                }
    except Exception:
        # 랭크 파싱 실패는 저장 자체를 막지 않음
        pass

    # ─────────────────────────────────────────────────────────
    # 파일 입출력 및 시즌 동기화
    # ─────────────────────────────────────────────────────────
    leaderboard_path = "season_leaderboard.json"
    try:
        if os.path.exists(leaderboard_path):
            with open(leaderboard_path, "r", encoding="utf-8") as f:
                file_data = json.load(f) or {}
                stored_season_id = file_data.get("season_id")
                leaderboard = file_data.get("players", []) or []
        else:
            stored_season_id = None
            leaderboard = []

        # 시즌이 바뀌면 리셋
        if stored_season_id != season_id:
            leaderboard = []

        # 같은 유저(= 같은 discord_id) 기존 항목 제거 → 최신 정보로 대체
        leaderboard = [p for p in leaderboard if p.get("discord_id") != str(discord_id)]
        leaderboard.append(data_to_save)

        with open(leaderboard_path, "w", encoding="utf-8") as f:
            json.dump({"season_id": season_id, "players": leaderboard}, f, ensure_ascii=False, indent=2)

        print(f"✅ 저장 성공 ({source}): {nickname} ({data_to_save.get('pubg_id')})")
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
    top10s = mode_stats.get("top10s", 0)
    headshots = mode_stats.get("headshotKills", 0)
    time_survived = mode_stats.get("timeSurvived", 0)
    longest_kill = mode_stats.get("longestKill", 0)

    avg_damage = damage / rounds
    kd = kills / max(1, rounds - wins)
    win_rate = (wins / rounds) * 100
    top10_rate = (top10s / rounds) * 100 if rounds > 0 else 0
    headshot_ratio = (headshots / kills * 100) if kills > 0 else 0
    avg_survival = time_survived / rounds if rounds > 0 else 0

    # ✅ return 타입을 튜플(스코어용) + 상세 딕셔너리로 구분
    primary_metrics = (avg_damage, kd, win_rate)
    additional_metrics = {
        "top10_rate": top10_rate,
        "headshot_ratio": headshot_ratio,
        "avg_survival": avg_survival,
        "longest_kill": longest_kill,
        "rounds": rounds,
        "kills": kills,
        "wins": wins
    }

    return primary_metrics, additional_metrics

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


def pick_best_rank_tier(ranked_stats):
    """가장 높은 RP 기준으로 best 티어를 반환"""
    best = ("Unranked", "", 0)
    modes = ranked_stats.get("data", {}).get("attributes", {}).get("rankedGameModeStats", {})

    for mode_data in modes.values():
        tier = mode_data.get("currentTier", {}).get("tier", "Unranked")
        sub = mode_data.get("currentTier", {}).get("subTier", "")
        point = mode_data.get("currentRankPoint", 0)

        if point > best[2]:
            best = (tier, sub, point)

    return best  # (tier, sub, point)





from discord.ui import View, Button

class ModeSwitchView(View):
    def __init__(self, nickname, stats, ranked_stats=None):
        super().__init__(timeout=180)
        self.nickname = nickname
        self.stats = stats
        self.ranked_stats = ranked_stats

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="SOLO", style=discord.ButtonStyle.secondary, custom_id="solo")
    async def solo_button(self, interaction: discord.Interaction, button: Button):
        embed = generate_mode_embed(self.stats, "solo", self.nickname)
        await interaction.response.edit_message(embed=embed, view=self, attachments=[])

    @discord.ui.button(label="DUO", style=discord.ButtonStyle.secondary, custom_id="duo")
    async def duo_button(self, interaction: discord.Interaction, button: Button):
        embed = generate_mode_embed(self.stats, "duo", self.nickname)
        await interaction.response.edit_message(embed=embed, view=self, attachments=[])

    @discord.ui.button(label="SQUAD", style=discord.ButtonStyle.primary, custom_id="squad")
    async def squad_button(self, interaction: discord.Interaction, button: Button):
        embed = generate_mode_embed(self.stats, "squad", self.nickname)
        await interaction.response.edit_message(embed=embed, view=self, attachments=[])

    @discord.ui.button(label="랭크", style=discord.ButtonStyle.success, custom_id="ranked")
    async def ranked_button(self, interaction: discord.Interaction, button: Button):
        embed, file = generate_ranked_embed(self.ranked_stats, self.nickname)
        if file:
            await interaction.response.edit_message(embed=embed, view=self, attachments=[file])
        else:
            await interaction.response.edit_message(embed=embed, view=self, attachments=[])



def generate_mode_embed(stats, mode="squad", nickname="플레이어"):
    embed = discord.Embed(title=f"{nickname} - {mode.upper()} 전적", color=discord.Color.blurple())

    mode_key = {
        "solo": "solo",
        "duo": "duo",
        "squad": "squad"
    }.get(mode.lower(), "squad")

    m = stats.get("data", {}).get("attributes", {}).get("gameModeStats", {}).get(mode_key, {})
    if not m:
        embed.description = f"❌ {mode.upper()} 전적 정보가 없습니다."
        return embed

    rounds = m.get("roundsPlayed", 0)
    wins = m.get("wins", 0)
    kills = m.get("kills", 0)
    top10s = m.get("top10s", 0)
    headshot_kills = m.get("headshotKills", 0)
    damage_dealt = m.get("damageDealt", 0.0)
    longest_kill = m.get("longestKill", 0.0)
    time_survived = m.get("timeSurvived", 0)

    # 안전한 계산 (0 나누기 방지)
    win_rate = (wins / rounds * 100) if rounds > 0 else 0
    top10_ratio = (top10s / rounds * 100) if rounds > 0 else 0
    kd = round(kills / (rounds - wins) if (rounds - wins) > 0 else kills, 2)
    avg_dmg = (damage_dealt / rounds) if rounds > 0 else 0
    hs_pct = (headshot_kills / kills * 100) if kills > 0 else 0
    survival_time = (time_survived / rounds) if rounds > 0 else 0

    mins = int(survival_time // 60)
    secs = int(survival_time % 60)
    surv_fmt = f"{mins}분 {secs:02d}초"

    # 임베드 필드 추가 (좌우 정렬)
    embed.add_field(name="게임 수", value=f"{rounds:,}판", inline=True)
    embed.add_field(name="승률", value=f"{win_rate:.2f}%", inline=True)

    embed.add_field(name="K/D", value=f"{kd:.2f}", inline=True)
    embed.add_field(name="킬 수", value=f"{kills:,}", inline=True)

    embed.add_field(name="평균 데미지", value=f"{avg_dmg:.2f}", inline=True)
    embed.add_field(name="Top10 진입률", value=f"{top10_ratio:.2f}%", inline=True)

    embed.add_field(name="헤드샷률", value=f"{hs_pct:.2f}%", inline=True)
    embed.add_field(name="평균 생존시간", value=surv_fmt, inline=True)

    embed.add_field(name="최장 저격 거리", value=f"{longest_kill:.1f}m", inline=True)

    # 스쿼드 모드일 때 피드백 표시
    if mode == "squad":
        metrics, error = extract_squad_metrics(stats)
        if metrics:
            avg_damage, kd_val, win_rate_val = metrics
            dmg_msg, kd_msg, win_msg = detailed_feedback(avg_damage, kd_val, win_rate_val)
            feedback_text = f"{dmg_msg}\n{kd_msg}\n{win_msg}"
        else:
            feedback_text = error
        embed.add_field(name="📊 SQUAD 분석 피드백", value=feedback_text, inline=False)

    return embed






def generate_ranked_embed(ranked_stats, nickname="플레이어"):
    embed = discord.Embed(title=f"{nickname} - 랭크 전적", color=discord.Color.gold())

    if not ranked_stats or "data" not in ranked_stats:
        embed.description = "❌ 랭크 전적 정보가 없습니다."
        return embed, None

    modes = ranked_stats["data"]["attributes"]["rankedGameModeStats"]
    for mode in ["solo", "duo", "squad"]:
        m = modes.get(mode)
        if not m:
            continue

        tier = m.get("currentTier", {}).get("tier", "Unranked")
        sub = m.get("currentTier", {}).get("subTier", "")
        point = m.get("currentRankPoint", 0)
        rounds = m.get("roundsPlayed", 0)
        wins = m.get("wins", 0)
        kd = m.get("kda", 0.0)
        win_pct = wins / rounds * 100 if rounds else 0

        embed.add_field(
            name=f"🏅 {mode.upper()}",
            value=(
                f"티어: **{tier} {sub}**\n"
                f"RP: **{point}** | K/D: **{kd:.2f}**\n"
                f"게임: **{rounds}** | 승률: **{win_pct:.2f}%**"
            ),
            inline=False
        )

    # ✅ RP 가장 높은 티어로 이미지 결정
    tier, sub, _ = pick_best_rank_tier(ranked_stats)
    img_path = get_rank_image_path(tier, sub)
    file = None
    if os.path.exists(img_path):
        file = discord.File(img_path, filename="rank.png")
        embed.set_thumbnail(url="attachment://rank.png")

    return embed, file


@tree.command(name="전적", description="PUBG 닉네임으로 전적 조회", guild=discord.Object(id=GUILD_ID))
async def 전적(interaction: discord.Interaction, 닉네임: str):
    await interaction.response.defer()
    try:
        player_id = get_player_id(닉네임)  # ✅ account.xxxx 형식의 고유 ID
        season_id = get_season_id()
        stats = get_player_stats(player_id, season_id)
        ranked = get_player_ranked_stats(player_id, season_id)

        squad_metrics, error = extract_squad_metrics(stats)
        if squad_metrics:
            save_player_stats_to_file(
                닉네임,
                squad_metrics,
                ranked,
                stats=stats,
                discord_id=interaction.user.id,
                pubg_id=닉네임.strip(),  # ✅ 닉네임 기반으로 pubg_id 저장
                source="전적명령"
            )

        embed = generate_mode_embed(stats, "squad", 닉네임)
        view = ModeSwitchView(nickname=닉네임, stats=stats, ranked_stats=ranked)
        await interaction.followup.send(embed=embed, view=view)

    except Exception as e:
        await interaction.followup.send(f"❌ 오류 발생: {e}", ephemeral=True)









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


from scipy.stats import norm

def compute_final_score(raw_value, mean, std, n, C=500, confidence=0.95):
    """
    성과를 Z-Score로 변환하고, 신뢰 하한과 유지난이도 보정을 반영한 점수 계산 함수.
    
    - raw_value: 사용자 스탯 값
    - mean: 공식 평균
    - std: 사용자 집단 표준편차
    - n: 판 수
    - C: 기준 판수 (default=500)
    - confidence: 신뢰수준 (default=95%)
    """
    if n == 0 or std == 0:
        return -999  # 점수 무효 처리

    z = (raw_value - mean) / std

    # 🧠 신뢰구간 기반 하한값 보정
    z_critical = norm.ppf((1 + confidence) / 2)  # e.g., 1.96 for 95%
    se = std / (n ** 0.5)
    adjusted_z = z - z_critical * (se / std)

    # 🔼 유지 난이도 기반 보정 (판수가 많을수록 점수 상승)
    if n > C:
        factor = (n - C) / C
        bonus = 1 + min(factor * 0.1, 0.15)  # 최대 +15%
        adjusted_z *= bonus

    return adjusted_z





@tree.command(name="전적해설", description="특정 유저 시즌 점수 계산 해설을 확인합니다.", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(닉네임="PUBG 닉네임")
async def 전적해설(interaction: discord.Interaction, 닉네임: str):
    await interaction.response.defer()

    import os, json, statistics
    from scipy.stats import norm

    weights = {
        "avg_damage": 0.28,
        "kd": 0.28,
        "win_rate": 0.20,
        "top10_ratio": 0.08,
        "avg_survive": 0.10,
        "headshot_pct": 0.06
    }

    C_MAP = {
        "avg_damage": 1200,
        "kd": 1200,
        "win_rate": 1500,
        "top10_ratio": 700,
        "avg_survive": 600,
        "headshot_pct": 300
    }

    def compute_final_score(raw_value, mean, std, n, C, bonus_cap=0.15):
        if n == 0 or std == 0:
            return -999.0, 0.0, 1.0
        z = (raw_value - mean) / std
        penalty_factor = n / (n + C)
        adjusted_z = z * penalty_factor

        bonus_multiplier = 1.0
        if z > 0 and n > C:
            bonus_multiplier = 1 + min((n - C) / C * 0.1, bonus_cap)
            adjusted_z *= bonus_multiplier

        return adjusted_z, z, bonus_multiplier

    leaderboard_path = "season_leaderboard.json"
    if not os.path.exists(leaderboard_path):
        return await interaction.followup.send("❌ 시즌 데이터가 없습니다.", ephemeral=True)

    with open(leaderboard_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    players = data.get("players", [])
    player = next((p for p in players if p.get("nickname") == 닉네임), None)
    if not player:
        return await interaction.followup.send(f"❌ '{닉네임}' 님의 시즌 전적을 찾을 수 없습니다.", ephemeral=True)

    squad = player.get("squad", {})
    games = squad.get("rounds_played", 0)
    if games == 0:
        return await interaction.followup.send("❌ 게임 수가 0인 유저는 해설이 제공되지 않습니다.", ephemeral=True)

    keys = list(weights.keys())
    means = {
        "avg_damage": 150.00,
        "kd": 1.00,
        "win_rate": 4.50,
        "top10_ratio": 38.00,
        "headshot_pct": 15.00,
        "avg_survive": 500.00
    }

    metric_lists = {
        k: [p.get("squad", {}).get(k, 0) for p in players if isinstance(p.get("squad"), dict)]
        for k in keys
    }
    stds = {k: max(statistics.pstdev(vals), 1.0) for k, vals in metric_lists.items()}

    explanation_lines = [
        f"🏅 **{닉네임}** 님의 시즌 점수 해설\n",
        f"🎮 게임 수: {games} 판\n"
    ]

    total_score = 0.0
    for key in keys:
        val = squad.get(key, 0)
        mean = means.get(key, 0)
        std = stds[key]

        adj_z, raw_z, bonus_mul = compute_final_score(val, mean, std, games, C_MAP[key])
        contrib = adj_z * weights[key]
        total_score += contrib

        explanation_lines.append(
            f"📊 {key:<12} : {val:.2f} (평균 {mean:.2f}, 표준편차 {std:.2f})\n"
            f"   • Z-Score      : {raw_z:.3f}\n"
            f"   • 보정 Z       : {adj_z:.3f} (판수 보정 C={C_MAP[key]})\n"
            f"   • 보너스 배수  : x{bonus_mul:.3f}\n"
            f"   • 가중치       : {weights[key]:.2f}\n"
            f"   • 점수 기여도  : {contrib:.3f}\n"
        )

    explanation_lines.append(f"🏆 최종 종합 점수: **{total_score:.3f}**\n")
    explanation_lines.append("📌 규칙 요약")
    explanation_lines.append(" - 판수가 적으면 Z-Score가 강하게 줄어듭니다. (Z × n/(n+C))")
    explanation_lines.append(" - 평균 이상 성과(z>0)를 충분한 판수에서 유지하면 최대 15% 보너스")
    explanation_lines.append(" - C값은 지표별로 다르게 적용 (승률=1500, KD=1200 등)")

    await interaction.followup.send("\n".join(explanation_lines), ephemeral=True)





@전적해설.autocomplete("닉네임")
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
                    name=full_nick,  # 자동완성에 보이는 항목 예) 토끼 / N_cafe24_A / 90
                    value=nickname    # 실제 입력될 값: N_cafe24_A
                ))

    return choices[:25]








@tree.command(name="시즌랭킹", description="현재 시즌의 항목별 TOP7을 확인합니다.", guild=discord.Object(id=GUILD_ID))
async def 시즌랭킹(interaction: discord.Interaction):
    await interaction.response.defer()

    import os, json, statistics

    weights = {
        "avg_damage": 0.28,
        "kd": 0.28,
        "win_rate": 0.20,
        "top10_ratio": 0.08,
        "avg_survive": 0.10,
        "headshot_pct": 0.06
    }

    C_MAP = {
        "avg_damage": 1200,
        "kd": 1200,
        "win_rate": 1500,
        "top10_ratio": 700,
        "avg_survive": 600,
        "headshot_pct": 300
    }

    def compute_final_score(raw_value, mean, std, n, C, bonus_cap=0.15):
        if n == 0 or std == 0:
            return -999.0
        z = (raw_value - mean) / std
        penalty_factor = n / (n + C)
        adjusted_z = z * penalty_factor
        if z > 0 and n > C:
            bonus = 1 + min((n - C) / C * 0.1, bonus_cap)
            adjusted_z *= bonus
        return adjusted_z

    def safe_get(p, key):
        squad = p.get("squad", {})
        return squad.get(key, 0) if isinstance(squad, dict) else 0

    # ✅ valid_pubg_ids.json 로드
    try:
        with open("valid_pubg_ids.json", "r", encoding="utf-8") as f:
            valid_data = json.load(f)
    except Exception:
        return await interaction.followup.send("❌ 유효 PUBG ID 목록을 불러오지 못했습니다.", ephemeral=True)

    # ✅ 유효 게임 ID + 디스코드 ID 수집 (is_guest 제외)
    valid_pubg_ids = set()
    valid_discord_ids = set()
    for entry in valid_data:
        if not entry.get("is_guest", False):
            game_id = entry.get("game_id", "").strip().lower()
            discord_id = str(entry.get("discord_id", "")).strip()
            if game_id:
                valid_pubg_ids.add(game_id)
            if discord_id:
                valid_discord_ids.add(discord_id)

    # ✅ season_leaderboard.json 로드
    leaderboard_path = "season_leaderboard.json"
    if not os.path.exists(leaderboard_path):
        return await interaction.followup.send("❌ 저장된 전적 데이터가 없습니다.", ephemeral=True)

    with open(leaderboard_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_players = data.get("players", [])
    total_saved_non_guest = sum(1 for p in raw_players if "(게스트)" not in p.get("nickname", ""))

    # ✅ 유효 필터링 (nickname / pubg_id / discord_id)
    players = []
    for p in raw_players:
        nickname = p.get("nickname", "")
        pubg_id = p.get("pubg_id", "").strip().lower()
        discord_id = str(p.get("discord_id", "")).strip()

        if "(게스트)" in nickname:
            continue
        if pubg_id not in valid_pubg_ids:
            print(f"❌ 제외: pubg_id 불일치 → {pubg_id}")
            continue
        if discord_id not in valid_discord_ids:
            print(f"❌ 제외: discord_id 불일치 → {discord_id}")
            continue

        players.append(p)

    if not players:
        return await interaction.followup.send("❌ 유효한 유저 전적이 없습니다. (게스트 제외 + ID검사 통과자 없음)", ephemeral=True)

    keys = list(weights.keys())
    means = {
        "avg_damage": 150.00,
        "kd": 1.00,
        "win_rate": 4.50,
        "top10_ratio": 38.00,
        "headshot_pct": 15.00,
        "avg_survive": 500.00
    }

    stds = {
        k: max(statistics.pstdev([safe_get(p, k) for p in players]), 1.0)
        for k in keys
    }

    seen_names = set()
    weighted_list = []
    for p in players:
        name = p.get("nickname", "")
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        squad = p.get("squad", {})
        games = squad.get("rounds_played", 0)
        if games == 0:
            continue

        adj_scores = {
            k: compute_final_score(
                raw_value=squad.get(k, 0),
                mean=means[k],
                std=stds[k],
                n=games,
                C=C_MAP[k]
            ) for k in keys
        }

        score = sum(adj_scores[k] * weights[k] for k in keys)
        weighted_list.append((name, score, *[adj_scores[k] for k in keys]))

    weighted_top = sorted(weighted_list, key=lambda x: x[1], reverse=True)[:7]

    def unique_top(lst):
        seen = set()
        result = []
        for item in lst:
            if item[0] not in seen:
                seen.add(item[0])
                result.append(item)
            if len(result) == 7:
                break
        return result

    damage_top = unique_top(sorted([(p["nickname"], safe_get(p, "avg_damage")) for p in players], key=lambda x: x[1], reverse=True))
    kd_top = unique_top(sorted([(p["nickname"], safe_get(p, "kd")) for p in players], key=lambda x: x[1], reverse=True))
    win_top = unique_top(sorted([(p["nickname"], safe_get(p, "win_rate")) for p in players], key=lambda x: x[1], reverse=True))
    rounds_top = unique_top(sorted([(p["nickname"], safe_get(p, "rounds_played")) for p in players], key=lambda x: x[1], reverse=True))
    kills_top = unique_top(sorted([(p["nickname"], safe_get(p, "kills")) for p in players], key=lambda x: x[1], reverse=True))

    rankpoint_list = []
    seen_rank_names = set()
    for p in players:
        name = p.get("nickname", "")
        ranked = p.get("ranked", {})
        if ranked and name not in seen_rank_names:
            seen_rank_names.add(name)
            rankpoint_list.append((name, ranked.get("points", 0), ranked.get("tier", ""), ranked.get("subTier", "")))
    rank_top = sorted(rankpoint_list, key=lambda x: x[1], reverse=True)[:7]

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣"]

    def format_top_score(entries):
        return "```\n" + "\n".join(
            f"{medals[i]} {'*'+entry[0]+'*' if i < 3 else entry[0]:20} {entry[1]:.3f}"
            for i, entry in enumerate(entries)
        ) + "\n```"

    def format_top(entries, is_percentage=False):
        return "```\n" + "\n".join(
            f"{medals[i]} {'*'+entry[0]+'*' if i < 3 else entry[0]:20} {entry[1]:.2f}{'%' if is_percentage else ''}"
            for i, entry in enumerate(entries)
        ) + "\n```"

    def format_top_int(entries):
        return "```\n" + "\n".join(
            f"{medals[i]} {'*'+entry[0]+'*' if i < 3 else entry[0]:20} {entry[1]:>7}"
            for i, entry in enumerate(entries)
        ) + "\n```"

    embed = discord.Embed(
        title=f"🏆 현재 시즌 랭킹 (시즌 ID: {data.get('season_id', '알 수 없음')})",
        color=discord.Color.gold()
    )

    if weighted_top:
        embed.add_field(name="💯 종합 점수 TOP 7", value=format_top_score(weighted_top), inline=False)
    embed.add_field(name="🔫 평균 데미지", value=format_top(damage_top), inline=True)
    embed.add_field(name="⚔️ K/D", value=format_top(kd_top), inline=True)
    embed.add_field(name="🏆 승률", value=format_top(win_top, is_percentage=True), inline=True)
    embed.add_field(name="🎮 게임 수", value=format_top_int(rounds_top), inline=True)
    embed.add_field(name="💀 킬 수", value=format_top_int(kills_top), inline=True)

    if rank_top:
        embed.add_field(
            name="🥇 랭크 포인트",
            value="```\n" + "\n".join(
                f"{medals[i]} {'*'+name+'*' if i < 3 else name} - {tier} {sub} ({points})"
                for i, (name, points, tier, sub) in enumerate(rank_top)
            ) + "\n```",
            inline=False
        )

    embed.add_field(
        name="📌 점수 계산 방식",
        value=(
            "1️⃣ 각 항목은 Z-Score를 사용해 평균 대비 성과를 측정합니다.\n"
            "2️⃣ 판수가 적으면 `Z × (판수 / (판수 + C))`로 강하게 감점됩니다.\n"
            "3️⃣ 평균 이상 성과(z>0)를 판수로 유지하면 최대 15% 보너스가 적용됩니다.\n"
            "4️⃣ C값은 지표별로 다릅니다 (예: 승률=1500, KD=1200).\n"
            "5️⃣ 헤드샷 비중은 낮으며, 평균값은 전체 유저 기준입니다."
        ),
        inline=False
    )

    embed.set_footer(text=f"※ 기준: 저장 유저 {total_saved_non_guest}명 / 유효 계정 {len(players)}명 (게스트 제외 + ID검사 통과)")

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
                 "game_id": game_id.strip().lower(),  # ← 여기 꼭 추가!
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
                    save_player_stats_to_file(nickname, squad_metrics, ranked_stats, stats, discord_id=m["discord_id"], pubg_id=nickname.strip(), source="자동갱신")

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
    import time
    start_time = time.time()

    if interaction.channel.id != 1394331814642057418:
        return await interaction.response.send_message(
            "❌ 이 명령어는 **#오덕도박장** 채널에서만 사용할 수 있습니다.",
            ephemeral=True
        )

    user_id = str(interaction.user.id)
    balances = load_balances()
    user_data = balances.get(user_id, {})
    balance = user_data.get("amount", 0)

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

    # 여기부터 defer 처리
    await interaction.response.defer()

    # 💸 베팅 차감
    balance -= 베팅액

    # 🎲 확률 생성
    success_chance = random.randint(30, 70)
    roll = random.randint(1, 100)

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

    building = get_user_building(user_id)
    stat_gain_text = ""

    # ✅ 도박 성공
    if roll <= success_chance:
        jackpot_chance = get_jackpot_chance(user_id, 0.01)
        is_jackpot = random.random() < jackpot_chance
        multiplier = 4 if is_jackpot else 2
        reward = apply_gamble_bonus(user_id, 베팅액 * multiplier)

        balance += reward

        # 상태치 증가
        if building:
            user_stats = get_user_stats(user_id)
            gained_stats = []
            for stat in ["stability", "risk", "labor", "tech"]:
                if random.random() < 0.15:
                    add_user_stat(user_id, stat, 1)
                    gained_stats.append(stat)
            if gained_stats:
                stat_gain_text = f"\n📈 상태치 증가: {', '.join(gained_stats)}"

        # ✅ 기록 저장
        record_gamble_result(user_id, True)
        title = get_gamble_title(load_balances().get(user_id, {}), True)
        jackpot_msg = "💥 **🎉 잭팟! 4배 당첨!** 💥\n" if is_jackpot else ""

    # ❌ 도박 실패
    else:
        add_oduk_pool(베팅액)
        pool_amt = get_oduk_pool_amount()

        record_gamble_result(user_id, False)
        title = get_gamble_title(load_balances().get(user_id, {}), False)

    # 💾 잔액 저장
    balances[user_id] = {
        **balances.get(user_id, {}),
        "amount": balance,
        "last_updated": datetime.now().isoformat()
    }
    save_balances(balances)

    final_balance = balances[user_id]["amount"]

    # 📤 메시지 출력
    if roll <= success_chance:
        embed = create_embed(
            "🎉 도박 성공!",
            f"{jackpot_msg}(확률: {success_chance}%, 값: {roll})\n{bar}\n"
            f"+{reward:,}원 획득!\n💰 잔액: {final_balance:,}원\n\n🏅 칭호: {title}{stat_gain_text}",
            discord.Color.gold() if is_jackpot else discord.Color.green(),
            user_id
        )
    else:
        embed = create_embed(
            "💀 도박 실패!",
            f"(확률: {success_chance}%, 값: {roll})\n{bar}\n"
            f"-{베팅액:,}원 손실...\n"
            f"🍜 오덕 로또 상금: **{pool_amt:,}원** 적립됨!\n"
            f"🎟️ `/오덕로또참여`로 도전하세요!\n\n"
            f"🏅 칭호: {title}",
            discord.Color.red(),
            user_id
        )

    await interaction.followup.send(embed=embed)


  













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
                reward = apply_gamble_bonus(self.user_id, reward)  # ✅ 건물 효과 적용
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

    add_balance(user_id, -베팅액)

    await interaction.response.defer()
    message = await interaction.followup.send("🎰 슬롯머신 작동 중...", wait=True)

    result = []
    for i in range(5):
        result.append(random.choice(symbols))
        display = " | ".join(result + ["⬜"] * (5 - len(result)))
        await message.edit(content=f"🎰 **슬롯머신 작동 중...**\n| {display} |")
        await asyncio.sleep(0.7)

    result_str = " | ".join(result)

    max_streak = 1
    cur_streak = 1
    for i in range(1, len(result)):
        if result[i] == result[i - 1]:
            cur_streak += 1
            max_streak = max(max_streak, cur_streak)
        else:
            cur_streak = 1

    if max_streak == 5:
        winnings = 베팅액 * 10
        winnings = apply_gamble_bonus(user_id, winnings)  # ✅ 건물 효과 적용
        add_balance(user_id, winnings)
        record_gamble_result(user_id, True)
        titles = get_gamble_title(user_id, True)
        title_str = "\n🏅 칭호: " + ", ".join(titles) if titles else ""
        outcome = f"🎉 **5개 연속 일치! +{winnings:,}원 획득!**{title_str}"
        color = discord.Color.green()

    elif max_streak >= 3:
        winnings = 베팅액 * 4
        winnings = apply_gamble_bonus(user_id, winnings)  # ✅ 건물 효과 적용
        add_balance(user_id, winnings)
        record_gamble_result(user_id, True)
        titles = get_gamble_title(user_id, True)
        title_str = "\n🏅 칭호: " + ", ".join(titles) if titles else ""
        outcome = f"✨ **{max_streak}개 연속 일치! +{winnings:,}원 획득!**{title_str}"
        color = discord.Color.green()

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
            
            # ✅ 건물 효과 적용
            net_gain = apply_gamble_bonus(str(winner.id), net_gain)
            
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





@tree.command(name="청소", description="채널의 이전 메시지를 삭제합니다.", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(개수="삭제할 메시지 개수 (최대 100개)")
async def 청소(interaction: discord.Interaction, 개수: int):
    if not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("🚫 메시지를 삭제할 권한이 없습니다.", ephemeral=True)

    if 개수 < 1 or 개수 > 100:
        return await interaction.response.send_message("❌ 1~100 사이의 숫자를 입력하세요.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)  # ✅ 먼저 응답 예약

    deleted = await interaction.channel.purge(limit=개수)
    await interaction.followup.send(f"🧹 {len(deleted)}개의 메시지를 삭제했습니다.", ephemeral=True)











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
            update_job_record(user_id, 0, job_type="default", success=False)
            await msg.reply("❌ 문장이 틀렸습니다. 알바 실패!", mention_author=False)
            return

        elapsed = (end_time - start_time).total_seconds()
        base_reward = 1200
        penalty = int(elapsed * 60)
        reward = max(120, base_reward - penalty)
        reward = apply_alba_bonus(user_id, reward)

        # 🎉 잭팟 확률 1%
        is_jackpot = random.random() < 0.01
        if is_jackpot:
            reward *= 3

        # ✅ 초과근무 여부
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

        # 💸 정상 보상
        add_balance(user_id, reward)

        # ✅ 상태치 증가 확률 적용
        stat_gain_text = ""
        if random.random() < 0.4:
            add_user_stat(user_id, "labor", 1)
            stat_gain_text = "\n📈 상태치 증가: labor +1"

        record = load_job_records().get(user_id, {})
        today_used = record.get("daily", {}).get(today, 0)
        remaining = max(0, 5 - today_used)

        message = (
            f"✅ **{elapsed:.1f}초** 만에 성공!\n"
            f"💰 **{reward:,}원**을 획득했습니다."
        )
        if is_jackpot:
            message += "\n🎉 **성실 알바생 임명! 사장님의 은혜로 알바비를 3배 지급합니다.** 🎉"
        message += stat_gain_text
        message += f"\n📌 오늘 남은 알바 가능 횟수: **{remaining}회** (총 5회 중)"

        await msg.reply(message, mention_author=False)

    except asyncio.TimeoutError:
        update_job_record(user_id, 0, job_type="default", success=False)
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
                compensation_with_bonus = apply_alba_bonus(user_id, compensation)
                bonus_amount = compensation_with_bonus - compensation
                add_balance(user_id, compensation_with_bonus)

                msg = (
                    f"💢 초과근무를 했지만 악덕 오덕사장이 알바비 **{reward:,}원**을 가로챘습니다...\n"
                    f"⚖️ 고용노동부 신고 성공! **{compensation_with_bonus:,}원**을 되찾았습니다!"
                )
                if bonus_amount > 0:
                    msg += f"\n🏢 건물 효과로 추가 보너스 +**{bonus_amount:,}원**!"
                msg += (
                    f"\n🏦 현재 오덕잔고: **{pool_amount:,}원**\n"
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
            # ✅ 정상 보상 처리
            base_reward = reward
            reward_with_bonus = apply_alba_bonus(user_id, reward)
            bonus_amount = reward_with_bonus - base_reward
            add_balance(user_id, reward_with_bonus)

            msg = f"📦 박스를 정확히 치웠습니다! 💰 **{reward_with_bonus:,}원** 획득!"
            if bonus_amount > 0:
                msg += f"\n🏢 건물 보유 효과로 추가 보너스 +**{bonus_amount:,}원**!"
            if is_jackpot:
                msg += "\n🎉 **우수 알바생! 보너스 지급으로 2배 보상!** 🎉"

            # ✅ 상태치 확률 상승 처리 (건물 보유자만)

            if get_user_building(user_id):
                stat_gains = []
                for stat in ["stability", "risk", "labor", "tech"]:
                    if random.random() < 0.15:
                        add_user_stat(user_id, stat, 1)
                        stat_gains.append(stat)
                if stat_gains:
                    msg += f"\n📈 상태치 증가: {', '.join(stat_gains)}"


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
            base_interest = int(take * 0.02)
            interest = apply_interest_bonus(user_id, base_interest)  # ✅ 건물 보정 적용
            interest_total += interest

        updated_deposits.append(d)

        if remaining <= 0:
            continue  # 🔄 break → continue 유지

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
        deposits = list(user_data.get("deposits", []))
        if not deposits:
            continue

        total_balance = sum(d.get("amount", 0) - d.get("used", 0) for d in deposits)

        if total_balance > 5_000_000:
            # ✅ 초과분의 20% 감가, 최소 500만 원 보장
            excess = total_balance - 5_000_000
            to_cut = int(excess * 0.2)  # 20%
            remaining_cut = to_cut

            # 오래된 순서부터 차감
            sorted_deposits = sorted(deposits, key=lambda d: d.get("timestamp", 0))
            updated_deposits = []

            for idx, deposit in enumerate(sorted_deposits):
                amount = int(deposit.get("amount", 0))
                used = int(deposit.get("used", 0))
                available = amount - used

                if available <= 0:
                    updated_deposits.append(deposit)
                    continue

                reduce = min(available, remaining_cut)
                if reduce > 0:
                    deposit["used"] = used + reduce
                    remaining_cut -= reduce

                updated_deposits.append(deposit)

                if remaining_cut <= 0:
                    # ✅ 남은 예치금들 유지(리스트 잘림 방지)
                    updated_deposits.extend(sorted_deposits[idx + 1:])
                    break
            # for가 자연 종료된 경우(updated_deposits에 이미 전부 들어있음) 별도 처리 불필요

            # 사용 완료된(남은 금액 0) deposit 제거
            bank[user_id]["deposits"] = [
                d for d in updated_deposits if (int(d.get("amount", 0)) - int(d.get("used", 0))) > 0
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

            # ── 감가 정책 안내 (정책/주기/최소보장/예시) ─────────────────────────
            APPLY_MIN   = 5_000_000   # 적용 기준: 500만 원 초과
            RATE        = 0.20        # 초과분의 20% 감가
            LOOP_HOURS  = 6           # 몇 시간마다 적용되는지 (decorator와 일치시켜주세요)

            lines.append("\n📊 **은행 감가 안내**")
            lines.append(f"- 적용 기준: 총 예치금 **{APPLY_MIN:,}원 초과**")
            lines.append(f"- 주기: **{LOOP_HOURS}시간마다** 적용")
            lines.append(f"- 차감 방식: 초과분의 **{int(RATE * 100)}%** 차감")
            lines.append(f"- 최소 보장: **{APPLY_MIN:,}원** (이 금액 이하는 감가되지 않음)")

            # 금액별 예시 (이번 회차 기준, 가독용)
            examples = [6_000_000, 10_000_000, 20_000_000, 50_000_000]
            example_lines = []
            for ex in examples:
                if ex > APPLY_MIN:
                    excess = ex - APPLY_MIN
                    cut = int(excess * RATE)
                    after = ex - cut
                    example_lines.append(f"  · {ex:,}원 → {after:,}원 (이번 회차 {cut:,}원 차감)")
                else:
                    example_lines.append(f"  · {ex:,}원 → 변동 없음 (감가 기준 미만)")

            lines.append("\n🔎 **예시(이번 회차 기준)**")
            lines.extend(example_lines)
            # ────────────────────────────────────────────────────────────────

            await channel.send("\n".join(lines))





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

            user_id = str(self.user.id)
            count = get_today_real_estate_count(user_id)
            if count < 3:
                loss_multiplier = 1.0
            elif count < 6:
                loss_multiplier = 1.2
            elif count < 10:
                loss_multiplier = 1.5
            else:
                loss_multiplier = 2.0

            loss_shield = has_real_estate_shield(user_id)
            rocket_up = False
            bonus_boost = False

            if random.random() < 0.01:
                profit_rate = 300
                rocket_up = True
            else:
                profit_rate = random.randint(-100, 80)
                if profit_rate < 0:
                    profit_rate = int(profit_rate * loss_multiplier)
                    profit_rate = max(profit_rate, -100)
                    if loss_shield:
                        profit_rate = int(profit_rate * 0.6)
                        profit_rate = max(profit_rate, -100)

            if not rocket_up and random.random() < 0.03:
                bonus_boost = True
                profit_rate += 50

            profit_amount_raw = int(self.invest_amount * (profit_rate / 100))
            profit_amount = apply_investment_bonus(user_id, profit_amount_raw)

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

            effect_text = ""
            if rocket_up:
                effect_text = "💥 지역 개발 대박! 재개발 호재!"
            elif profit_rate >= 40:
                effect_text = "📊 재건축 발표로 급등!"
            elif profit_rate > 10:
                effect_text = "📈 집값 상승세로 이익 발생"
            elif profit_rate > 0:
                effect_text = "📦 소폭 수익 발생"
            elif profit_rate == 0:
                effect_text = "😐 부동산 시장 조용함 (본전)"
            elif profit_rate > -30:
                effect_text = "🏚️ 거래 침체로 손실..."
            elif profit_rate > -70:
                effect_text = "🔥 하락장! 큰 손해 발생"
            else:
                effect_text = "💀 부동산 사기! 전액 손실..."

            title_badge = "🚀 로켓 캐처" if rocket_up else \
                          "💼 투자 귀재" if profit_rate >= 40 else \
                          "💀 투기의 귀재" if profit_rate <= -70 else None

            title_line = f"🎖️ 칭호: {title_badge}\n" if title_badge else ""
            bonus_line = "✨ 보너스 수익률 +50%\n" if bonus_boost else ""
            loss_line = "🛡️ 손실 완화 적용됨 (건물 효과)\n" if loss_shield and profit_rate < 0 else ""

            # 📈 상태치 증가 (건물 보유자만)

            stat_line = ""
            if get_user_building(user_id):
                gained_stats = []
                if profit_rate >= 30 and random.random() < 0.3:
                    add_user_stat(user_id, "stability", 1)
                    gained_stats.append("stability")
                if profit_rate <= -50 and random.random() < 0.3:
                    add_user_stat(user_id, "tech", 1)
                    gained_stats.append("tech")
                if gained_stats:
                    stat_line = f"📈 상태치 증가: {', '.join(gained_stats)}\n"

            embed = discord.Embed(
                title="🚀 대박 투자 성공!" if profit_amount >= 0 else "📉 투자 실패...",
                description=(
                    f"👤 투자자: {interaction.user.mention}\n"
                    f"📍 투자 지역: **{region}**\n"
                    f"{title_line}"
                    f"{bonus_line}"
                    f"{loss_line}"
                    f"{stat_line}"
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

    # ✅ created_at 방어 처리
    raw_created_at = loan.get("created_at")
    raw_last_checked = loan.get("last_checked")

    if not raw_created_at or not isinstance(raw_created_at, str) or raw_created_at.strip() == "":
        
        return None

    try:
        created_at = datetime.fromisoformat(raw_created_at)
        last_checked = datetime.fromisoformat(raw_last_checked) if raw_last_checked else created_at
    except ValueError as e:
        print(f"❌ 자동상환 오류 - 유저 {user_id}: 날짜 파싱 실패 → {e}")
        return None

    now = datetime.now(KST)
    if (now - last_checked).total_seconds() < 1740 and not force:
        return None

    rate = loan.get("interest_rate", 0.05)
    total_due = calculate_loan_due(loan["amount"], raw_created_at, rate, force_future_30min=False)

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

        grade_message, updated_credit_grade, _ = get_grade_recovery_message(data)

        # ✅ 대출 초기화 전 정보 백업
        created_at_backup = raw_created_at

        clear_loan(user_id)

        # ✅ 최신 상태 복구
        loans = load_loans()
        loans[user_id] = {
            "amount": 0,
            "credit_grade": updated_credit_grade,
            "consecutive_successes": data["consecutive_successes"],
            "consecutive_failures": 0,
            "created_at": created_at_backup,
            "last_checked": now.isoformat(),
            "unpaid_days": 0,
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

        set_balance(user_id, 0)
        reset_bank_deposits(user_id)
        reset_investments(user_id)
        add_to_bankrupt_log(user_id)

        now_str = now.isoformat()
        loans = load_loans()
        loans[user_id] = {
            "amount": 0,
            "credit_grade": "F",
            "consecutive_successes": 0,
            "consecutive_failures": 0,
            "created_at": now_str,
            "last_checked": now_str,
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
        raw_created_at,
        total_due,
        f"❌ 결과: 상환 실패! {get_failure_message(data['credit_grade'], data['consecutive_failures'])}\n💣 누적 연체: {data['consecutive_failures']}회"
    )





@tree.command(name="상환", description="현재 대출금을 즉시 상환 시도합니다.", guild=discord.Object(id=GUILD_ID))
async def 상환(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)  # ✅ 3초 이상 처리 대비

    user_id = str(interaction.user.id)
    member = interaction.user

    loan = get_user_loan(user_id)
    if not loan or loan.get("amount", 0) <= 0:
        return await interaction.followup.send("✅ 현재 상환할 대출금이 없습니다.")

    # 수동 상환 시도
    result = await try_repay(user_id, member, force=True)

    if result:
        await interaction.followup.send(result)  # ✅ followup 사용
    else:
        await interaction.followup.send("❌ 상환 실패! 잔액이 부족하거나 처리 중 오류가 발생했습니다.")











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

            # ✅ 감지된 유저에게 5만원 보상 지급
            for user_id, member in detected_users.items():
                add_balance(str(user_id), 50_000)
                log(f"💰 치킨 보상 지급: {member.display_name} (5만원)")

            # ✅ 오덕도박장 채널로 보상 안내 Embed 전송
            dokdo_channel = bot.get_channel(DOKDO_CHANNEL_ID)
            if dokdo_channel:
                names = ', '.join(member.display_name for member in detected_users.values())
                reward_embed = discord.Embed(
                    title="💰 치킨 보상 지급!",
                    description=f"🍗 **{ch_key}** 채널의 유저들에게 1인당 **5만원**이 지급되었습니다!\n\n"
                                f"👑 수령자: {names}",
                    color=discord.Color.green()
                )
                reward_embed.set_footer(text="오덕봇 보상 시스템")
                await dokdo_channel.send(embed=reward_embed)
                
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


import sqlite3
import os
from datetime import datetime

DB_PATH = "buildings.db"

STAT_KEYS = ["stability", "risk", "labor", "tech"]

def get_db_connection():
    return sqlite3.connect(DB_PATH)

    
# ✅ 건물 효과 연동 통합 적용 코드

# 🧱 건물 효과 정의
BUILDING_EFFECTS = {
    "alba_bonus": {"target": "alba", "type": "percent_increase", "value": 0.2},
    "gamble_bonus": {"target": "gamble", "type": "percent_increase", "value": 0.15},
    "jackpot_chance": {"target": "jackpot_chance", "type": "percent_increase", "value": 0.1},
    "exp_boost": {"target": "exp", "type": "percent_increase", "value": 0.3},
    "invest_bonus": {"target": "invest", "type": "percent_increase", "value": 0.1},
    "bank_interest": {"target": "bank_interest", "type": "percent_increase", "value": 0.05},
}


# ✅ 도박 보상 / 잭팟 확률에 건물 효과 적용

def apply_gamble_bonus(user_id, base_reward):
    user_building = get_user_building(user_id)
    if not user_building:
        return base_reward

    building_id = user_building.get("building_id")
    level = user_building.get("level", 1)
    building_def = BUILDING_DEFS.get(building_id)
    if not building_def:
        return base_reward

    effect_key = building_def.get("effect")
    if effect_key != "gamble_bonus":
        return base_reward

    bonus = get_effective_building_value(building_id, level)
    return int(base_reward * (1 + bonus))

# ✅ 잭팟 확률 보정
def get_jackpot_chance(user_id, base_chance):
    user_building = get_user_building(user_id)
    if not user_building:
        return base_chance

    building_id = user_building.get("building_id")
    level = user_building.get("level", 1)
    building_def = BUILDING_DEFS.get(building_id)
    if not building_def:
        return base_chance

    if building_def.get("effect") != "jackpot_chance":
        return base_chance

    bonus = get_effective_building_value(building_id, level)
    return base_chance + bonus



# ✅ 알바 보상 보정
def apply_alba_bonus(user_id, base_reward):
    building = get_user_building(user_id)
    if not building:
        return base_reward

    building_id = building.get("building_id")
    level = building.get("level", 1)
    building_def = BUILDING_DEFS.get(building_id)
    if not building_def or building_def.get("effect") != "alba_bonus":
        return base_reward

    bonus = get_effective_building_value(building_id, level)
    return int(base_reward * (1 + bonus))

# ✅ 투자 수익 보정
def apply_investment_bonus(user_id, reward):
    building = get_user_building(user_id)
    if not building:
        return reward

    building_id = building.get("building_id")
    level = building.get("level", 1)
    building_def = BUILDING_DEFS.get(building_id)
    if not building_def or building_def.get("effect") != "invest_bonus":
        return reward

    bonus = get_effective_building_value(building_id, level)
    return int(reward * (1 + bonus))


# ✅ 은행 이자 보정
def apply_interest_bonus(user_id, interest):
    building = get_user_building(user_id)
    if not building:
        return interest

    building_id = building.get("building_id")
    level = building.get("level", 1)
    building_def = BUILDING_DEFS.get(building_id)
    if not building_def or building_def.get("effect") != "bank_bonus":
        return interest

    bonus = get_effective_building_value(building_id, level)
    return int(interest * (1 + bonus))


# ✅ 경험치 보정
def apply_exp_boost(user_id, base_exp):
    building = get_user_building(user_id)
    if not building:
        return base_exp

    building_id = building.get("building_id")
    level = building.get("level", 1)
    building_def = BUILDING_DEFS.get(building_id)
    if not building_def or building_def.get("effect") != "exp_boost":
        return base_exp

    bonus = get_effective_building_value(building_id, level)
    return int(base_exp * (1 + bonus))


# ✅ 부동산 손실 보호 여부
def has_real_estate_shield(user_id: str) -> bool:
    building = get_user_building(user_id)
    if not building:
        return False

    building_id = building.get("building_id")
    building_def = BUILDING_DEFS.get(building_id)
    if not building_def:
        return False

    return building_def.get("effect") == "real_estate_shield"





import math

STAT_KEYS = ["stability", "risk", "labor", "tech"]

BUILDING_DEFS = {
    "convenience_store": {
        "name": "🏪 편의점",
        "type": "안정형",
        "price": 800_000,
        "base_reward": 4_000,
        "exp_gain": 3,
        "max_level": 30,
        "daily_cap": 100_000,
        "traits": ["stability"],
        "effect": "alba_bonus",
        "level_requirements": {
            2: {"stability": 10}, 5: {"stability": 25}, 10: {"stability": 50}, 20: {"stability": 80}
        },
        "description": "💼 알바 수익 증가 + 안정적 수익"
    },
    "casino": {
        "name": "🎰 카지노",
        "type": "고위험",
        "price": 990_000,
        "base_reward": 9_900,
        "exp_gain": 4,
        "max_level": 30,
        "daily_cap": 150_000,
        "traits": ["risk"],
        "effect": "jackpot_chance",
        "level_requirements": {
            2: {"risk": 20}, 5: {"risk": 45}, 10: {"risk": 100}, 20: {"risk": 160}
        },
        "description": "🎰 도박 잭팟 확률 증가"
    },
    "academy": {
        "name": "📚 학원",
        "type": "성장형",
        "price": 400_000,
        "base_reward": 4_000,
        "exp_gain": 5,
        "max_level": 30,
        "daily_cap": 90_000,
        "traits": ["tech", "labor"],
        "effect": "exp_boost",
        "level_requirements": {
            2: {"tech": 10, "labor": 10}, 5: {"tech": 40, "labor": 30}, 10: {"tech": 65, "labor": 60}
        },
        "description": "📖 경험치 획득량 증가"
    },
    "apartment": {
        "name": "🏢 아파트",
        "type": "안정형",
        "price": 990_000,
        "base_reward": 9_900,
        "exp_gain": 3,
        "max_level": 30,
        "daily_cap": 100_000,
        "traits": ["stability", "risk"],
        "effect": "real_estate_shield",
        "level_requirements": {
            2: {"stability": 10}, 5: {"stability": 35}, 10: {"stability": 70}
        },
        "description": "📉 부동산 손실률을 줄여주는 안정형 자산"
    },
    
    "mall": {
        "name": "🏬 백화점",
        "type": "복합형",
        "price": 650_000,
        "base_reward": 6_500,
        "exp_gain": 4,
        "max_level": 30,
        "daily_cap": 120_000,
        "traits": ["stability", "tech"],
        "effect": "bank_bonus",
        "level_requirements": {
            2: {"stability": 15, "tech": 10}, 5: {"stability": 45, "tech": 40}, 10: {"stability": 80, "tech": 80}
        },
        "description": "🏦 은행 이자 증가"
    }
}

BUILDING_EFFECTS = {
    "alba_bonus": {"target": "alba", "type": "multiplier", "value": 0.2},
    "jackpot_chance": {"target": "jackpot", "type": "chance", "value": 0.05},
    "bank_bonus": {"target": "bank_interest", "type": "multiplier", "value": 0.3},
    "exp_boost": {"target": "exp", "type": "multiplier", "value": 1.25},
    "real_estate_shield": {"target": "real_estate", "type": "loss_reduction", "value": 0.4}
}

def get_levelup_cost(level: int) -> int:
    return int(50_000 * (1.1 ** (level - 1)))

def get_effective_building_value(building_id: str, level: int) -> float:
    building_def = BUILDING_DEFS.get(building_id)
    if not building_def:
        return 0.0
    effect_key = building_def.get("effect")
    base = BUILDING_EFFECTS.get(effect_key, {}).get("value", 0.0)
    factor = 1 + (level - 1) / 29
    return base * factor

def get_user_building(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM buildings WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {
            "building_id": row[1],
            "level": row[2],
            "exp": row[3],
            "today_reward": row[4],
            "last_updated": row[5]
        }
    return None

def set_user_building(user_id, data):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO buildings
        (user_id, building_id, level, exp, today_reward, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        data.get("building_id"),
        data.get("level", 1),
        data.get("exp", 0),
        data.get("today_reward", 0),
        data.get("last_updated")
    ))
    conn.commit()
    conn.close()

def clear_user_building(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM buildings WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM building_stats WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return {
            "stability": row[1],
            "risk": row[2],
            "labor": row[3],
            "tech": row[4]
        }
    return {k: 0 for k in STAT_KEYS}

def add_user_stat(user_id: str, stat: str, amount: int):
    stats = get_user_stats(user_id)
    stats[stat] = stats.get(stat, 0) + amount
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO building_stats
        (user_id, stability, risk, labor, tech)
        VALUES (?, ?, ?, ?, ?)
    """, (
        user_id,
        stats["stability"],
        stats["risk"],
        stats["labor"],
        stats["tech"]
    ))
    conn.commit()
    conn.close()

def reset_user_stats(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE building_stats SET
        stability = 0, risk = 0, labor = 0, tech = 0
        WHERE user_id = ?
    """, (user_id,))
    conn.commit()
    conn.close()

def get_all_buildings():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM buildings")
    rows = cur.fetchall()
    conn.close()
    result = {}
    for row in rows:
        result[row[0]] = {
            "building_id": row[1],
            "level": row[2],
            "exp": row[3],
            "today_reward": row[4],
            "last_updated": row[5]
        }
    return result

def get_required_exp(level: int) -> int:
    return int(100 + (level - 1) ** 2.7 * 25)

def can_level_up(user_id: str, data: dict) -> tuple[bool, str]:
    b = BUILDING_DEFS.get(data["building_id"])
    lv = data["level"]
    next_lv = lv + 1
    if next_lv > b["max_level"]:
        return False, "🏁 최대 레벨 도달"

    messages = []
    ok = True

    # 경험치 조건
    req_exp = get_required_exp(lv)
    if data["exp"] < req_exp:
        messages.append(f"🧪 경험치 부족: {data['exp']} / {req_exp}")
        ok = False

    # 상태치 조건
    stat_req = b.get("level_requirements", {}).get(next_lv)
    if stat_req:
        stats = get_user_stats(user_id)
        for stat, req in stat_req.items():
            current = stats.get(stat, 0)
            if current < req:
                messages.append(f"🔧 상태치 부족: {stat} {current} / {req}")
                ok = False

    # 자금 조건
    cost = get_levelup_cost(lv)
    wallet = get_balance(user_id)
    if wallet < cost:
        messages.append(f"💸 자금 부족: {wallet:,} / {cost:,}")
        ok = False

    return ok, "\n".join(messages) if messages else "레벨업 가능"

def perform_level_up(user_id: str):
    data = get_user_building(user_id)
    if not data:
        return "❌ 건물 없음"

    building_def = BUILDING_DEFS.get(data["building_id"])
    level = data["level"]
    next_level = level + 1

    if next_level > building_def["max_level"]:
        return "🏁 최대 레벨에 도달했습니다."

    messages = []
    can_upgrade = True

    # ✅ 경험치 체크
    required_exp = get_required_exp(level)
    current_exp = data.get("exp", 0)
    if current_exp < required_exp:
        messages.append(f"🧪 경험치 부족: {current_exp} / {required_exp}")
        can_upgrade = False

    # ✅ 상태치 체크
    stat_req = building_def.get("level_requirements", {}).get(next_level, {})
    user_stats = get_user_stats(user_id)
    for stat, required in stat_req.items():
        user_value = user_stats.get(stat, 0)
        if user_value < required:
            messages.append(f"📊 상태치 부족: `{stat}` {user_value} / {required}")
            can_upgrade = False

    # ✅ 자금 체크
    cost = get_levelup_cost(level)
    user_money = get_balance(user_id)
    if user_money < cost:
        messages.append(f"💸 잔액 부족: {user_money:,} / 필요 {cost:,}원")
        can_upgrade = False

    if not can_upgrade:
        return "\n".join(messages)

    # ✅ 조건 충족 → 레벨업 진행
    add_balance(user_id, -cost)
    data["level"] += 1
    data["exp"] -= required_exp
    set_user_building(user_id, data)

    # ✅ 상태치 초기화
    reset_user_stats(user_id)

    return f"🎉 Lv.{data['level']} 달성! 💸 비용 {cost:,}원 지불됨 (🔧 상태치 초기화됨)"




@tree.command(name="건물주", description="건물을 보유한 유저 목록을 확인합니다.", guild=discord.Object(id=GUILD_ID))
async def 건물주(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    building_data = get_all_buildings()
    if not building_data:
        return await interaction.followup.send("🏚️ 현재 건물을 보유한 유저가 없습니다.")

    lines = []
    for user_id, data in building_data.items():
        member = interaction.guild.get_member(int(user_id))
        if member:
            building_id = data.get("building_id", "unknown")
            level = data.get("level", 1)
            building_name = BUILDING_DEFS.get(building_id, {}).get("name", "❓알 수 없음")
            lines.append(f"👤 {member.display_name} - {building_name} Lv.{level}")

    if not lines:
        return await interaction.followup.send("🏚️ 건물 보유자가 없습니다.")

    # 🔹 한 번에 25명씩 나눠서 출력
    CHUNK_SIZE = 25
    chunks = [lines[i:i+CHUNK_SIZE] for i in range(0, len(lines), CHUNK_SIZE)]

    for i, chunk in enumerate(chunks):
        desc = "\n".join(chunk)
        embed = discord.Embed(
            title="🏘️ 건물주 목록" + (f" (Page {i+1})" if len(chunks) > 1 else ""),
            description=desc,
            color=discord.Color.blue()
        )
        if i == 0:
            await interaction.followup.send(embed=embed)
        else:
            await interaction.channel.send(embed=embed)







@tree.command(name="건물레벨업", description="조건을 만족하면 건물의 레벨을 올립니다.", guild=discord.Object(id=GUILD_ID))
async def 건물레벨업(interaction: discord.Interaction):
    user_id = str(interaction.user.id)

    data = get_user_building(user_id)
    if not data:
        return await interaction.response.send_message("🏚️ 건물을 보유하고 있지 않습니다.", ephemeral=True)

    result = perform_level_up(user_id)

    color = discord.Color.gold() if "달성" in result else discord.Color.red()
    await interaction.response.send_message(embed=discord.Embed(
        title="📈 건물 레벨업 결과",
        description=result,
        color=color
    ))



# ✅ 자동완성 함수
async def 건물_자동완성(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(
            name=f"{v['name']} - {v['price']:,}원 ({v['description']})",
            value=k
        )
        for k, v in BUILDING_DEFS.items()
        if current.lower() in k.lower() or current in v["name"]
    ][:25]

# ✅ 명령어 정의
@tree.command(name="건물구입", description="건물을 구입하여 매일 자동 보상을 받습니다.", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(건물="구매할 건물")
async def 건물구입(interaction: discord.Interaction, 건물: str):
    user_id = str(interaction.user.id)
    balance = get_balance(user_id)

    if get_user_building(user_id):
        return await interaction.response.send_message("❌ 이미 건물을 보유 중입니다. `/건물정보`를 확인하세요.", ephemeral=True)

    building = BUILDING_DEFS.get(건물)
    if not building:
        return await interaction.response.send_message("❌ 존재하지 않는 건물입니다.", ephemeral=True)

    if balance < building["price"]:
        return await interaction.response.send_message(f"💰 잔액 부족: {balance:,}원 / 필요 {building['price']:,}원", ephemeral=True)

    # 건물 구매 처리
    set_user_building(user_id, {
        "building_id": 건물,
        "level": 1,
        "exp": 0,
        "today_reward": 0,  # ✅ 기존 pending_reward → today_reward 로 통일
        "last_updated": datetime.now(KST).isoformat()
    })
    add_balance(user_id, -building["price"])

    await interaction.response.send_message(
        f"✅ {building['name']}를 구입했습니다! 매일 자동 보상이 누적됩니다.\n"
        f"💰 가격: {building['price']:,}원\n🔧 특성: {', '.join(building['traits'])}\n🧱 효과: {building['description']}"
    )

# ✅ 자동완성 연결
건물구입.autocomplete("건물")(건물_자동완성)


# 🧮 레벨에 따른 보상 계산 함수
def get_building_reward(base_reward: int, level: int) -> int:
    # 예: 레벨마다 보상 +5% 증가
    multiplier = 1 + 0.05 * (level - 1)
    return int(base_reward * multiplier)

# 🧮 레벨업에 필요한 경험치 계산 (예시: 20 + 10 * (레벨^1.2))
def get_required_exp(level: int) -> int:
    return int(20 + 10 * (level ** 1.2))

@tree.command(name="건물정보", description="현재 보유 중인 건물의 상태를 확인합니다.", guild=discord.Object(id=GUILD_ID))
async def 건물정보(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    data = get_user_building(user_id)

    if not data:
        return await interaction.response.send_message("🏚️ 아직 건물을 보유하고 있지 않습니다.", ephemeral=True)

    b = BUILDING_DEFS[data["building_id"]]
    stats = get_user_stats(user_id)

    level = data["level"]
    reward = get_building_reward(b["base_reward"], level)
    cap = b.get("daily_cap", 999_999)
    today = data.get("today_reward", 0)
    rate = int(today / cap * 100) if cap else 0

    embed = discord.Embed(
        title=f"{b['name']} 정보",
        description=b["description"],
        color=discord.Color.green()
    )

    # 기본 정보
    embed.add_field(name="📈 레벨", value=f"{level} / {b['max_level']}")
    embed.add_field(name="🧪 경험치", value=f"{data['exp']} / {get_required_exp(level)}")
    embed.add_field(name="💰 예상 보상", value=f"{reward:,}원 (30분당)")
    embed.add_field(name="💼 오늘 받은 보상", value=f"{today:,} / {cap:,}원 ({rate}%)")
    embed.add_field(
        name="🔧 상태치",
        value="\n".join([f"{k}: {stats.get(k, 0)}" for k in STAT_KEYS]),
        inline=False
    )

    # ✅ 효과 상세 계산
    effect_key = b.get("effect")
    if effect_key:
        current_val = get_effective_building_value(data["building_id"], level)
        next_val = get_effective_building_value(data["building_id"], min(level+1, b["max_level"]))
        effect_name = {
            "alba_bonus": "알바 수익 증가율",
            "jackpot_chance": "잭팟 확률 증가",
            "bank_bonus": "은행 이자 증가율",
            "exp_boost": "경험치 획득량 증가",
            "real_estate_shield": "부동산 손실 감소율"
        }.get(effect_key, effect_key)

        # % 변환 여부 결정
        if BUILDING_EFFECTS.get(effect_key, {}).get("type") in ["multiplier", "chance", "loss_reduction"]:
            current_val *= 100
            next_val *= 100
            unit = "%"
        else:
            unit = ""

        embed.add_field(
            name="📊 효과 증가",
            value=f"{effect_name}: **{current_val:.2f}{unit} → {next_val:.2f}{unit}** (다음 레벨)",
            inline=False
        )

    await interaction.response.send_message(embed=embed)


@tree.command(name="건물판매", description="보유 중인 건물을 판매하여 일부 금액을 환불받습니다.", guild=discord.Object(id=GUILD_ID))
async def 건물판매(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    building_data = get_user_building(user_id)

    if not building_data:
        return await interaction.response.send_message("🏚️ 보유 중인 건물이 없습니다.", ephemeral=True)

    building_id = building_data["building_id"]
    building_def = BUILDING_DEFS.get(building_id)

    if not building_def:
        return await interaction.response.send_message("❌ 건물 정보 오류가 발생했습니다.", ephemeral=True)

    refund_rate = 0.5  # 💸 환불 비율: 50%
    refund_amount = int(building_def["price"] * refund_rate)

    # 💥 건물 삭제 및 금액 환불
    clear_user_building(user_id)
    add_balance(user_id, refund_amount)

    # 💥 상태치 초기화
    reset_user_stats(user_id)

    await interaction.response.send_message(
        embed=discord.Embed(
            title="🏚️ 건물 판매 완료",
            description=(
                f"{building_def['name']} 건물을 판매하였습니다.\n"
                f"💰 환불 금액: **{refund_amount:,}원**\n"
                f"📉 누적 보상 및 상태치가 초기화되었으며, 건물 효과도 사라집니다."
            ),
            color=discord.Color.orange()
        )
    )


# ✅ 자동 보상 적립 루프
from discord.ext import tasks
from datetime import datetime, timedelta

@tasks.loop(minutes=30)
async def accumulate_building_rewards():
    buildings = get_all_buildings()
    now = datetime.now(KST)

    for user_id, info in buildings.items():
        building_def = BUILDING_DEFS.get(info["building_id"])
        if not building_def:
            continue

        # ⏱️ 마지막 보상 시각 확인
        last_updated_str = info.get("last_updated")
        last_updated = datetime.fromisoformat(last_updated_str) if last_updated_str else now - timedelta(minutes=31)

        # 30분 미만 경과 시 스킵
        if (now - last_updated).total_seconds() < 1800:
            continue

        # 🗓️ 하루 지나면 리셋
        if last_updated.date() != now.date():
            info["today_reward"] = 0

        # 💸 보상 계산
        base_reward = building_def["base_reward"]
        reward = get_building_reward(base_reward, info["level"])
        max_cap = building_def.get("daily_cap", 999_999)

        today_reward = info.get("today_reward", 0)
        remaining = max_cap - today_reward
        actual_reward = min(reward, remaining)

        if actual_reward > 0:
            add_balance(user_id, actual_reward)
            info["today_reward"] += actual_reward

        # 🧪 경험치 적립
        exp_gain = building_def["exp_gain"]
        effect = BUILDING_EFFECTS.get(building_def["effect"])
        if effect and effect["target"] == "exp":
            exp_gain = int(exp_gain * effect["value"])

        info["exp"] += exp_gain

        # ⏰ 타임스탬프 갱신
        info["last_updated"] = now.isoformat()

        # 🔄 업데이트 저장
        set_user_building(user_id, info)




import sqlite3

def get_db_connection():
    return sqlite3.connect("buildings.db")

def init_building_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # ✅ 건물 테이블 생성
    cur.execute("""
        CREATE TABLE IF NOT EXISTS buildings (
            user_id TEXT PRIMARY KEY,
            building_id TEXT,
            level INTEGER,
            exp INTEGER,
            today_reward INTEGER,
            last_updated TEXT
        )
    """)

    # ✅ 상태치 테이블 생성
    cur.execute("""
        CREATE TABLE IF NOT EXISTS building_stats (
            user_id TEXT PRIMARY KEY,
            stability INTEGER DEFAULT 0,
            risk INTEGER DEFAULT 0,
            labor INTEGER DEFAULT 0,
            tech INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# ── 추가 import (중복되면 생략) ─────────────────────────────
import os, re, math, asyncio

import aiosqlite
import wavelink

import logging

# ——— wavelink REST 디버그를 위해 로깅 레벨 설정 ———
logging.basicConfig(level=logging.INFO)
logging.getLogger("wavelink.rest").setLevel(logging.DEBUG)



# ── 음악 채널 (원하면 그대로 사용) ─────────────────────────
MUSIC_TEXT_CHANNEL_ID = 1400712729001721877
MUSIC_VOICE_CHANNEL_ID = 1400712268932583435

# ── Lavalink 연결 정보 (환경변수) ─────────────────────────
LAVALINK_HOST = os.getenv("LAVALINK_HOST", "127.0.0.1")
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", "2333"))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "yoursecret")

# ── SQLite 캐시 DB 파일 경로 ─────────────────────────────
MUSIC_CACHE_DB = os.path.join(os.path.dirname(__file__), "music_cache.db")

@tree.command(name="노드체크", description="Lavalink 노드 연결 상태 확인", guild=discord.Object(id=GUILD_ID))
async def 노드체크(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)

    node = next(iter(wavelink.Pool.nodes.values()), None)
    if node is None:
        return await interaction.followup.send("❌ 노드가 없습니다. (Pool.nodes 비어 있음)")

    # wavelink Node에 연결/가용성 체크
    if not getattr(node, "available", True):
        return await interaction.followup.send("❌ 노드가 연결되지 않았습니다.")

    stats = getattr(node, "stats", None)

    embed = discord.Embed(title="Lavalink 노드 상태", color=discord.Color.green())
    embed.add_field(name="URI", value=getattr(node, "uri", "N/A"), inline=False)

    if stats:
        # 속성 이름은 버전에 따라 다를 수 있어 getattr로 안전 접근
        uptime = getattr(stats, "uptime", None)
        players = getattr(stats, "players", None)
        playing = getattr(stats, "playing", None)
        cpu_cores = getattr(getattr(stats, "cpu", object()), "cores", None)
        mem_used = getattr(getattr(stats, "memory", object()), "used", None)
        mem_res = getattr(getattr(stats, "memory", object()), "reservable", None)

        embed.add_field(name="Players", value=str(players if players is not None else "N/A"))
        embed.add_field(name="Playing", value=str(playing if playing is not None else "N/A"))
        embed.add_field(name="Uptime(ms)", value=str(uptime if uptime is not None else "N/A"), inline=False)

        if cpu_cores is not None:
            embed.add_field(name="CPU Cores", value=str(cpu_cores))
        if mem_used is not None and mem_res is not None:
            embed.add_field(name="Memory", value=f"{mem_used} / {mem_res}")
    else:
        embed.description = "노드 연결됨 (통계 미수신)."

    await interaction.followup.send(embed=embed)

# ─────────────────────────────────────────────────────────
# 쿼리 정규화 (캐시 키)
# ─────────────────────────────────────────────────────────
def _norm_query(artist: str, title: str) -> str:
    base = f"{(artist or '').strip()} {(title or '').strip()}".lower()
    # 특수문자 제거 → 공백 정규화
    base = re.sub(r"[\[\]\(\)\|\-_/]+", " ", base)
    return re.sub(r"\s+", " ", base).strip()

# ─────────────────────────────────────────────────────────
# SQLite 캐시 DB 초기화 (인덱스/PRAGMA 보강)
# ─────────────────────────────────────────────────────────
async def init_music_cache_db():
    # DB 파일 위치 디렉터리 보장 (보통 __file__ 경로는 이미 존재하지만 안전차원)
    os.makedirs(os.path.dirname(MUSIC_CACHE_DB), exist_ok=True)
    async with aiosqlite.connect(MUSIC_CACHE_DB) as db:
        # I/O 성능 및 동시성 안정성 향상
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA synchronous=NORMAL;")

        await db.execute("""
        CREATE TABLE IF NOT EXISTS song_cache (
            query_norm   TEXT PRIMARY KEY,
            video_url    TEXT NOT NULL,
            title        TEXT,
            hit_count    INTEGER DEFAULT 0,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        # 조회/정렬에 필요한 보조 인덱스(선택)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_song_cache_hits ON song_cache(hit_count);")
        await db.commit()

async def cache_get_video_url(query_norm: str) -> str | None:
    async with aiosqlite.connect(MUSIC_CACHE_DB) as db:
        async with db.execute("SELECT video_url FROM song_cache WHERE query_norm = ?;", (query_norm,)) as cur:
            row = await cur.fetchone()
            if row and row[0]:
                # 히트 카운트 증가
                await db.execute("UPDATE song_cache SET hit_count = hit_count + 1 WHERE query_norm = ?;", (query_norm,))
                await db.commit()
                return row[0]
    return None

async def cache_set_video_url(query_norm: str, video_url: str, title: str | None = None):
    async with aiosqlite.connect(MUSIC_CACHE_DB) as db:
        await db.execute("""
        INSERT INTO song_cache (query_norm, video_url, title, hit_count)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(query_norm) DO UPDATE SET
            video_url=excluded.video_url,
            title=excluded.title,
            hit_count=song_cache.hit_count + 1
        ;""", (query_norm, video_url, title or None))
        await db.commit()


def _norm(s: str) -> str:
    return re.sub(r"[\s\-\_\|\[\]\(\)]+", " ", (s or "").lower()).strip()

_EXCLUDE_IF_NOT_REQUESTED = ["live", "cover", "instrumental", "remix", "sped up", "nightcore"]

def _score_track(track: wavelink.Playable, want_tokens: set[str], prefer_official=True) -> float:
    title = _norm(track.title)
    author = _norm(getattr(track, "author", "") or "")
    duration_ms = int(getattr(track, "length", 0) or 0)  # ms
    duration_sec = duration_ms // 1000

    t_tokens = set(title.split())
    overlap = len(want_tokens & t_tokens)

    len_penalty = 1.0
    if duration_sec == 0 or duration_sec > 15 * 60:
        len_penalty = 0.6

    excl_penalty = 1.0
    if any(kw in title for kw in _EXCLUDE_IF_NOT_REQUESTED):
        excl_penalty = 0.7

    ch_bonus = 1.0
    if prefer_official and any(k in author for k in ["official", "vevo", "topic"]):
        ch_bonus = 1.15

    score = (overlap * 2.0 + math.log1p(len(title))) * len_penalty * excl_penalty * ch_bonus
    return score

async def search_best_by_lavalink(query: str, limit: int = 10) -> wavelink.Playable | None:
    results = await wavelink.Playable.search(f"ytsearch:{query}")
    if not results:
        return None
    want_tokens = set(_norm(query).split())
    best, best_score = None, -1.0
    for t in results[:limit]:
        sc = _score_track(t, want_tokens)
        if sc > best_score:
            best_score, best = sc, t
    return best

async def get_or_connect_player(interaction: discord.Interaction) -> wavelink.Player:
    if not interaction.user.voice or not interaction.user.voice.channel:
        raise ValueError("먼저 음성 채널에 접속해주세요!")
    channel = interaction.user.voice.channel

    node = wavelink.Pool.get_node()
    if not node:
        raise RuntimeError("Lavalink 노드가 연결되지 않았습니다.")

    # node.connect로 플레이어 생성 혹은 채널 이동
    player = node.get_player(interaction.guild.id)
    if not player:
        player = await node.connect(
            guild_id=interaction.guild.id,
            channel_id=channel.id
        )
    elif player.channel.id != channel.id:
        await player.move_to(channel.id)  # v3 메서드: 이동

    return player


async def lavalink_search_http(query: str) -> dict | None:
    """
    Lavalink v4 REST API로 ytsearch:쿼리를 날려서
    첫 번째 트랙 정보를 dict 형태로 반환합니다.
    """
    url = f"http://{LAVALINK_HOST}:{LAVALINK_PORT}/v4/loadtracks"
    headers = {"Authorization": LAVALINK_PASSWORD}
    params = {"identifier": f"ytsearch:{query}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                print(f"[SongSearch]   ⚠️ HTTP REST 실패: 상태코드 {resp.status}")
                return None
            body = await resp.json()

    if body.get("loadType") != "search":
        print(f"[SongSearch]   ⚠️ REST loadType: {body.get('loadType')}")
        return None

    data = body.get("data", [])
    if not data:
        print("[SongSearch]   · HTTP REST 검색 결과 없음")
        return None

    # 첫 번째 아이템 리턴
    return data[0]





class SongSearchModal(discord.ui.Modal, title="노래 검색"):
    artist = discord.ui.TextInput(label="가수", placeholder="예: IU", max_length=80)
    title_ = discord.ui.TextInput(label="제목", placeholder="예: Love wins all", max_length=100)

    def __init__(self, parent_view: "MusicControlView"):
        super().__init__(timeout=180)
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        # 검색어 준비 & 로그
        artist = self.artist.value.strip()
        title  = self.title_.value.strip()
        query = f"{artist} {title}".strip()
        print(f"[SongSearch] ▶️ 검색 시작: {query}")

        await interaction.response.defer(thinking=True)

        # 플레이어 연결
        try:
            player = await get_or_connect_player(interaction)
        except Exception as e:
            return await interaction.followup.send(f"❌ 플레이어 연결 실패: {e}", ephemeral=True)

        track = None
        norm  = _norm_query(artist, title)

        # 캐시 조회
        print("[SongSearch]   · 캐시 조회")
        cached_url = await cache_get_video_url(norm)
        print(f"[SongSearch]   · 캐시 URL: {cached_url!r}")
        if cached_url:
            try:
                results = await wavelink.Playable.search(cached_url)
                if results:
                    track = results[0]
            except Exception as e:
                print(f"[SongSearch]   ⚠️ 캐시 재생 예외: {e}")

        # YouTubeTrack.search 폴백
        if not track:
            print("[SongSearch]   · YouTubeTrack.search 호출")
            try:
                yt = await wavelink.YouTubeTrack.search(query=query, limit=1)
                print(f"[SongSearch]   · YouTubeTrack.search 결과: {yt!r}")
                if yt:
                    track = yt[0]
            except Exception as e:
                print(f"[SongSearch]   ⚠️ YouTubeTrack.search 예외: {e}")

        # Playable.search 최종 폴백
        if not track:
            print("[SongSearch]   · Playable.search 호출")
            try:
                plays = await wavelink.Playable.search(f"ytsearch:{query}")
                print(f"[SongSearch]   · Playable.search 결과: {plays!r}")
                if plays:
                    track = plays[0]
            except Exception as e:
                print(f"[SongSearch]   ⚠️ Playable.search 예외: {e}")

        # HTTP REST 직접 검색 폴백
        if not track:
            print("[SongSearch]   · HTTP REST 직접 검색 폴백")
            rest_item = await lavalink_search_http(query)
            if rest_item:
                uri = rest_item["info"]["uri"]
                print(f"[SongSearch]   · REST 반환 URI: {uri}")
                try:
                    plays = await wavelink.Playable.search(uri)
                    print(f"[SongSearch]   · URI Playable.search 결과: {plays!r}")
                    if plays:
                        track = plays[0]
                except Exception as e:
                    print(f"[SongSearch]   ⚠️ URI Playable.search 예외: {e}")

        # 발견 여부 체크
        if not track:
            print("[SongSearch] ❌ 트랙 미발견")
            return await interaction.followup.send(
                "🔍 검색 결과를 찾지 못했어요. 키워드를 조금 바꿔볼까요?",
                ephemeral=True
            )
        print(f"[SongSearch] ✅ 트랙 발견: {track.title} ({track.uri})")

        # 캐시 저장
        try:
            await cache_set_video_url(norm, track.uri, track.title)
        except Exception as e:
            print(f"[SongSearch] ⚠️ 캐시 저장 실패: {e}")
 
        
        # 8) 재생 또는 대기열 추가 (player.playing 사용)
        if not player.playing:
            print(f"[SongSearch] ▶️ 재생 시도: {track.uri}")
            try:
                await player.play(track)
                print("[SongSearch] ▶️ play() 호출 완료")
            except Exception as e:
                print(f"[SongSearch]   ⚠️ player.play 예외: {e}")
                return await interaction.followup.send(f"❌ 재생 실패: {e}", ephemeral=True)

            msg = f"▶️ 재생 시작: **{track.title}**"
        else:
            print(f"[SongSearch] ➕ 이미 재생 중이어서 대기열 추가: {track.title}")
            player.queue.put(track)
            msg = f"➕ 대기열 추가: **{track.title}**"

        # 추가 디버그: 재생 상태와 채널 정보 확인
        print(f"[SongSearch]   · player.playing → {player.playing}")
        print(f"[SongSearch]   · player.channel → {getattr(player, 'channel', None)}")

        await interaction.followup.send(msg)







class MusicControlView(discord.ui.View):
    def __init__(self, *, timeout: float = 300):
        super().__init__(timeout=timeout)

    @discord.ui.button(label="노래 검색", style=discord.ButtonStyle.primary)
    async def search_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SongSearchModal(self))

    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.secondary)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        player = interaction.guild.voice_client
        if not player or not isinstance(player, wavelink.Player):
            return await interaction.followup.send("플레이어가 없습니다.", ephemeral=True)
        if player.paused:
            await player.resume()
            return await interaction.followup.send("▶️ 재개", ephemeral=True)
        else:
            await player.pause()
            return await interaction.followup.send("⏸️ 일시정지", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        player = interaction.guild.voice_client
        if not player or not isinstance(player, wavelink.Player):
            return await interaction.followup.send("플레이어가 없습니다.", ephemeral=True)
        if player.queue:
            await player.play(player.queue.get())
            return await interaction.followup.send("⏭️ 다음 곡", ephemeral=True)
        else:
            await player.stop()
            return await interaction.followup.send("⏹️ 대기열이 비어 종료", ephemeral=True)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary)
    async def loop_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        player = interaction.guild.voice_client
        if not player or not isinstance(player, wavelink.Player):
            return await interaction.followup.send("플레이어가 없습니다.", ephemeral=True)
        flag = getattr(player, "loop", False)
        player.loop = not flag
        await interaction.followup.send(f"🔁 반복: {'ON' if player.loop else 'OFF'}", ephemeral=True)

    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary)
    async def volume_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        player = interaction.guild.voice_client
        if not player or not isinstance(player, wavelink.Player):
            return await interaction.followup.send("플레이어가 없습니다.", ephemeral=True)
        vol = min((player.volume or 100) + 10, 150)
        await player.set_volume(vol)
        await interaction.followup.send(f"🔊 볼륨: {vol}%", ephemeral=True)

    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary)
    async def volume_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        player = interaction.guild.voice_client
        if not player or not isinstance(player, wavelink.Player):
            return await interaction.followup.send("플레이어가 없습니다.", ephemeral=True)
        vol = max((player.volume or 100) - 10, 10)
        await player.set_volume(vol)
        await interaction.followup.send(f"🔉 볼륨: {vol}%", ephemeral=True)

    @discord.ui.button(emoji="🧾", style=discord.ButtonStyle.secondary)
    async def show_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        player = interaction.guild.voice_client
        if not player or not isinstance(player, wavelink.Player):
            return await interaction.followup.send("플레이어가 없습니다.", ephemeral=True)
        if not player.queue:
            return await interaction.followup.send("대기열이 비었습니다.", ephemeral=True)
        lines = [f"{i}. {t.title}" for i, t in enumerate(list(player.queue)[:10], 1)]
        await interaction.followup.send("**대기열**\n" + "\n".join(lines), ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        player = interaction.guild.voice_client
        if not player or not isinstance(player, wavelink.Player):
            return await interaction.followup.send("플레이어가 없습니다.", ephemeral=True)
        await player.stop()
        player.queue.clear()
        await interaction.followup.send("⏹️ 정지 및 대기열 초기화", ephemeral=True)

@tree.command(name="오덕송", description="오덕봇 음악 컨트롤 패널을 엽니다.", guild=discord.Object(id=GUILD_ID))
async def 오덕송(interaction: discord.Interaction):
    await interaction.response.defer(thinking=False)

    embed = discord.Embed(
        title="🎵 오덕송 컨트롤",
        description="노래 검색 → 재생 / 일시정지 / 스킵 / 반복 / 볼륨 / 대기열 관리",
        color=discord.Color.blurple()
    )

    view = MusicControlView()
    if hasattr(view, "start"):
        await view.start()  # ❓ 비동기 초기화가 필요하다면 호출됨

    await interaction.followup.send(embed=embed, view=view)


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload):
    player: wavelink.Player = payload.player
    if getattr(player, "loop", False) and payload.track:
        player.queue.put(payload.track)
    if player.queue:
        await player.play(player.queue.get())



async def init_song_cache_table():
    """
    music_cache.db 에 song_cache 테이블이 없으면 생성합니다.
    """
    async with aiosqlite.connect(MUSIC_CACHE_DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS song_cache (
                query_norm TEXT    PRIMARY KEY,
                video_url  TEXT    NOT NULL,
                title      TEXT,
                hit_count  INTEGER DEFAULT 0
            );
        """)
        await db.commit()




# main.py 상단에, 이미 import 되어 있겠지만 혹시 누락됐다면 추가:
import os
import discord
from discord import app_commands

# (bot, tree, GUILD_ID 등 기존 설정 부분)

@tree.command(
    name="삑",
    description="짧은 테스트 삑 소리를 재생합니다.",
    guild=discord.Object(id=GUILD_ID)
)
async def beep(interaction: discord.Interaction):
    # 1) defer
    await interaction.response.defer(thinking=True)
    print("[Beep] 커맨드 호출됨")

    # 2) 음성 채널 체크
    channel = interaction.user.voice.channel if interaction.user.voice else None
    print("[Beep] 유저 채널:", channel)
    if not channel:
        return await interaction.followup.send("❌ 먼저 음성 채널에 접속해주세요!", ephemeral=True)

    # 3) 파일 경로 및 존재 확인
    path = os.path.join(os.path.dirname(__file__), "test.wav")
    print("[Beep] 파일 경로:", path)
    print("[Beep] 파일 존재:", os.path.exists(path))
    if not os.path.exists(path):
        return await interaction.followup.send("❌ test.wav 파일을 찾을 수 없습니다.", ephemeral=True)

    # 4) VoiceClient 연결
    vc: discord.VoiceClient = interaction.guild.voice_client  # type: ignore
    if not vc:
        print("[Beep] 새로 연결 시도")
        vc = await channel.connect()
    print("[Beep] VoiceClient:", vc)

    # 5) FFmpegPCMAudio 생성
    try:
        source = discord.FFmpegPCMAudio(path)
        print("[Beep] FFmpegPCMAudio 생성 성공")
    except Exception as e:
        print("[Beep] FFmpegPCMAudio 생성 실패:", e)
        return await interaction.followup.send(f"❌ FFmpeg 로드 실패: {e}", ephemeral=True)

    # 6) 재생
    try:
        vc.play(source, after=lambda e: print("[Beep] 재생 완료, 오류:", e))
        print("[Beep] play() 호출됨")
    except Exception as e:
        print("[Beep] play() 예외:", e)
        return await interaction.followup.send(f"❌ 재생 실패: {e}", ephemeral=True)

    # 7) 사용자 피드백
    await interaction.followup.send("🔊 Beep 테스트 재생중...", ephemeral=True)

@tree.command(
    name="테스트재생",
    description="node → channel.connect(cls=wavelink.Player, node=...) 테스트",
    guild=discord.Object(id=GUILD_ID)
)
async def playtest(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    # 1) 음성 채널 체크
    channel = interaction.user.voice.channel if interaction.user.voice else None
    if not channel:
        return await interaction.followup.send("❌ 먼저 음성 채널에 접속해주세요!", ephemeral=True)

    # 2) Lavalink 노드가 연결되어 있는지 확인
    node = wavelink.Pool.get_node()
    if not node:
        return await interaction.followup.send("❌ Lavalink 노드가 연결되지 않았습니다.", ephemeral=True)
    print("[PlayTest] 사용할 노드:", node)

    # 3) channel.connect 로 플레이어 생성 (node 파라미터 추가)
    try:
        player: wavelink.Player = interaction.guild.voice_client or await channel.connect(
            cls=wavelink.Player,
            node=node
        )
        print("[PlayTest] channel.connect() 플레이어 생성 완료")
    except Exception as e:
        print("[PlayTest] channel.connect 예외:", e)
        return await interaction.followup.send(f"❌ 플레이어 연결 실패: {e}", ephemeral=True)

    # 4) HTTP REST 검색 → Playable.search → 트랙 재생
    item = await lavalink_search_http("IU LILAC")
    if not item:
        return await interaction.followup.send("❌ 테스트 트랙을 찾을 수 없습니다.", ephemeral=True)

    uri = item["info"]["uri"]
    print("[PlayTest] URI 재검색:", uri)
    results = await wavelink.Playable.search(uri)
    if not results:
        return await interaction.followup.send("❌ URI 재검색 실패", ephemeral=True)
    track = results[0]

    try:
        await player.play(track)
        print("[PlayTest] play() 호출 완료")
    except Exception as e:
        print("[PlayTest] play() 예외:", e)
        return await interaction.followup.send(f"❌ 재생 실패: {e}", ephemeral=True)

    await interaction.followup.send(f"▶️ 테스트 재생 시작: **{track.title}**")









@bot.event
async def on_ready():
    global oduk_pool_cache, invites_cache

    # Opus 로드 여부 확인
    print("🔊 Opus loaded:", discord.opus.is_loaded())

    await process_overdue_loans_on_startup(bot)
    init_building_db()
    auto_repay_check.start()
    accumulate_building_rewards.start()
    await init_song_cache_table()
    print(f"🤖 봇 로그인됨: {bot.user}")

    # ✅ Lavalink 노드 연결 디버깅 시작
    nodes = wavelink.Pool.nodes
    print("🔌 Lavalink 노드 연결 시도 중...")
    print(f"🔌 현재 연결된 Lavalink 노드 수: {len(nodes)}")

    if not nodes:
        try:
            # ← 여기를 Pool.connect 대신 NodePool.create_node 로 변경
            await wavelink.NodePool.create_node(
                bot=bot,
                host=LAVALINK_HOST,
                port=LAVALINK_PORT,
                password=LAVALINK_PASSWORD,
                # region="asia"   # 필요 시 추가
            )
            print("🎧 Lavalink 노드 생성 성공 ✅")
        except Exception as e:
            print(f"❌ Lavalink 노드 생성 실패: {type(e).__name__}: {e}")

    print("🔌 Pool.nodes 상태:", wavelink.Pool.nodes)




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
