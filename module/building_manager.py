# building_manager.py
import json, os, random
from datetime import datetime
from discord import Interaction, Embed, app_commands

# ✅ 건물 정의
BUILDING_DEFS = {
    "편의점": {
        "price": 100_000,
        "manage_cost": [5000 + i * 300 for i in range(20)],
        "rewards_by_level": [(2000 + i * 100, 3000 + i * 200) for i in range(1, 21)],
        "growth": {"cleanliness": 60, "popularity": 50},
        "desc": "소소한 수익, 안정적인 운영이 가능한 건물입니다. 레벨업도 쉬운 편입니다.",
        "risk": 0.0,
        "bonus": None,
    },
    "카페": {
        "price": 250_000,
        "manage_cost": [8000 + i * 500 for i in range(20)],
        "rewards_by_level": [(1000 + i * 200, 5000 + i * 250) for i in range(1, 21)],
        "growth": {"popularity": 80},
        "desc": "SNS 인기 덕분에 운빨로 대박이 가능해요! 단, 가끔 손님이 없을 수도 있어요.",
        "risk": 0.1,
        "bonus": None,
    },
    "알바센터": {
        "price": 200_000,
        "manage_cost": [6000 + i * 300 for i in range(20)],
        "rewards_by_level": [(3000 + i * 150, 6000 + i * 150) for i in range(1, 21)],
        "growth": {"satisfaction": 70},
        "desc": "알바를 잘 돌리면 레벨업이 빠릅니다. 관리 시 경험치 보너스가 있어요.",
        "risk": 0.0,
        "bonus": "exp_boost",
    },
    "오락실": {
        "price": 300_000,
        "manage_cost": [10000 + i * 700 for i in range(20)],
        "rewards_by_level": [(0 + i * 500, 7000 + i * 400) for i in range(1, 21)],
        "growth": {"popularity": 100},
        "desc": "하이리스크 하이리턴! 15% 확률로 수익이 0원일 수 있어요.",
        "risk": 0.15,
        "bonus": None,
    },
    "독서실": {
        "price": 150_000,
        "manage_cost": [4000 + i * 200 for i in range(20)],
        "rewards_by_level": [(1500 + i * 80, 2500 + i * 100) for i in range(1, 21)],
        "growth": {"cleanliness": 90},
        "desc": "조용히, 꾸준히. 느리지만 안정적인 수익. 관리 실패 없음.",
        "risk": 0.0,
        "bonus": None,
    },
    "PC방": {
        "price": 180_000,
        "manage_cost": [6000 + i * 400 for i in range(20)],
        "rewards_by_level": [(2500 + i * 150, 4000 + i * 200) for i in range(1, 21)],
        "growth": {"satisfaction": 60, "popularity": 40},
        "desc": "청소년들의 아지트! 알바 성공 시 추가 수익이 발생합니다.",
        "risk": 0.0,
        "bonus": "alba_bonus",
    }
}

BUILDING_FILE = "data/buildings.json"

from main import get_balance, add_balance, add_oduk_pool

# ---------------- 기본 입출력 ----------------
def load_building_data():
    if not os.path.exists(BUILDING_FILE):
        return {}
    with open(BUILDING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_building_data(data):
    with open(BUILDING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_user_building(user_id):
    return load_building_data().get(str(user_id))

def set_user_building(user_id, building_info):
    data = load_building_data()
    data[str(user_id)] = building_info
    save_building_data(data)

def load_building_defs():
    return BUILDING_DEFS

# ---------------- 상태치 회복 제한 ----------------
def can_use_stat_action(building: dict, key: str) -> bool:
    today = datetime.utcnow().date().isoformat()
    count_key = f"{key}_used"
    used_info = building.setdefault("stat_used", {})
    if used_info.get("date") != today:
        used_info.clear()
        used_info["date"] = today
        used_info[count_key] = 0
    return used_info.get(count_key, 0) < 2

def record_stat_action(building: dict, key: str):
    today = datetime.utcnow().date().isoformat()
    count_key = f"{key}_used"
    used_info = building.setdefault("stat_used", {})
    used_info.setdefault("date", today)
    used_info[count_key] = used_info.get(count_key, 0) + 1

# ---------------- 레벨업 조건 ----------------
def can_level_up(building: dict, defs: dict) -> bool:
    level = building.get("level", 1)
    exp = building.get("exp", 0)
    if level >= 20 or exp < level * 3:
        return False
    required = defs[building["building_type"]].get("growth", {})
    for stat, threshold in required.items():
        if building["stats"].get(stat, 0) < threshold:
            return False
    return True

def try_level_up(building: dict, defs: dict):
    if can_level_up(building, defs):
        building["level"] += 1
        building["exp"] = 0
        return True
    return False

def check_post_stat_level_up(user_id: str):
    building = get_user_building(user_id)
    defs = load_building_defs()
    if try_level_up(building, defs):
        set_user_building(user_id, building)
        return building["level"]
    return None

# ---------------- 명령어 함수 ----------------
async def clean_building(interaction: Interaction):
    user_id = str(interaction.user.id)
    building = get_user_building(user_id)
    if not building: return await interaction.response.send_message("🏚️ 건물이 없습니다.", ephemeral=True)
    if not can_use_stat_action(building, "cleanliness"):
        return await interaction.response.send_message("❌ 청소는 하루 2회만 가능합니다.", ephemeral=True)
    building["stats"]["cleanliness"] = min(100, building["stats"].get("cleanliness", 0) + 10)
    record_stat_action(building, "cleanliness")
    set_user_building(user_id, building)
    check_post_stat_level_up(user_id)
    await interaction.response.send_message("🧼 청결도를 10 회복했습니다!", ephemeral=True)

async def advertise_building(interaction: Interaction):
    user_id = str(interaction.user.id)
    building = get_user_building(user_id)
    if not building: return await interaction.response.send_message("🏚️ 건물이 없습니다.", ephemeral=True)
    if not can_use_stat_action(building, "popularity"):
        return await interaction.response.send_message("❌ 광고는 하루 2회만 가능합니다.", ephemeral=True)
    building["stats"]["popularity"] = min(100, building["stats"].get("popularity", 0) + 10)
    record_stat_action(building, "popularity")
    set_user_building(user_id, building)
    check_post_stat_level_up(user_id)
    await interaction.response.send_message("📢 인기도를 10 회복했습니다!", ephemeral=True)

async def boost_satisfaction(interaction: Interaction):
    user_id = str(interaction.user.id)
    building = get_user_building(user_id)
    if not building: return await interaction.response.send_message("🏚️ 건물이 없습니다.", ephemeral=True)
    if not can_use_stat_action(building, "satisfaction"):
        return await interaction.response.send_message("❌ 만족도 회복은 하루 2회만 가능합니다.", ephemeral=True)
    building["stats"]["satisfaction"] = min(100, building["stats"].get("satisfaction", 0) + 10)
    record_stat_action(building, "satisfaction")
    set_user_building(user_id, building)
    check_post_stat_level_up(user_id)
    await interaction.response.send_message("😌 만족도를 10 회복했습니다!", ephemeral=True)

async def buy_building_selected(interaction: Interaction, name: str):
    user_id = str(interaction.user.id)
    if get_user_building(user_id):
        return await interaction.response.send_message("❌ 이미 건물을 보유하고 있습니다.", ephemeral=True)
    defs = load_building_defs()
    if name not in defs:
        return await interaction.response.send_message("❌ 존재하지 않는 건물입니다.", ephemeral=True)
    price = defs[name]["price"]
    if get_balance(user_id) < price:
        return await interaction.response.send_message("❌ 잔액 부족으로 구매할 수 없습니다.", ephemeral=True)

    add_balance(user_id, -price)
    set_user_building(user_id, {
        "building_type": name,
        "level": 1,
        "exp": 0,
        "last_manage_date": "",
        "stats": {"cleanliness": 100, "popularity": 100, "satisfaction": 100},
    })
    await interaction.response.send_message(f"✅ **{name}** 건물을 구입했습니다!", ephemeral=True)

async def manage_building(interaction: Interaction):
    user_id = str(interaction.user.id)
    building = get_user_building(user_id)
    if not building:
        return await interaction.response.send_message("🏚️ 건물이 없습니다.", ephemeral=True)

    today = datetime.utcnow().date().isoformat()
    if building.get("last_manage_date") == today:
        return await interaction.response.send_message("🕐 오늘은 이미 관리했습니다.", ephemeral=True)

    defs = load_building_defs()
    b_type = building["building_type"]
    level = min(building.get("level", 1), 20)
    exp = building.get("exp", 0)
    cost = defs[b_type]["manage_cost"][level - 1]
    if get_balance(user_id) < cost:
        return await interaction.response.send_message(f"💸 관리비 {cost:,}원이 부족합니다.", ephemeral=True)
    add_balance(user_id, -cost)

    # 상태치 감소
    for stat in ["cleanliness", "popularity", "satisfaction"]:
        if stat in building["stats"]:
            building["stats"][stat] = max(0, building["stats"][stat] - random.randint(3, 10))

    # 수익
    risk = defs[b_type].get("risk", 0)
    if random.random() < risk:
        reward = 0
    else:
        r_min, r_max = defs[b_type]["rewards_by_level"][level - 1]
        reward = random.randint(r_min, r_max)
    tax = int(reward * 0.1)
    net = reward - tax
    add_balance(user_id, net)
    add_oduk_pool(tax)

    # 경험치 증가
    exp += 1
    if defs[b_type].get("bonus") == "exp_boost":
        exp += 1
    building["exp"] = exp
    building["last_manage_date"] = today
    level_up_text = ""
    if try_level_up(building, defs):
        level_up_text = f"\n✨ 건물 레벨업! LV.{building['level']}"

    set_user_building(user_id, building)
    await interaction.response.send_message(
        f"🛠️ 건물 관리 완료!\n💰 수익: {reward:,}원 (세금 {tax:,}원)\n📉 상태치 일부 감소\n{level_up_text}",
        ephemeral=True)

# ✅ 건물 판매
def sell_user_building(user_id: str) -> int:
    path = f"data/buildings/{user_id}.json"
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        building = json.load(f)
    b_type = building.get("building_type")
    level = building.get("level", 1)
    base = BUILDING_DEFS.get(b_type, {}).get("price", 0)
    price = int(base * (1 + (level - 1) * 0.05))
    tax = int(price * 0.2)
    add_oduk_pool(tax)
    os.remove(path)
    return price - tax
