from PIL import Image, ImageDraw, ImageFont
import os

def generate_pubg_card(nickname: str, metrics: dict, mode: str, tier: str, sub_tier: str, matches: list = []) -> str:
    # ✅ 모드 → 레이아웃 매핑
    layout_map = {
        "일반": "normal",
        "경쟁": "ranked",
        "히스토리": "matches"
    }

    layout_key = layout_map.get(mode, "normal")
    layout_path = f"assets/layout/{layout_key}_layout.png"
    output_path = f"temp_card_{nickname}_{layout_key}.png"

    font_path = "assets/layout/NotoSansKR-Bold.ttf"

    # ✅ 레이아웃 로딩
    base = Image.open(layout_path).convert("RGBA")
    draw = ImageDraw.Draw(base)
    font_large = ImageFont.truetype(font_path, 48)
    font_small = ImageFont.truetype(font_path, 28)

    # ✅ 닉네임 출력
    draw.text((180, 60), nickname, font=font_large, fill="white")

    # ✅ 일반 카드
    if mode == "일반":
        centers = {
            "솔로": 128,
            "듀오": 384,
            "스쿼드": 640
        }
        y_start = 160
        spacing = 40
        for key in ["솔로", "듀오", "스쿼드"]:
            x = centers[key]
            draw.text((x - 60, y_start), f"K/D: {metrics.get(key, {}).get('kd', 0):.2f}", font=font_small, fill="white")
            draw.text((x - 60, y_start + spacing), f"평균 데미지: {metrics.get(key, {}).get('avg_damage', 0):.1f}", font=font_small, fill="white")
            draw.text((x - 60, y_start + spacing * 2), f"승률: {metrics.get(key, {}).get('win_rate', 0):.1f}%", font=font_small, fill="white")

    # ✅ 경쟁 카드
    elif mode == "경쟁":
        # 티어 배지 삽입 (우측 상단 영역 크게)
        tier_image = f"{tier}-{sub_tier}".replace(" ", "").replace("/", "").replace("_", "")
        insignia_path = f"assets/insignias/{tier_image}.png"
        if os.path.exists(insignia_path):
            insignia = Image.open(insignia_path).convert("RGBA").resize((180, 180))
            base.paste(insignia, (520, 140), insignia)

        # 경쟁 스탯 (좌측 영역)
        x_start = 60
        y_start = 150
        spacing = 45
        draw.text((x_start, y_start), f"K/D: {metrics.get('kd', 0):.2f}", font=font_small, fill="white")
        draw.text((x_start, y_start + spacing), f"평균 데미지: {metrics.get('avg_damage', 0):.1f}", font=font_small, fill="white")
        draw.text((x_start, y_start + spacing * 2), f"승률: {metrics.get('win_rate', 0):.1f}%", font=font_small, fill="white")

        tier_text = f"{tier} {sub_tier}" if sub_tier else tier
        draw.text((x_start, y_start + spacing * 3 + 10), f"티어: {tier_text}", font=font_small, fill="white")

    # ✅ 히스토리 카드
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

        y_start = 160
        spacing = 55
        for i, match in enumerate(matches[:3]):
            y = y_start + i * spacing
            draw.text((50, y), f"{match['map']} / {match['mode']}", font=font_small, fill="white")

            if "kill" in icons:
                base.paste(icons["kill"], (280, y), icons["kill"])
                draw.text((320, y), f"{match['kills']}", font=font_small, fill="white")

            if "death" in icons:
                base.paste(icons["death"], (380, y), icons["death"])
                draw.text((420, y), f"{match['deaths']}", font=font_small, fill="white")

            if "revive" in icons:
                base.paste(icons["revive"], (480, y), icons["revive"])
                draw.text((520, y), f"{match['revives']}", font=font_small, fill="white")

            draw.text((620, y), f"딜: {match['damage']} / 순위: {match['rank']}위", font=font_small, fill="white")

    base.save(output_path)
    return output_path
