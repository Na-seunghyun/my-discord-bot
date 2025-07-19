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
    data[str(user_id)] = {
        "amount": amount,
        "last_updated": datetime.utcnow().isoformat()
    }
    save_balances(data)

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

# 욕설 부분만 ***로 가리는 함수
def censor_badwords_regex(text, badword_patterns):
    censored_text = text
    for pattern in badword_patterns:
        censored_text = pattern.sub("***", censored_text)
    return censored_text



@bot.event
async def on_member_update(before, after):
    if before.nick != after.nick:
        print(f"🔄 닉네임 변경 감지: {before.display_name} → {after.display_name}")
        await update_valid_pubg_ids(after.guild)












@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if str(message.channel.name) != WELCOME_CHANNEL_NAME:
        return

    msg = message.content
    lowered_msg = msg.lower()

    if any(p.search(lowered_msg) for p in BADWORD_PATTERNS):
        censored = censor_badwords_regex(msg, BADWORD_PATTERNS)
        try:
            await message.delete()
        except Exception as e:
            print(f"메시지 삭제 실패: {e}")

        embed = discord.Embed(
            title="💬 욕설 필터링 안내",
            description=f"{message.author.mention} 님이 작성한 메시지에 욕설이 포함되어 필터링 되었습니다.\n\n"
                        f"**필터링된 메시지:**\n{censored}",
            color=0xFFD700  # 노란색
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
    else:
        invites_cache = {}

def save_invite_cache():
    with open(INVITE_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(invites_cache, f, ensure_ascii=False, indent=2)





@bot.event
async def on_member_join(member):
    guild = member.guild
    channel = discord.utils.get(guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if not channel:
        return

    # 최신 초대 링크 받아오기
    try:
        current_invites = await guild.invites()
    except Exception as e:
        print(f"❌ 현재 초대 링크 불러오기 실패: {e}")
        return

    # 기존 초대 캐시 불러오기 (메모리 또는 파일)
    global invites_cache
    old_invites = invites_cache.get(str(guild.id), {})

    # fallback: invites_cache.json에서 불러오기
    if not old_invites:
        try:
            with open("invites_cache.json", "r", encoding="utf-8") as f:
                file_cache = json.load(f)
                old_invites = file_cache.get(str(guild.id), {})
                print("📂 invites_cache.json에서 캐시 불러옴")
        except Exception as e:
            print(f"❌ invites_cache.json 로딩 실패: {e}")
            old_invites = {}

    # 누가 초대한 것인지 비교
    inviter = None
    for invite in current_invites:
        old = old_invites.get(invite.code)
        if old and invite.uses > old["uses"]:
            inviter_id = old.get("inviter_id")
            if inviter_id:
                inviter = guild.get_member(inviter_id)
            break

    # 입장 시간
    KST = timezone(timedelta(hours=9))
    joined_dt = datetime.now(tz=KST)
    timestamp = int(joined_dt.timestamp())
    formatted_time = joined_dt.strftime("%Y-%m-%d %H:%M:%S")
    relative_time = f"<t:{timestamp}:R>"  # 예: 1분 전

    # 임베드 작성
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

@tasks.loop(minutes=10)  # 주기적으로 초대 캐시 갱신
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

        moved_members = []

        for ch in target_channels:
            for member in ch.members:
                if member.bot:
                    continue
                if member.voice and member.voice.channel.id == vc.id:
                    continue  # 나와 같은 채널은 스킵
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

DAILY_REWARD = 50000
WEEKLY_REWARD = 500000


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
@app_commands.describe(베팅액="최소 500원부터 도박 가능")
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
    if 베팅액 < 500:
        return await interaction.response.send_message(
            embed=create_embed("❌ 베팅 실패", "최소 베팅 금액은 **500원**입니다.", discord.Color.red()), ephemeral=True)
    if balance < 베팅액:
        return await interaction.response.send_message(
            embed=create_embed("💸 잔액 부족", f"현재 잔액: **{balance:,}원**", discord.Color.red()), ephemeral=True)

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
    updated_balance = get_balance(user_id)

    # 성공
    if roll <= success_chance:
        add_balance(user_id, 베팅액 * 2)
        final_balance = get_balance(user_id)
        embed = create_embed("🎉 도박 성공!",
            f"(확률: {success_chance}%, 값: {roll})\n{bar}\n"
            f"+{베팅액:,}원 획득!\n💰 잔액: {final_balance:,}원",
            discord.Color.green(), user_id)

    # 실패
    else:
        add_oduk_pool(베팅액)
        pool_amt = get_oduk_pool_amount()
        embed = create_embed(
            "💀 도박 실패!",
            (
                f"(확률: {success_chance}%, 값: {roll})\n{bar}\n"
                f"-{베팅액:,}원 손실...\n"
                f"🍜 오덕 로또 상금: **{pool_amt:,}원** 적립됨!\n"
                f"🎟️ `/오덕로또참여`로 도전하세요!"
            ),
            discord.Color.red(),
            user_id
        )

    await interaction.response.send_message(embed=embed)







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
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ 본인만 참여할 수 있습니다.", ephemeral=True)
        if self.view.stopped:
            return await interaction.response.send_message("❌ 이미 복권이 종료되었습니다.", ephemeral=True)

        self.view.stop()

        try:
            if self.label == self.correct_slot:
                add_balance(self.user_id, self.베팅액 * 3)
                title = "🎉 당첨!"
                desc = f"축하합니다! **{self.베팅액 * 3:,}원**을 획득했습니다!"
                color = discord.Color.green()
            else:
                add_oduk_pool(self.베팅액)
                pool_amt = get_oduk_pool_amount()
                title = "💔 꽝!"
                desc = (
                    f"아쉽지만 탈락입니다.\n**{self.베팅액:,}원**을 잃었습니다.\n\n"
                    f"🍜 오덕 로또 상금: **{pool_amt:,}원** 적립됨!\n"
                    f"🎟️ `/오덕로또참여`로 참여하세요!"
                )
                color = discord.Color.red()

            await interaction.response.edit_message(
                embed=create_embed(title, desc, color, str(self.user_id)),
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
        add_balance(user_id, winnings)
        outcome = f"🎉 **5개 연속 일치! +{winnings:,}원 획득!**"
        color = discord.Color.green()
    elif max_streak >= 3:
        winnings = 베팅액 * 4
        add_balance(user_id, winnings)
        outcome = f"✨ **{max_streak}개 연속 일치! +{winnings:,}원 획득!**"
        color = discord.Color.green()
    else:
        add_oduk_pool(베팅액)
        pool_amt = get_oduk_pool_amount()

        outcome = (
            f"😢 **꽝! 다음 기회를 노려보세요.\n-{베팅액:,}원 손실**\n\n"
            f"🍜 오덕 로또 상금: **{pool_amt:,}원** 적립됨!\n"
            f"🎟️ `/오덕로또참여`로 참여하세요!"
        )
        color = discord.Color.red()


    await message.edit(
        content=f"🎰 **슬롯머신 결과**\n| {result_str} |\n\n{outcome}\n💵 현재 잔액: {get_balance(user_id):,}원"
    )


@tree.command(name="도박순위", description="도박 잔액 순위 TOP 10", guild=discord.Object(id=GUILD_ID))
async def 도박순위(interaction: discord.Interaction):
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
    # ✅ 허용된 채널: 오덕도박장, 오덕코인
    if interaction.channel.id not in [1394331814642057418, 1394519744463245543]:
        return await interaction.response.send_message(
            "❌ 이 명령어는 **#오덕도박장** 또는 **#오덕코인** 채널에서만 사용할 수 있습니다.",
            ephemeral=True
        )

    user_id = str(interaction.user.id)
    balance = get_balance(user_id)


    if 금액 < 1000:
        return await interaction.response.send_message(
            embed=create_embed("❌ 금액 오류", "최소 **1,000원** 이상만 가능합니다.", discord.Color.red()), ephemeral=True)

    if balance < 금액:
        return await interaction.response.send_message(
            embed=create_embed("💸 잔액 부족", f"현재 잔액: **{balance:,}원**", discord.Color.red()), ephemeral=True)

    stocks = load_stocks()
    종목_전체 = list(stocks.keys())
    random.shuffle(종목_전체)

    # ✅ 1~30개 랜덤 종목 선택
    선택종목수 = random.randint(1, min(30, len(종목_전체)))
    선택된종목 = 종목_전체[:선택종목수]

    # ✅ 랜덤 비율 생성 (전체 합 = 1.0)
    비율들 = [random.random() for _ in range(선택종목수)]
    총합 = sum(비율들)
    비율들 = [v / 총합 for v in 비율들]

    투자결과 = []
    investments = load_investments()
    수수료총합 = 0
    총사용액 = 0

    for 종목, 비율 in zip(선택된종목, 비율들):
        배정금액 = int(금액 * 비율)

        단가 = stocks[종목]["price"]
        실단가 = int(단가 * 1.01)
        수량 = 배정금액 // 실단가

        if 수량 < 1:
            continue

        총액 = 실단가 * 수량
        실제구매가 = 단가 * 수량
        수수료 = 총액 - 실제구매가

        add_balance(user_id, -총액)
        수수료총합 += 수수료
        총사용액 += 총액

        investments.append({
            "user_id": user_id,
            "stock": 종목,
            "shares": 수량,
            "price_per_share": 단가,
            "timestamp": datetime.now().isoformat()
        })

        투자결과.append(f"📈 **{종목}** {수량}주 (총 {총액:,}원)")

    save_investments(investments)
    add_oduk_pool(수수료총합)
    oduk_amount = get_oduk_pool_amount()

    if not 투자결과:
        return await interaction.response.send_message(
            embed=create_embed("🤷 자동투자 실패", "입력 금액으로는 매수 가능한 종목이 없습니다.", discord.Color.orange()), ephemeral=False)

    await interaction.response.send_message(
        embed=create_embed(
            "🎯 랜덤 자동투자 완료",
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

@tasks.loop(minutes=30)
async def process_investments():
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







@tree.command(name="잔액초기화", description="모든 유저의 잔액 및 기록을 초기화합니다 (채널관리자 전용)", guild=discord.Object(id=GUILD_ID))
async def 잔액초기화(interaction: discord.Interaction):
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
    save_investment_history([])  # 수익 히스토리 초기화
    save_last_chart_time(datetime.utcnow())  # 주가 갱신 기준 초기화

    await interaction.response.send_message(
        embed=create_embed(
            "✅ 초기화 완료",
            f"총 {len(balances)}명의 잔액과 오덕로또, 투자 보유/수익 기록이 초기화되었습니다.\n※ 투자 종목은 유지됩니다.",
            discord.Color.green()
        ),
        ephemeral=False
    )



ODUK_LOTTO_ENTRIES_FILE = "oduk_lotto_entries.json"

def load_oduk_lotto_entries():
    if not os.path.exists(ODUK_LOTTO_ENTRIES_FILE):
        with open(ODUK_LOTTO_ENTRIES_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    with open(ODUK_LOTTO_ENTRIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_oduk_lotto_entries(data):
    with open(ODUK_LOTTO_ENTRIES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)






# ✅ 자동 오덕로또 추첨 함수
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
        answer = sorted(random.sample(range(1, 46), 4))
        bonus = random.choice([n for n in range(1, 46) if n not in answer])
        tier1, tier2, tier3 = [], [], []

        for uid, combos in filtered_entries.items():
            for combo in combos:
                matched = set(combo) & set(answer)
                match = len(matched)
                has_bonus = bonus in combo

                if match == 4:
                    tier1.append(uid)
                elif match == 3 and has_bonus:
                    tier2.append(uid)
                elif match == 3 or (match == 2 and has_bonus):
                    tier3.append(uid)

        result_str = f"🎯 정답 번호: {', '.join(map(str, answer))} + 보너스({bonus})\n\n"

        amount = get_oduk_pool_amount()
        tier2_pool = int(amount * 0.2)
        tier1_pool = int(amount * 0.8)
        lines = []
        notified_users = set()
        leftover = 0

        guild = bot.guilds[0]

        def get_mention(uid):
            member = guild.get_member(int(uid))
            return member.mention if member else f"<@{uid}>"

        # ✅ 1등
        if tier1:
            share = tier1_pool // len(tier1)
            for uid in tier1:
                add_balance(uid, share)
                try:
                    user = await bot.fetch_user(int(uid))
                    await user.send(
                        f"🏆🎉 오덕로또 **1등** 당첨!\n"
                        f"정답 번호: {', '.join(map(str, answer))} + 보너스({bonus})\n"
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
                        f"🥈 오덕로또 2등 당첨!\n"
                        f"정답 번호: {', '.join(map(str, answer))} + 보너스({bonus})\n"
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

        # ✅ 3등 (공지 전용, 중복 표시)
        if tier3:
            from collections import Counter

            count_by_uid = Counter(tier3)
            for uid, count in count_by_uid.items():
                add_balance(uid, 5000 * count)

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
            except Exception as e:
                print(f"❌ 로또 결과 전송 실패: {e}")

    print(f"✅ 오덕로또 추첨 완료됨! 정답: {answer} + 보너스({bonus})")
    print(f"🥇 1등: {len(tier1)}명 | 🥈 2등: {len(tier2)}명 | 🥉 3등: {len(tier3)}명")
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
        f"🏆 1등 당첨 시 예상 상금: **{tier1_pool:,}원** (당첨자 1명 기준)\n"
        f"🥈 2등 당첨 시 예상 상금: **{tier2_pool:,}원** (당첨자 1명 기준)\n"
        f"⏰ 다음 추첨: <t:{int(draw_end.timestamp())}:F>\n"
        f"🕓 제한 초기화까지: <t:{int(draw_end.timestamp())}:R>\n"
        f"🎯 매일 오전 9시에 자동 추첨됩니다!\n"
        f"\n💰 현재 잔액: {get_balance(user_id):,}원"
    )

    await interaction.response.send_message(content=desc)






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

    answer = sorted(random.sample(range(1, 46), 4))
    bonus = random.choice([n for n in range(1, 46) if n not in answer])
    tier1, tier2, tier3 = [], [], []

    for uid, combos in filtered_entries.items():
        for combo in combos:
            matched = set(combo) & set(answer)
            match = len(matched)
            has_bonus = bonus in combo

            if match == 4:
                tier1.append(uid)
            elif match == 3 and has_bonus:
                tier2.append(uid)
            elif (match == 3) or (match == 2 and has_bonus):
                tier3.append(uid)

    result_str = f"🎯 정답 번호: {', '.join(map(str, answer))} + 보너스({bonus})\n\n"

    amount = get_oduk_pool_amount()
    tier2_pool = int(amount * 0.2)
    tier1_pool = int(amount * 0.8)
    lines = []
    notified_users = set()
    leftover = 0

    guild = interaction.guild  # 현재 명령어 실행한 서버 기준

    def get_mention(uid):
        member = guild.get_member(int(uid))
        return member.mention if member else f"<@{uid}>"

    # ✅ 1등
    if tier1:
        share = tier1_pool // len(tier1)
        for uid in tier1:
            add_balance(uid, share)
            try:
                user = await bot.fetch_user(int(uid))
                await user.send(
                    f"🏆🎉 [수동추첨] 오덕로또 **1등** 당첨!\n"
                    f"정답 번호: {', '.join(map(str, answer))} + 보너스({bonus})\n"
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
                    f"정답 번호: {', '.join(map(str, answer))} + 보너스({bonus})\n"
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
        for uid in tier3:
            add_balance(uid, 5000)

        from collections import Counter
        counts = Counter(tier3)
        formatted_mentions = []
        for uid, count in counts.items():
            mention = get_mention(uid)
            if count > 1:
                formatted_mentions.append(f"{mention} × {count}회")
            else:
                formatted_mentions.append(mention)

        mention_line = ", ".join(formatted_mentions)
        lines.append(f"🥉 3등 {len(tier3)}건 (3개 일치 또는 2개+보너스) → 1인당 5,000원\n  {mention_line}")
    else:
        lines.append("🥉 3등 당첨자 없음 → 상금 없음")


    result_str += "\n".join(lines)
    result_str += f"\n\n💰 이월된 상금: {leftover:,}원"

    # ✅ 캐시 저장, 날짜는 저장 안 함
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

    # 🕘 다음 추첨: 오늘 오전 9시 또는 내일 오전 9시
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

    embed = discord.Embed(
        title="🎯 오덕로또 추첨 상태 확인",
        description=(
            f"⏰ **다음 추첨 예정**: <t:{unix_ts}:F> | ⏳ <t:{unix_ts}:R>\n"
            f"{status}\n"
            f"👥 이번 회차 참여 인원 수: {count}명"
        ),
        color=discord.Color.orange()
    )

    await interaction.followup.send(embed=embed)




from discord.ext import tasks
from datetime import datetime

# 📡 핑 모니터링 경고 기준 (ms 단위)
PING_WARNING = 200
PING_CRITICAL = 400

# ⏱️ 각각의 알림 시간 (중복 방지용)
last_warning_alert_time = None
last_critical_alert_time = None

@tasks.loop(seconds=60)  # 매 1분마다 확인
async def monitor_discord_ping():
    global last_warning_alert_time, last_critical_alert_time

    ping_ms = round(bot.latency * 1000)
    now = datetime.utcnow()

    # 200ms 미만이면 정상 → 아무것도 안 함
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
            await interaction.response.send_message(chunk, ephemeral=True)
        else:
            await interaction.followup.send(chunk, ephemeral=True)














@bot.event
async def on_ready():
    print(f"🤖 봇 로그인됨: {bot.user}")
    monitor_discord_ping.start()  # ✅ 이 줄 추가
    await asyncio.sleep(2)  # 약간 대기

    for guild in bot.guilds:
        print(f"접속 서버: {guild.name} (ID: {guild.id})")

    try:
        synced = await tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"✅ 슬래시 명령어 {len(synced)}개 동기화됨")
    except Exception as e:
        print(f"❌ 슬래시 명령어 동기화 실패: {e}")

    # ⏲️ 자정 루프 시작
    if not reset_daily_claims.is_running():
        reset_daily_claims.start()

    # 초대 캐시 초기화 및 저장
    global invites_cache
    invites_cache = {}

    global oduk_pool_cache
    oduk_pool_cache = load_oduk_pool()

    if oduk_pool_cache is None:
        print("⚠️ 오덕 잔고 파일이 아직 없습니다. 처음 사용할 때 생성됩니다.")
        oduk_pool_cache = {}  # 또는 기본값 딕셔너리
    else:
        print(f"🔄 오덕 캐시 로딩됨: {oduk_pool_cache}")
   

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

    if not process_investments.is_running():
        process_investments.start()
        print("📈 투자 정산 루프 시작됨")






keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ 환경변수 DISCORD_TOKEN이 없습니다.")
