
import discord
from datetime import timezone, timedelta

# 서버(길드) ID
GUILD_ID = 1309433603331198977

# 모니터링 음성 채널 이름 리스트
MONITORED_CHANNEL_NAMES = [f"일반{i}" for i in range(1, 17)] + ["큰맵1", "큰맵2"]

# Discord Intents 설정
INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.voice_states = True

# KST 타임존 (필요시 사용)
KST = timezone(timedelta(hours=9))
