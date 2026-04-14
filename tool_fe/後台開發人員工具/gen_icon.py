#!/usr/bin/env python3
"""產生 splash 圖 + ICO — 台雞店風格"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os, math

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT     = 'C:/Windows/Fonts/msjhbd.ttc'   # 微軟正黑體 Bold

# ── 顏色 ─────────────────────────────────────────────────────────────────────
BG        = '#0f172a'   # 深藍背景
CARD      = '#1e293b'   # 卡片色
ORANGE    = '#f97316'   # 主橘
ORANGE_LT = '#fb923c'   # 淡橘
YELLOW    = '#fbbf24'   # 黃
RED_C     = '#ef4444'   # 雞冠紅
WHITE     = '#f8fafc'
MUTED     = '#94a3b8'


def font(size):
    try:    return ImageFont.truetype(FONT, size)
    except: return ImageFont.load_default()


def draw_chicken(d: ImageDraw.Draw, cx: int, cy: int, scale: float = 1.0):
    """以 (cx,cy) 為中心畫一隻簡約幾何雞，scale 控制大小"""
    s = scale

    def e(x1,y1,x2,y2, **kw):
        d.ellipse([cx+x1*s, cy+y1*s, cx+x2*s, cy+y2*s], **kw)
    def p(pts, **kw):
        d.polygon([(cx+x*s, cy+y*s) for x,y in pts], **kw)
    def ln(pts, **kw):
        d.line([(cx+x*s, cy+y*s) for x,y in pts], **kw)

    # 身體（大橢圓）
    e(-38, -10, 38, 48, fill=ORANGE, outline=ORANGE_LT, width=round(2*s))
    # 翅膀（左側陰影橢圓）
    e(-46, 4, 2, 44, fill='#ea580c', outline=ORANGE, width=round(1*s))
    # 頭
    e(14, -38, 52, -4, fill=ORANGE, outline=ORANGE_LT, width=round(2*s))
    # 雞冠（三個小圓）
    e(18, -52, 28, -40, fill=RED_C)
    e(27, -56, 37, -44, fill=RED_C)
    e(36, -52, 46, -40, fill=RED_C)
    # 眼睛
    e(30, -30, 40, -20, fill=WHITE)
    e(33, -28, 39, -22, fill='#1e293b')
    e(35, -27, 38, -24, fill=WHITE)   # 亮點
    # 嘴巴（三角）
    p([(50,-22),(62,-18),(50,-14)], fill=YELLOW)
    # 肉垂（下嘴巴紅肉）
    e(44,-18,54,-8, fill=RED_C)
    # 腳
    ln([(-8,48),(-14,66),(-20,72)], fill=YELLOW, width=round(3*s))
    ln([(-8,48),(-8,68),(-2,74)],  fill=YELLOW, width=round(3*s))
    ln([(10,48),(16,66),(22,72)],   fill=YELLOW, width=round(3*s))
    ln([(10,48),(10,68),(16,74)],   fill=YELLOW, width=round(3*s))


def make_splash(W=420, H=320) -> Image.Image:
    img = Image.new('RGBA', (W, H), BG)
    d   = ImageDraw.Draw(img)

    # ── 背景裝飾圓 ────────────────────────────────────────────────────────────
    d.ellipse([-60,-60,180,180],   fill='#1e293b')
    d.ellipse([260,-40,W+40,H//2], fill='#1e293b')

    # ── 中央卡片 ──────────────────────────────────────────────────────────────
    d.rounded_rectangle([W//2-130, 18, W//2+130, H-18],
                        radius=22, fill=CARD, outline='#334155', width=1)

    # ── 雞圖示 ────────────────────────────────────────────────────────────────
    draw_chicken(d, W//2, 120, scale=1.05)

    # ── 主標題 ────────────────────────────────────────────────────────────────
    d.text((W//2, 222), '後端開發人員工具',
           font=font(20), fill=WHITE, anchor='mm')

    # ── 橘色分隔線 ────────────────────────────────────────────────────────────
    d.rounded_rectangle([W//2-90, 238, W//2+90, 241],
                        radius=2, fill=ORANGE)

    # ── 副標語 ────────────────────────────────────────────────────────────────
    d.text((W//2, 260), '台雞店  關心您身心靈健康!~',
           font=font(14), fill=YELLOW, anchor='mm')

    # ── 版本小字 ──────────────────────────────────────────────────────────────
    d.text((W//2, H-14), 'Tiger Dev Tools  ·  Internal Use Only',
           font=font(10), fill=MUTED, anchor='mm')

    return img


def make_icon_sq(size=256) -> Image.Image:
    """正方形 icon（用於 .ico）"""
    img = Image.new('RGBA', (size, size), (0,0,0,0))
    d   = ImageDraw.Draw(img)
    R   = size // 2

    # 圓形背景
    d.ellipse([4, 4, size-4, size-4], fill=CARD, outline=ORANGE, width=4)

    # 雞
    draw_chicken(d, R, R-6, scale=size/280)

    return img


if __name__ == '__main__':
    # Splash PNG（供 splash screen 使用）
    splash = make_splash()
    splash_path = os.path.join(OUT_DIR, 'splash.png')
    splash.save(splash_path)
    print(f'Splash PNG → {splash_path}')

    # ICO（多尺寸）
    ico_src  = make_icon_sq(256)
    ico_path = os.path.join(OUT_DIR, '後端開發人員工具.ico')
    sizes    = [256, 128, 64, 48, 32, 16]
    frames   = [ico_src.resize((s,s), Image.LANCZOS) for s in sizes]
    frames[0].save(ico_path, format='ICO',
                   sizes=[(s,s) for s in sizes],
                   append_images=frames[1:])
    print(f'ICO        → {ico_path}')
    print('完成！')
