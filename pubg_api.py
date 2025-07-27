import requests
import os
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

_cached_season_id = None
_cached_season_time = None


def can_make_request():
    now = datetime.now()
    global _last_requests
    _last_requests = [t for t in _last_requests if (now - t).total_seconds() < RATE_LIMIT_INTERVAL]
    return len(_last_requests) < RATE_LIMIT


def register_request():
    global _last_requests
    _last_requests.append(datetime.now())


def get_player_id(player_name: str) -> str:
    url = f"https://api.pubg.com/shards/{PLATFORM}/players?filter[playerNames]={player_name}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    return data["data"][0]["id"]


def get_season_id() -> str:
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
            _cached_season_id = season["id"]
            _cached_season_time = now
            return _cached_season_id

    raise ValueError("현재 시즌 ID를 찾을 수 없습니다.")


def get_player_stats(player_id: str, season_id: str) -> dict:
    url = f"https://api.pubg.com/shards/{PLATFORM}/players/{player_id}/seasons/{season_id}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
