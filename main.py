from keep_alive import keep_alive  # ✅ Koyeb 헬스체크용 Flask 서버 실행

import discord
from discord.ext import commands
from discord import app_commands
import re
import os
import random
import asyncio
import aiohttp  # ✅ PUBG API 요청용

# 디스코드 서버 ID
GUILD_ID = 1309433603331198977

# 봇 설정
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True  # 음성 상태 이벤트 수신

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

nickname_pattern = re.compile(r"^[가-힣a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+/\d{2}$")

# 자동 퇴장 태스크 관리
auto_disconnect_tasks = {}

# 자동 퇴장 타이머 함수 (로그 추가)
async def auto_disconnect_after_timeout(user: discord.Member, channel: discord.VoiceChannel, timeout=1200):
    print(f"[자동퇴장 타이머 시작] {user}님, {timeout}초 후 자동퇴장 대기중...")
    await asyncio.sleep(timeout)
    print(f"[자동퇴장 타이머 종료] {user}님 퇴장 시도")
    if user.voice and user.voice.channel == channel:
        try:
            await user.move_to(None)
            print(f"{user} 님이 {channel.name}에서 자동 퇴장 처리됨")

            # 자유채팅방에 메시지 보내기
            guild = user.guild
            text_channel = discord.utils.get(guild.text_channels, name="자유채팅방")
            if text_channel:
                await text_channel.send(f"{user.mention} 님, 결국 20분 동안 밥을 먹지 못해 강제 퇴장 당했습니다. 😢")

        except Exception as e:
            print(f"강제 퇴장 실패: {e}")
        finally:
            auto_disconnect_tasks.pop(user.id, None)
    else:
        print(f"{user} 님이 이미 채널을 떠났거나 다른 채널에 있습니다.")
        auto_disconnect_tasks.pop(user.id, None)

# ✅ 음성 상태 변화 감지 (자동퇴장 취소 + 대기방 메시지 전송 통합)
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    # 자동퇴장 타이머 취소
    if member.id in auto_disconnect_tasks:
        task = auto_disconnect_tasks.pop(member.id)
        task.cancel()
        print(f"{member.name}님의 자동퇴장 타이머가 취소되었습니다.")

    # 대기방 진입 감지
    if after.channel and after.channel.name == "대기방":
        if not before.channel or before.channel != after.channel:
            guild = member.guild
            text_channel = discord.utils.get(guild.text_channels, name="자유채팅방")
            if text_channel:
                await text_channel.send(
                    f"{member.mention} 나도 게임을 하고싶어! "
                    f"나를 끼워주지 않으면 토끼록끼가 모든 음성채널을 폭파합니다. 💥🐰"
                )

# ⏱ 봇 준비 시
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await tree.sync(guild=guild)
    print(f"✅ 봇 로그인 완료: {bot.user} | 슬래시 명령어 동기화 완료")

# 🧪 닉네임 검사 명령어 (변경 없음)
@tree.command(name="검사", description="서버 전체 닉네임을 검사합니다.", guild=discord.Object(id=GUILD_ID))
async def 검사(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ 서버에서만 사용 가능합니다.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    count = 0
    for member in guild.members:
        if member.bot:
            continue
        raw_nickname = member.nick or member.name
        parts = raw_nickname.split("/")
        if len(parts) != 3:
            valid = False
        else:
            clean_parts = [p.strip().replace(" ", "") for p in parts]
            cleaned_nickname = "/".join(clean_parts)
            valid = bool(nickname_pattern.fullmatch(cleaned_nickname))

        if not valid:
            try:
                await interaction.channel.send(
                    f"{member.mention} 님, 별명 형식이 올바르지 않습니다.\n이름 / 아이디 / 년생 형식으로 변경해주세요."
                )
            except:
                pass
            count += 1

    await interaction.followup.send(f"🔍 닉네임 검사 완료: {count}명 오류", ephemeral=True)

# 📣 소환 명령어 (변경 없음)
@tree.command(name="소환", description="모든 유저를 현재 음성 채널로 소환합니다.", guild=discord.Object(id=GUILD_ID))
async def 소환(interaction: discord.Interaction):
    user_channel = interaction.user.voice.channel if interaction.user.voice else None
    if not user_channel:
        await interaction.response.send_message("❌ 음성 채널에 먼저 들어가 주세요!", ephemeral=True)
        return

    guild = interaction.guild
    moved = 0
    for vc in guild.voice_channels:
        if vc == user_channel or vc.name == "밥좀묵겠습니다":
            continue
        for member in vc.members:
            if not member.bot:
                try:
                    await member.move_to(user_channel)
                    moved += 1
                except:
                    pass

    await interaction.response.send_message(f"📢 총 {moved}명을 소환했습니다!")

# 🆕 PUBG 전적 조회 명령어
@tree.command(name="전적", description="카카오 배틀그라운드 전적을 조회합니다.", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(nickname="닉네임을 입력하세요.")
async def 전적(interaction: discord.Interaction, nickname: str):
    await interaction.response.defer(ephemeral=True)

    api_key = os.getenv("PUBG_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/vnd.api+json"
    }
    platform = "kakao"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.pubg.com/shards/{platform}/players?filter[playerNames]={nickname}", headers=headers) as res:
                data = await res.json()
                if res.status != 200 or not data.get("data"):
                    await interaction.followup.send("❌ 유저를 찾을 수 없습니다.", ephemeral=True)
                    return
                player_id = data["data"][0]["id"]

            async with session.get(f"https://api.pubg.com/shards/{platform}/players/{player_id}/matches", headers=headers) as res:
                match_data = await res.json()
                match_ids = match_data.get("data", [])
                if not match_ids:
                    await interaction.followup.send("⚠️ 최근 매치가 없습니다.", ephemeral=True)
                    return
                latest_match_id = match_ids[0]["id"]

            async with session.get(f"https://api.pubg.com/shards/{platform}/matches/{latest_match_id}", headers=headers) as res:
                match_detail = await res.json()

            for participant in match_detail["included"]:
                if participant["type"] == "participant" and participant["attributes"]["stats"]["name"] == nickname:
                    stats = participant["attributes"]["stats"]
                    break
            else:
                await interaction.followup.send("⚠️ 플레이어 전적 정보를 찾을 수 없습니다.", ephemeral=True)
                return

            embed = discord.Embed(title=f"{nickname}님의 최근 전적", color=0x1F8B4C)
            embed.add_field(name="킬", value=str(stats["kills"]))
            embed.add_field(name="어시스트", value=str(stats["assists"]))
            embed.add_field(name="데미지", value=str(round(stats["damageDealt"], 1)))
            embed.add_field(name="생존 시간", value=f"{int(stats['timeSurvived'])}초")
            embed.add_field(name="KDA", value=f"{(stats['kills'] + stats['assists']) / (stats['DBNOs'] or 1):.2f}")
            embed.set_footer(text="Powered by PUBG API")

            await interaction.followup.send(embed=embed, ephemeral=True)

    except Exception as e:
        print("전적 명령어 오류:", e)
        await interaction.followup.send("⚠️ 전적 조회 중 오류가 발생했습니다.", ephemeral=True)

# /밥 명령어 부분 (변경 없음)
@tree.command(name="밥", description="밥좀묵겠습니다 채널로 이동합니다.", guild=discord.Object(id=GUILD_ID))
async def 밥(interaction: discord.Interaction):
    user = interaction.user
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ 서버에서만 사용할 수 있습니다.", ephemeral=True)
        return

    target_channel = discord.utils.get(guild.voice_channels, name="밥좀묵겠습니다")
    text_channel = discord.utils.get(guild.text_channels, name="자유채팅방")

    if not target_channel:
        await interaction.response.send_message("❌ '밥좀묵겠습니다' 음성채널을 찾을 수 없습니다.", ephemeral=True)
        return

    if not text_channel:
        await interaction.response.send_message("❌ '자유채팅방' 텍스트채널을 찾을 수 없습니다.", ephemeral=True)
        return

    try:
        await user.move_to(target_channel)
        await interaction.response.send_message(
            f"🍚 '{target_channel.name}' 채널로 이동했습니다! 20분 후 토끼록끼의 강력한 파워로 자동 퇴장된다!.",
            ephemeral=True
        )
        await text_channel.send(f"{user.mention}님, 20분 동안 밥을 먹지 못하면 토끼록끼의 강력한 염력으로 강제퇴장 당할 수 있습니다.")

        if user.id in auto_disconnect_tasks:
            auto_disconnect_tasks[user.id].cancel()
            print(f"[타이머 취소] 기존 {user}님의 자동퇴장 타이머가 취소되었습니다.")

        task = asyncio.create_task(auto_disconnect_after_timeout(user, target_channel, timeout=1200))
        auto_disconnect_tasks[user.id] = task
        print(f"[타이머 등록] {user}님 자동퇴장 타이머가 등록되었습니다.")

    except Exception as e:
        try:
            await interaction.response.send_message(f"❌ 채널 이동에 실패했습니다: {e}", ephemeral=True)
        except Exception as send_error:
            print(f"에러 발생, 응답 전송 실패: {send_error}")
        print(f"채널 이동 실패: {e}")

# ▶️ Koyeb 헬스 체크용 웹서버 실행
keep_alive()

# ▶️ 봇 실행
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ 환경변수 DISCORD_TOKEN이 없습니다.")
