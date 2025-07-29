# migrate_building_data.py

import json
import sqlite3
import os

# JSON 파일 경로
BUILDING_DATA_FILE = "building_data.json"
BUILDING_STATS_FILE = "building_stats.json"

# SQLite DB 경로
DB_PATH = "buildings.db"

# JSON 로딩
def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

building_data = load_json(BUILDING_DATA_FILE)
stats_data = load_json(BUILDING_STATS_FILE)

# SQLite 연결
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 테이블 생성
cur.execute("""
CREATE TABLE IF NOT EXISTS buildings (
    user_id TEXT PRIMARY KEY,
    building_id TEXT,
    level INTEGER,
    exp INTEGER,
    today_reward INTEGER,
    last_updated TEXT
)""")

cur.execute("""
CREATE TABLE IF NOT EXISTS building_stats (
    user_id TEXT PRIMARY KEY,
    stability INTEGER,
    risk INTEGER,
    labor INTEGER,
    tech INTEGER
)""")

# 데이터 마이그레이션
for user_id, d in building_data.items():
    cur.execute("""
        INSERT OR REPLACE INTO buildings
        (user_id, building_id, level, exp, today_reward, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        d.get("building_id"),
        d.get("level", 1),
        d.get("exp", 0),
        d.get("today_reward", 0),
        d.get("last_updated", None)
    ))

for user_id, stats in stats_data.items():
    cur.execute("""
        INSERT OR REPLACE INTO building_stats
        (user_id, stability, risk, labor, tech)
        VALUES (?, ?, ?, ?, ?)
    """, (
        user_id,
        stats.get("stability", 0),
        stats.get("risk", 0),
        stats.get("labor", 0),
        stats.get("tech", 0)
    ))

conn.commit()
conn.close()

print("✅ 데이터 이전 완료: buildings.db")
