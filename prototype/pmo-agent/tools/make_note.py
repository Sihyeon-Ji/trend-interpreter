"""데모용 회의 메모 이미지 생성 — ingest.py 의 멀티모달 경로를 실제로 검증하기 위한 것.

진짜 손글씨는 아니다. 종이 질감·기울어짐·잉크 번짐·줄 간격 흔들림을 넣어
'폰으로 찍은 메모지'에 가깝게 만든 합성 이미지다.
실제 손글씨 판독력은 사람이 직접 쓴 사진으로 한 번 더 확인해야 한다 (README 한계 항목).

실행: python tools/make_note.py [출력경로]
"""

from __future__ import annotations

import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pmo_agent.env import samples_dir

OUT = str(samples_dir() / "meeting-note.png")
FONT = r"C:\Windows\Fonts\batang.ttc"  # 명조 계열 — 고딕보다 필기에 가깝다
PAPER = (250, 247, 238)
INK = (32, 38, 60)

# 시드 보드(data/seed.py)의 실제 태스크를 가리킨다 — 데모에서 메모와 보드가 어긋나지 않게.
# ECHO-27(단위 테스트 보강)은 재배치 제안이 '오태경 → 한서준'으로 집어내는 바로 그 태스크다.
LINES = [
    ("9/21 주간 회의", 0),
    ("", 0),
    ("- 인증 구현(ECHO-16) : 외부 IdP 결정 지연", 1),
    ("   → 마감 10/5로 미룸", 2),
    ("- ECHO-22 API 연동 오늘 끝남 (완료)", 1),
    ("- 오태경 부하 큼", 1),
    ("   단위테스트(ECHO-27) 한서준한테 넘기는거 검토", 2),
    ("- 정기회의 다음주 월요일 취소", 1),
    ("", 0),
    ("* 통합테스트(ECHO-28) 일정 다시 봐야 함", 0),
]


def render(path: str = OUT, seed: int = 7) -> str:
    rnd = random.Random(seed)
    W, H = 1000, 720
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # 종이 결: 옅은 얼룩과 가로 괘선
    for _ in range(1400):
        x, y = rnd.randrange(W), rnd.randrange(H)
        v = rnd.randint(-6, 6)
        d.point((x, y), fill=(PAPER[0] + v, PAPER[1] + v, PAPER[2] + v))
    for y in range(120, H - 40, 52):
        d.line([(60, y), (W - 60, y)], fill=(214, 220, 228), width=1)

    y = 70
    for text, indent in LINES:
        if not text:
            y += 26
            continue
        size = 40 if indent == 0 and text.startswith("9/") else 32
        font = ImageFont.truetype(FONT, size)
        x = 70 + indent * 34 + rnd.randint(-3, 3)  # 줄마다 살짝 흔들리게
        # 글자마다 미세하게 위아래로 흔들어 필기감을 낸다
        for ch in text:
            dy = rnd.randint(-2, 2)
            d.text(
                (x, y + dy),
                ch,
                font=font,
                fill=(
                    INK[0] + rnd.randint(-12, 12),
                    INK[1] + rnd.randint(-12, 12),
                    INK[2] + rnd.randint(-12, 12),
                ),
            )
            x += d.textlength(ch, font=font) + rnd.uniform(-0.6, 1.2)
        y += size + 22

    img = img.rotate(rnd.uniform(-1.6, 1.6), resample=Image.BICUBIC, fillcolor=PAPER)
    img = img.filter(ImageFilter.GaussianBlur(0.6))  # 촬영 초점 흐림
    # 조명 기울기 (한쪽이 어둡게)
    grad = Image.linear_gradient("L").resize((W, H)).rotate(70, fillcolor=128)
    img = Image.composite(
        img, Image.blend(img, Image.new("RGB", (W, H), (200, 197, 190)), 0.35), grad
    )

    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, quality=88)
    return path


if __name__ == "__main__":
    p = render(sys.argv[1] if len(sys.argv) > 1 else OUT)
    print("생성:", p, os.path.getsize(p), "bytes")
