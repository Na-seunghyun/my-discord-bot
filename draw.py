from PIL import Image, ImageDraw, ImageFont
import os

def generate_pubg_card(nickname: str, metrics: dict, mode: str, tier: str, sub_tier: str, matches: list = []) -> str:
    # 기본 경로 설정
    layout_path = f"assets/layout/{mode.lower()}_layout.png"
    output_path = f"temp_card_{nickname}_{mode}.png"
    font_path = "assets/layout/NotoSansKR-Bold.ttf"

    # 레이아웃 이미지 불러오기
    base = Image.open(layout_path).convert("RGBA")
    draw = ImageDraw.Draw(base)
    font_large = ImageFont.truetype(font_path, 48)
    font_small = ImageFont.truetype(font_path, 28)

    # 티어 배지 삽입
    insignia_path = f"assets/insignias/{tier}-{sub_tier}.png"
    if os.path.exists(insignia_path):
        insignia = Image.open(insignia_path).convert("RGBA").resize((100, 100))
        base.paste(insignia, (50, 50), insignia)

    # 닉네임 텍스트
    draw.text((180, 60), nickname, font=font_large, fill="white")

    # 일반 / 경쟁 모드 카드 정보 표시
    if mode in ["일반", "경쟁"]:
        draw.text((180, 140), f"K/D: {metrics['kd']:.2f}", font=font_small, fill="white")
        draw.text((180, 190), f"평균 데미지: {metrics['avg_damage']:.1f}", font=font_small, fill="white")
        draw.text((180, 240), f"승률: {metrics['win_rate']:.1f}%", font=font_small, fill="white")

    # 매치 히스토리 카드 구성
    elif mode == "히스토리":
        icon_paths = {
            "kill": "assets/icons/kill.png",
            "death": "assets/icons/death.png",
            "revive": "assets/icons/revive.png",
            "care_package": "assets/icons/care_package.png",
        }
        icons = {
            name: Image.open(path).convert("RGBA").resize((32, 32))
            for name, path in icon_paths.items() if os.path.exists(path)
        }

        y_start = 150
        for i, match in enumerate(matches[:5]):
            y = y_start + i * 70
            draw.text((50, y), f"{match['map']} / {match['mode']}", font=font_small, fill="white")

            if "kill" in icons:
                base.paste(icons["kill"], (300, y), icons["kill"])
                draw.text((340, y), f"{match['kills']}", font=font_small, fill="white")

            if "death" in icons:
                base.paste(icons["death"], (400, y), icons["death"])
                draw.text((440, y), f"{match['deaths']}", font=font_small, fill="white")

            if "revive" in icons:
                base.paste(icons["revive"], (500, y), icons["revive"])
                draw.text((540, y), f"{match['revives']}", font=font_small, fill="white")

            draw.text((620, y), f"딜: {match['damage']} / 순위: {match['rank']}위", font=font_small, fill="white")

    # 최종 저장
    base.save(output_path)
    return output_path
