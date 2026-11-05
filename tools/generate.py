"""
JaKing Lunar Colony Collection — Roblox classic clothing generator.

Renders 10 original shirt templates + 2 matching pants templates in the
official Roblox classic clothing layout (585 x 559 px), plus front/back
avatar mockups and a collection contact sheet.

Everything is drawn procedurally at 4x and downsampled for clean edges.
Run:  python3 tools/generate.py
"""
import math
import os
import random
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_SHIRTS = os.path.join(ROOT, "shirts")
OUT_PANTS = os.path.join(ROOT, "pants")
OUT_PREV = os.path.join(ROOT, "previews")
for d in (OUT_SHIRTS, OUT_PANTS, OUT_PREV):
    os.makedirs(d, exist_ok=True)

S = 4                      # supersample factor
W, H = 585, 559            # Roblox classic clothing template size
FONT_BOLD = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
FONT_MED = "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

# ---------------------------------------------------------------- layout --
# (x, y, w, h) in final template pixels — official Roblox shirt/pants layout
FACES = {
    "torso": {"U": (231, 8, 128, 64), "R": (165, 74, 64, 128), "F": (231, 74, 128, 128),
              "L": (361, 74, 64, 128), "B": (427, 74, 128, 128), "D": (231, 204, 128, 64)},
    "rarm":  {"U": (217, 289, 64, 64), "L": (19, 355, 64, 128), "B": (85, 355, 64, 128),
              "R": (151, 355, 64, 128), "F": (217, 355, 64, 128), "D": (217, 485, 64, 64)},
    "larm":  {"U": (308, 289, 64, 64), "F": (308, 355, 64, 128), "L": (374, 355, 64, 128),
              "B": (440, 355, 64, 128), "R": (506, 355, 64, 128), "D": (308, 485, 64, 64)},
}
OUTER = {("rarm", "R"), ("larm", "L")}   # outward-facing sleeve faces (patch spot)


# --------------------------------------------------------------- helpers --
def hexc(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def mix(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(4))


def font(path, px):
    return ImageFont.truetype(path, int(px * S))


def gradient(w, h, c1, c2):
    img = Image.new("RGBA", (w * S, h * S))
    d = ImageDraw.Draw(img)
    for y in range(h * S):
        d.line([(0, y), (w * S, y)], fill=mix(c1, c2, y / max(1, h * S - 1)))
    return img


def sc(*v):
    return [x * S for x in v]


def glow_layer(size, draw_fn, radius=3, strength=2):
    """Draw shapes on a transparent layer, blur, and stack for a neon glow."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    blurred = layer.filter(ImageFilter.GaussianBlur(radius * S))
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    for _ in range(strength):
        out = Image.alpha_composite(out, blurred)
    return Image.alpha_composite(out, layer)


def comp(img, layer):
    img.alpha_composite(layer)


def text_fit(d, cx, cy, txt, path, max_w, px, fill, anchor="mm"):
    while px > 4:
        f = font(path, px)
        if d.textlength(txt, font=f) <= max_w * S:
            break
        px -= 0.5
    d.text((cx * S, cy * S), txt, font=f, fill=fill, anchor=anchor)


def poly(d, pts, **kw):
    d.polygon([(x * S, y * S) for x, y in pts], **kw)


def line(d, pts, width, fill):
    d.line([(x * S, y * S) for x, y in pts], fill=fill, width=int(width * S), joint="curve")


def circle(d, cx, cy, r, **kw):
    if "width" in kw:
        kw["width"] = int(kw["width"] * S)
    d.ellipse(sc(cx - r, cy - r, cx + r, cy + r), **kw)


def rrect(d, x0, y0, x1, y1, r, **kw):
    if "width" in kw:
        kw["width"] = int(kw["width"] * S)
    d.rounded_rectangle(sc(x0, y0, x1, y1), radius=r * S, **kw)


def hexagon(d, cx, cy, r, rot=0, **kw):
    pts = [(cx + r * math.cos(math.radians(60 * i + rot)),
            cy + r * math.sin(math.radians(60 * i + rot))) for i in range(6)]
    poly(d, pts, **kw)


def gear(d, cx, cy, r, teeth, fill, hole=None):
    pts = []
    for i in range(teeth * 4):
        a = 2 * math.pi * i / (teeth * 4)
        rr = r if (i % 4) in (0, 1) else r * 0.78
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    poly(d, pts, fill=fill)
    if hole:
        circle(d, cx, cy, r * 0.32, fill=hole)


def star(d, cx, cy, r, fill, points=5, inner=0.45, rot=-90):
    pts = []
    for i in range(points * 2):
        a = math.radians(rot + 180 * i / points)
        rr = r if i % 2 == 0 else r * inner
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    poly(d, pts, fill=fill)


def rotated_ellipse_layer(size, cx, cy, rx, ry, angle, outline, width):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(sc(cx - rx, cy - ry, cx + rx, cy + ry),
                                  outline=outline, width=int(width * S))
    return layer.rotate(angle, center=(cx * S, cy * S), resample=Image.BICUBIC)


def starfield(d, w, h, rng, n, color):
    for _ in range(n):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.choice([0.4, 0.5, 0.7, 1.0])
        a = rng.randint(120, 255)
        circle(d, x, y, r, fill=color[:3] + (a,))


# ------------------------------------------------- collection branding --
def emblem(d, cx, cy, r, ring, fill_c, accent):
    """Lunar Colony emblem: hex badge + crescent + orbit dot (shared by all items)."""
    hexagon(d, cx, cy, r, rot=30, fill=ring)
    hexagon(d, cx, cy, r * 0.82, rot=30, fill=fill_c)
    circle(d, cx - r * 0.08, cy, r * 0.48, fill=accent)
    circle(d, cx + r * 0.12, cy - r * 0.08, r * 0.42, fill=fill_c)
    circle(d, cx + r * 0.45, cy + r * 0.32, r * 0.11, fill=accent)


def sleeve_patch(d, cx, cy, r, p, symbol):
    circle(d, cx, cy, r, fill=p["trim"])
    circle(d, cx, cy, r * 0.84, fill=p["dark"])
    s = r * 0.5
    a = p["accent"]
    if symbol == "moon":
        circle(d, cx, cy, s, fill=a); circle(d, cx + s * 0.4, cy - s * 0.25, s * 0.85, fill=p["dark"])
    elif symbol == "code":
        text_fit(d, cx, cy, "</>", FONT_MONO, r * 1.5, r * 0.8, a)
    elif symbol == "atom":
        for ang in (0, 60, 120):
            pts = [(cx + s * math.cos(t) * math.cos(math.radians(ang)) - s * 0.35 * math.sin(t) * math.sin(math.radians(ang)),
                    cy + s * math.cos(t) * math.sin(math.radians(ang)) + s * 0.35 * math.sin(t) * math.cos(math.radians(ang)))
                   for t in [i * math.pi / 18 for i in range(37)]]
            line(d, pts, 0.8, a)
        circle(d, cx, cy, s * 0.2, fill=a)
    elif symbol == "gear":
        gear(d, cx, cy, s, 8, a, hole=p["dark"])
    elif symbol == "chip":
        rrect(d, cx - s * 0.6, cy - s * 0.6, cx + s * 0.6, cy + s * 0.6, 1, fill=a)
        for i in (-0.35, 0, 0.35):
            line(d, [(cx - s, cy + i * s), (cx + s, cy + i * s)], 0.6, a)
            line(d, [(cx + i * s, cy - s), (cx + i * s, cy + s)], 0.6, a)
        rrect(d, cx - s * 0.4, cy - s * 0.4, cx + s * 0.4, cy + s * 0.4, 1, fill=p["dark"])
    elif symbol == "star":
        star(d, cx, cy, s, a)
    elif symbol == "hex":
        hexagon(d, cx, cy, s, fill=a); hexagon(d, cx, cy, s * 0.5, fill=p["dark"])
    elif symbol == "planet":
        circle(d, cx, cy, s * 0.6, fill=a)
        line(d, [(cx - s, cy + s * 0.3), (cx + s, cy - s * 0.3)], 0.9, p["trim"])
    elif symbol == "void":
        circle(d, cx, cy, s * 0.8, fill=a); circle(d, cx, cy, s * 0.5, fill=(0, 0, 0, 255))
    elif symbol == "robot":
        rrect(d, cx - s * 0.7, cy - s * 0.5, cx + s * 0.7, cy + s * 0.6, 2, fill=a)
        circle(d, cx - s * 0.3, cy, s * 0.15, fill=p["dark"]); circle(d, cx + s * 0.3, cy, s * 0.15, fill=p["dark"])
        line(d, [(cx, cy - s * 0.5), (cx, cy - s * 0.9)], 0.8, a)


# ---------------------------------------------------- sleeve/side styles --
def style_sleeve(img, w, h, p, style, rng, outer, symbol, pants=False):
    d = ImageDraw.Draw(img)
    a, a2, trim = p["accent"], p["accent2"], p["trim"]
    if style == "circuit":
        def fn(g):
            for x in (w * 0.3, w * 0.7):
                pts = [(x, 0), (x, h * 0.35), (x + (8 if x < w / 2 else -8), h * 0.45), (x + (8 if x < w / 2 else -8), h * 0.8)]
                g.line([(px * S, py * S) for px, py in pts], fill=a, width=int(1.2 * S))
                g.ellipse(sc(pts[-1][0] - 2, pts[-1][1] - 2, pts[-1][0] + 2, pts[-1][1] + 2), fill=a)
        comp(img, glow_layer(img.size, fn, 1.5, 1))
    elif style == "stripes":
        for x0 in (w * 0.18, w * 0.72):
            d.rectangle(sc(x0, 0, x0 + 6, h), fill=a)
            d.rectangle(sc(x0 + 8, 0, x0 + 10, h), fill=a2)
    elif style == "hazard":
        band_y = h * 0.62
        d.rectangle(sc(0, band_y, w, band_y + 16), fill=a)
        for i in range(-2, 12):
            poly(d, [(i * 10, band_y + 16), (i * 10 + 6, band_y + 16), (i * 10 + 14, band_y), (i * 10 + 8, band_y)], fill=p["dark"])
    elif style == "code":
        for i in range(14):
            y = 6 + i * 8
            x = rng.choice([6, 10, 14])
            ln = rng.uniform(10, w - x - 6)
            d.rectangle(sc(x, y, x + ln, y + 2.5), fill=rng.choice([a, a2, trim])[:3] + (170,))
    elif style == "orbit":
        for k in range(3):
            comp(img, rotated_ellipse_layer(img.size, w / 2, h * 0.5, w * 0.7, 10 + k * 6, 25, a2[:3] + (140,), 0.8))
    elif style == "panels":
        for y in (h * 0.3, h * 0.6):
            d.rectangle(sc(0, y, w, y + 1.2), fill=p["dark"][:3] + (120,))
        for x in (w * 0.5,):
            d.rectangle(sc(x - 0.6, 0, x + 0.6, h), fill=p["dark"][:3] + (90,))
    elif style == "stars":
        starfield(d, w, h, rng, 40, (255, 255, 255, 255))
        for _ in range(3):
            star(d, rng.uniform(8, w - 8), rng.uniform(8, h - 30), rng.uniform(2, 3.5), a)
    # metallic joint (elbow / knee)
    if p.get("joint"):
        jy = h * 0.5
        d.rectangle(sc(0, jy - 6, w, jy + 6), fill=p["joint"])
        d.rectangle(sc(0, jy - 6, w, jy - 4.5), fill=mix(p["joint"], (255, 255, 255, 255), 0.5))
        d.rectangle(sc(0, jy + 4.5, w, jy + 6), fill=mix(p["joint"], (0, 0, 0, 255), 0.35))
        if p.get("glow"):
            comp(img, glow_layer(img.size, lambda g: g.rectangle(sc(0, jy - 1, w, jy + 1), fill=p["glow"]), 1.5, 2))
    # shoulder seam + cuff
    d.rectangle(sc(0, 0, w, 3), fill=trim)
    if pants:
        d.rectangle(sc(0, h - 20, w, h), fill=p.get("boot", trim))
        d.rectangle(sc(0, h - 22, w, h - 20), fill=a)
    else:
        d.rectangle(sc(0, h - 12, w, h), fill=trim)
        d.rectangle(sc(0, h - 14, w, h - 12), fill=a)
    if outer and not pants:
        sleeve_patch(d, w / 2, 24, 13, p, symbol)


def style_side(img, w, h, p):
    d = ImageDraw.Draw(img)
    d.rectangle(sc(w / 2 - 3, 0, w / 2 + 3, h), fill=p["trim"])
    d.rectangle(sc(w / 2 - 1, 0, w / 2 + 1, h), fill=p["accent"])
    d.rectangle(sc(0, h - 10, w, h), fill=p["trim"])


def hem(d, w, h, p):
    d.rectangle(sc(0, h - 10, w, h), fill=p["trim"])
    d.rectangle(sc(0, h - 12, w, h - 10), fill=p["accent"])


def collar(d, w, p):
    # V-ish collar at top of front face
    poly(d, [(w / 2 - 22, 0), (w / 2 + 22, 0), (w / 2, 14)], fill=p["trim"])
    poly(d, [(w / 2 - 15, 0), (w / 2 + 15, 0), (w / 2, 9)], fill=p["dark"])


# ============================================================ DESIGNS ====
# Each design: palette + front(img,w,h) + back(img,w,h) + sleeve style + patch.

def f_commander(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    # armored chest plate
    poly(d, [(14, 18), (w - 14, 18), (w - 8, 62), (w / 2 + 26, 104), (w / 2 - 26, 104), (8, 62)], fill=p["plate"])
    poly(d, [(14, 18), (w - 14, 18), (w - 8, 62), (w / 2 + 26, 104), (w / 2 - 26, 104), (8, 62)], outline=p["dark"], width=int(1.5 * S))
    for side in (-1, 1):  # pec plates
        x = w / 2 + side * 34
        poly(d, [(x - 22, 26), (x + 22, 26), (x + 18 * side if side > 0 else x + 18, 52), (x - 18, 52)], fill=p["plate2"])
    line(d, [(w / 2, 18), (w / 2, 34)], 1.2, p["dark"])
    # abdomen segments
    for i, y in enumerate((70, 82, 94)):
        inset = 18 + i * 8
        rrect(d, inset + 10, y, w - inset - 10, y + 8, 2, fill=p["plate2"], outline=p["dark"], width=0.8)
    # reactor core
    cx, cy = w / 2, 52

    def core(g):
        g.ellipse(sc(cx - 15, cy - 15, cx + 15, cy + 15), outline=p["glow"], width=int(2.5 * S))
        g.ellipse(sc(cx - 7, cy - 7, cx + 7, cy + 7), fill=p["glow"])
    circle(d, cx, cy, 19, fill=p["joint"])
    circle(d, cx, cy, 17, fill=p["dark"])
    comp(img, glow_layer(img.size, core, 3, 3))
    for k in range(8):
        a = math.radians(k * 45 + 22.5)
        line(d, [(cx + 10 * math.cos(a), cy + 10 * math.sin(a)), (cx + 15 * math.cos(a), cy + 15 * math.sin(a))], 1, p["dark"])
    circle(d, cx, cy, 3.5, fill=(255, 255, 255, 255))
    emblem(d, w - 26, 34, 7, p["trim"], p["dark"], p["glow"])
    text_fit(d, 28, 34, "MK-IV", FONT_BOLD, 28, 7, p["accent"])


def b_commander(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    # oxygen pack: two tanks + frame
    rrect(d, 18, 14, w - 18, 102, 8, fill=p["plate"], outline=p["dark"], width=1.5)
    for x in (32, w - 52):
        rrect(d, x, 20, x + 20, 92, 10, fill=p["joint"], outline=p["dark"], width=1)
        d.rectangle(sc(x + 3, 26, x + 6, 86), fill=mix(p["joint"], (255, 255, 255, 255), 0.55))
    rrect(d, w / 2 - 16, 26, w / 2 + 16, 88, 4, fill=p["dark"])
    for i in range(4):
        comp(img, glow_layer(img.size, lambda g, i=i: g.rectangle(sc(w / 2 - 10, 32 + i * 9, w / 2 + 10 - i * 4, 36 + i * 9), fill=p["glow"]), 1.5, 1))
    text_fit(d, w / 2, 80, "O2 100%", FONT_MONO, 26, 5, p["accent"])
    # hoses
    line(d, [(42, 20), (42, 8), (w / 2, 4)], 2, p["accent"])
    line(d, [(w - 42, 20), (w - 42, 8), (w / 2, 4)], 2, p["accent"])
    # mission patches
    sleeve_patch(d, 26, 112, 9, p, "moon")
    sleeve_patch(d, w - 26, 112, 9, p, "star")
    text_fit(d, w / 2, 112, "LUNAR COMMAND", FONT_BOLD, 52, 7, p["dark"])


def f_habitat(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    # hi-vis stripes
    for y in (64, 74):
        d.rectangle(sc(0, y, w, y + 5), fill=p["accent2"])
    # habitat emblem disc
    cx, cy = w / 2, 44
    circle(d, cx, cy, 30, fill=p["dark"])
    starfield(d, w, h, rng, 0, p["accent"])
    for _ in range(14):
        a = rng.uniform(0, 2 * math.pi); r = rng.uniform(0, 24)
        circle(d, cx + r * math.cos(a), cy - abs(r * math.sin(a)), 0.6, fill=(255, 255, 255, 220))
    d.pieslice(sc(cx - 30, cy - 30, cx + 30, cy + 30), 0, 180, fill=p["plate"])
    d.chord(sc(cx - 18, cy - 14, cx + 18, cy + 22), 180, 360, fill=p["trim"])
    for k in range(1, 4):
        line(d, [(cx - 18 + k * 9, cy + 4), (cx - 18 + k * 9, cy - 10 + abs(2 - k) * 3)], 0.7, p["dark"])
    rrect(d, cx + 16, cy - 2, cx + 26, cy + 4, 1, fill=p["trim"])
    circle(d, cx, cy, 30, outline=p["accent"], width=2)
    text_fit(d, cx, 92, "HABITAT ENGINEER", FONT_BOLD, 112, 10, p["text"])
    emblem(d, w - 16, 14, 7, p["trim"], p["dark"], p["accent"])
    # tool loops
    for x in (20, 34, w - 34, w - 20):
        rrect(d, x - 4, 104, x + 4, 116, 1, fill=p["dark"])


def b_habitat(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    for y in (64, 74):
        d.rectangle(sc(0, y, w, y + 5), fill=p["accent2"])
    text_fit(d, w / 2, 26, "CREW", FONT_BOLD, 60, 14, p["text"])
    text_fit(d, w / 2, 46, "07", FONT_BOLD, 60, 22, p["dark"])
    text_fit(d, w / 2, 96, "BUILD • SURVIVE • EXPLORE", FONT_MED, 112, 7, p["dark"])


def f_hacker(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    # hood drawstrings
    for x in (w / 2 - 12, w / 2 + 12):
        line(d, [(x, 0), (x, 30)], 1.4, p["trim"])
        circle(d, x, 31, 2, fill=p["accent"])
    # code window
    rrect(d, 18, 36, w - 18, 82, 4, fill=(5, 8, 6, 235), outline=p["accent"], width=1)
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        circle(d, 25 + i * 6, 41, 1.6, fill=hexc(c))
    lines = ["def explore(moon):", "  for crater in moon:", "    scan(crater)", "  return 'discovery'"]
    f = font(FONT_MONO, 5.2)
    for i, t in enumerate(lines):
        d.text(sc(24, 47 + i * 8), t, font=f, fill=[p["accent"], p["accent2"], p["text"], p["accent2"]][i])
    comp(img, glow_layer(img.size, lambda g: g.text(sc(w / 2, 22), "</>", font=font(FONT_MONO, 15), fill=p["accent"], anchor="mm"), 2, 2))
    # kangaroo pocket
    poly(d, [(26, 92), (w - 26, 92), (w - 16, 118), (16, 118)], fill=p["plate"])
    line(d, [(26, 92), (16, 118)], 1, p["accent"]); line(d, [(w - 26, 92), (w - 16, 118)], 1, p["accent"])
    emblem(d, w - 12, 90, 6, p["trim"], p["dark"], p["accent"])


def b_hacker(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    # hood outline
    d.chord(sc(14, -40, w - 14, 40), 0, 180, fill=p["plate"])
    d.arc(sc(14, -40, w - 14, 40), 0, 180, fill=p["accent"], width=int(1.2 * S))
    # binary rain
    f = font(FONT_MONO, 4.5)
    for col in range(14):
        x = 6 + col * 8.6
        for r in range(rng.randint(4, 11)):
            y = 46 + r * 6
            d.text(sc(x, y), rng.choice("01"), font=f, fill=p["accent"][:3] + (int(230 - r * 18),))
    comp(img, glow_layer(img.size, lambda g: g.text(sc(w / 2, 52), "QUANTUM", font=font(FONT_BOLD, 15), fill=p["text"], anchor="mm"), 2, 1))
    text_fit(d, w / 2, 70, "HACKER", FONT_BOLD, 80, 14, p["accent"])
    text_fit(d, w / 2, 112, "DEVELOPER ELITE", FONT_MONO, 90, 6, p["accent2"])


def pcb(d, w, h, p, rng, n=22):
    for _ in range(n):
        x, y = rng.uniform(4, w - 4), rng.uniform(4, h - 4)
        pts = [(x, y)]
        for _ in range(rng.randint(2, 4)):
            dx, dy = rng.choice([(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1)])
            ln = rng.uniform(8, 26)
            x = min(max(x + dx * ln, 3), w - 3); y = min(max(y + dy * ln, 3), h - 3)
            pts.append((x, y))
        line(d, pts, 1.1, p["accent"][:3] + (200,))
        circle(d, *pts[0], 2, fill=p["accent2"]); circle(d, *pts[-1], 1.6, fill=p["accent2"])


def f_circuit(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    pcb(d, w, h, p, rng)
    cx, cy = w / 2, 54
    for i in range(6):
        for side in (-1, 1):
            d.rectangle(sc(cx + side * 26 - 3, cy - 18 + i * 7, cx + side * 26 + 3, cy - 15 + i * 7), fill=p["accent2"])
            d.rectangle(sc(cx - 18 + i * 7, cy + side * 26 - 3, cx - 15 + i * 7, cy + side * 26 + 3), fill=p["accent2"])
    rrect(d, cx - 23, cy - 23, cx + 23, cy + 23, 3, fill=p["dark"])
    rrect(d, cx - 19, cy - 19, cx + 19, cy + 19, 2, outline=p["accent2"], width=0.8)
    text_fit(d, cx, cy - 4, "CA-01", FONT_MONO, 34, 8, p["accent2"])
    text_fit(d, cx, cy + 8, "CORE", FONT_BOLD, 30, 6, p["text"])
    text_fit(d, w / 2, 104, "CIRCUIT ARCHITECT", FONT_BOLD, 112, 10, p["text"])
    emblem(d, w - 14, 14, 7, p["trim"], p["dark"], p["accent2"])


def b_circuit(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    pcb(d, w, h, p, rng, 30)
    rrect(d, 10, 40, w - 10, 84, 4, fill=p["dark"])
    text_fit(d, w / 2, 56, "V = I × R", FONT_BOLD, 100, 14, p["accent2"])
    text_fit(d, w / 2, 74, "DESIGN • SOLDER • SHIP", FONT_MED, 100, 6, p["text"])


def f_orbital(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    starfield(d, w, h, rng, 60, (255, 255, 255, 255))
    cx, cy = w / 2, 56
    for rx, ry, ang in ((50, 18, -20), (40, 28, 30), (56, 12, 70)):
        comp(img, rotated_ellipse_layer(img.size, cx, cy, rx, ry, ang, p["accent2"][:3] + (200,), 0.8))
    comp(img, glow_layer(img.size, lambda g: g.ellipse(sc(cx - 12, cy - 12, cx + 12, cy + 12), fill=p["accent"]), 4, 2))
    circle(d, cx, cy, 12, fill=p["accent"])
    circle(d, cx - 3, cy - 3, 5, fill=mix(p["accent"], (255, 255, 255, 255), 0.5))
    for ang, r in ((200, 44), (20, 36), (300, 52)):
        a = math.radians(ang)
        circle(d, cx + r * math.cos(a), cy + r * 0.4 * math.sin(a), 3, fill=p["trim"])
    text_fit(d, w / 2, 102, "F = G·m₁m₂ / r²", FONT_MED, 100, 8, p["text"])
    emblem(d, w - 14, 14, 7, p["trim"], p["dark"], p["accent"])


def b_orbital(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    starfield(d, w, h, rng, 50, (255, 255, 255, 255))
    text_fit(d, w / 2, 30, "ORBITAL", FONT_BOLD, 100, 16, p["text"])
    text_fit(d, w / 2, 50, "MECHANICS", FONT_BOLD, 100, 13, p["accent2"])
    # hohmann transfer diagram
    cx, cy = w / 2, 92
    circle(d, cx, cy, 4, fill=p["accent"])
    circle(d, cx, cy, 14, outline=p["trim"], width=0.8)
    circle(d, cx, cy, 30, outline=p["trim"], width=0.8)
    d.arc(sc(cx - 14, cy - 22, cx + 30 + 16, cy + 22), 180, 360, fill=p["accent2"], width=int(1.2 * S))


def f_rover(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    # dunes
    poly(d, [(0, 86), (30, 76), (64, 84), (100, 72), (w, 80), (w, h), (0, h)], fill=p["plate"])
    circle(d, 100, 26, 9, fill=p["accent2"])
    cx = w / 2
    # rover body
    rrect(d, cx - 34, 52, cx + 34, 66, 2, fill=p["trim"], outline=p["dark"], width=1)
    d.rectangle(sc(cx - 26, 46, cx + 10, 52), fill=p["accent"])
    line(d, [(cx + 22, 52), (cx + 22, 32)], 1.5, p["dark"])
    rrect(d, cx + 16, 26, cx + 30, 34, 1, fill=p["trim"], outline=p["dark"], width=0.8)
    circle(d, cx + 26, 30, 2, fill=p["dark"])
    line(d, [(cx - 30, 46), (cx - 30, 36)], 1, p["dark"]); circle(d, cx - 30, 35, 2.5, fill=p["accent2"])
    for x in (cx - 28, cx - 10, cx + 10, cx + 28):
        line(d, [(x, 66), (x, 72)], 1.5, p["dark"])
        circle(d, x, 76, 6, fill=p["dark"]); circle(d, x, 76, 2.5, fill=p["joint"])
    text_fit(d, w / 2, 102, "MARS ROVER PILOT", FONT_BOLD, 112, 10, p["text"])
    emblem(d, 14, 14, 7, p["trim"], p["dark"], p["accent2"])


def b_rover(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    poly(d, [(0, 96), (40, 88), (80, 94), (w, 86), (w, h), (0, h)], fill=p["plate"])
    text_fit(d, w / 2, 32, "SOL", FONT_BOLD, 60, 14, p["text"])
    text_fit(d, w / 2, 56, "1024", FONT_BOLD, 100, 22, p["accent2"])
    # tire track
    for i in range(10):
        d.rectangle(sc(8 + i * 12, 106, 14 + i * 12, 112), fill=p["dark"])


def f_robotics(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    cx, cy = w / 2, 52
    line(d, [(cx, 18), (cx, 10)], 2, p["dark"])
    comp(img, glow_layer(img.size, lambda g: g.ellipse(sc(cx - 4, 4, cx + 4, 12), fill=p["glow"]), 2, 2))
    rrect(d, cx - 36, 18, cx + 36, 80, 12, fill=p["dark"])
    rrect(d, cx - 30, 24, cx + 30, 74, 9, fill=p["plate"])
    for side in (-1, 1):
        comp(img, glow_layer(img.size, lambda g, s=side: g.ellipse(sc(cx + s * 14 - 8, 38, cx + s * 14 + 8, 54), fill=p["glow"]), 2.5, 2))
        circle(d, cx + side * 14, 46, 3, fill=(255, 255, 255, 255))
        rrect(d, cx + side * 40 - 4, 36, cx + side * 40 + 4, 60, 2, fill=p["dark"])
    for i in range(5):
        d.rectangle(sc(cx - 15 + i * 6.5, 62, cx - 11 + i * 6.5, 68), fill=p["dark"])
    # hazard band
    d.rectangle(sc(0, 86, w, 98), fill=p["accent"])
    for i in range(-2, 16):
        poly(d, [(i * 10, 98), (i * 10 + 5, 98), (i * 10 + 11, 86), (i * 10 + 6, 86)], fill=p["dark"])
    text_fit(d, w / 2, 107, "ROBOTICS CREW", FONT_BOLD, 100, 9, p["accent"])
    emblem(d, w - 14, 14, 7, p["trim"], p["dark"], p["accent"])


def b_robotics(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    gear(d, 30, 30, 18, 10, p["plate"], hole=p["base1"])
    gear(d, 58, 46, 12, 8, p["accent"], hole=p["base1"])
    text_fit(d, 92, 32, "TEAM", FONT_BOLD, 54, 12, p["text"])
    text_fit(d, w / 2, 78, "BUILD.", FONT_BOLD, 110, 13, p["accent"])
    text_fit(d, w / 2, 96, "CODE. COMPETE.", FONT_BOLD, 110, 11, p["text"])
    d.rectangle(sc(0, 108, w, 116), fill=p["accent"])


def f_telescope(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    starfield(d, w, h, rng, 70, (255, 255, 255, 255))
    cx, cy, r = w / 2, 52, 9
    dx, dy = r * 1.5, r * math.sqrt(3)
    cells = [(0, 0)]
    for ring in range(1, 3):  # 2 rings of hexes around center = 19 cells
        q, rr = ring, 0
        dirs = [(-1, 1), (-1, 0), (0, -1), (1, -1), (1, 0), (0, 1)]
        for dq, dr in dirs:
            for _ in range(ring):
                cells.append((q, rr)); q += dq; rr += dr
    def mirrors(g):
        for q, rr in cells:
            if (q, rr) == (0, 0):
                continue
            x = cx + dx * q; y = cy + dy * (rr + q / 2)
            g.polygon([((x + r * 0.95 * math.cos(math.radians(60 * i))) * S, (y + r * 0.95 * math.sin(math.radians(60 * i))) * S) for i in range(6)], fill=p["accent"])
    comp(img, glow_layer(img.size, mirrors, 3, 1))
    for q, rr in cells:
        if (q, rr) == (0, 0):
            continue
        x = cx + dx * q; y = cy + dy * (rr + q / 2)
        hexagon(d, x - 1.5, y - 1.5, r * 0.4, fill=mix(p["accent"], (255, 255, 255, 255), 0.45))
    hexagon(d, cx, cy, r * 0.8, fill=p["dark"])
    text_fit(d, w / 2, 112, "SEE FURTHER", FONT_BOLD, 100, 9, p["accent"])
    emblem(d, 14, 14, 7, p["trim"], p["dark"], p["accent"])


def b_telescope(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    starfield(d, w, h, rng, 80, (255, 255, 255, 255))
    # spiral galaxy
    cx, cy = w / 2, 44
    for arm in range(2):
        for i in range(70):
            t = i / 10
            a = t + arm * math.pi
            r = 2 + t * 4.2
            circle(d, cx + r * math.cos(a), cy + r * 0.55 * math.sin(a), max(0.5, 1.8 - t * 0.2), fill=p["accent2"][:3] + (220,))
    comp(img, glow_layer(img.size, lambda g: g.ellipse(sc(cx - 5, cy - 3, cx + 5, cy + 3), fill=p["accent"]), 3, 2))
    text_fit(d, w / 2, 86, "DEEP SPACE", FONT_BOLD, 100, 13, p["text"])
    text_fit(d, w / 2, 102, "OBSERVATORY", FONT_MED, 100, 8, p["accent"])


def f_singularity(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    starfield(d, w, h, rng, 50, (230, 210, 255, 255))
    cx, cy = w / 2, 56
    for k, (rx, ry) in enumerate(((52, 12), (44, 9), (36, 7))):
        comp(img, glow_layer(img.size, lambda g, rx=rx, ry=ry, k=k: g.ellipse(sc(cx - rx, cy - ry, cx + rx, cy + ry), outline=[p["accent"], p["accent2"], p["glow"]][k], width=int(2 * S)), 2.5, 2))
    comp(img, glow_layer(img.size, lambda g: g.ellipse(sc(cx - 19, cy - 19, cx + 19, cy + 19), outline=p["accent"], width=int(2 * S)), 4, 3))
    circle(d, cx, cy, 17, fill=(0, 0, 0, 255))
    # front of disk passes over the hole
    d.chord(sc(cx - 52, cy - 12, cx + 52, cy + 12), 0, 180, outline=p["accent2"], width=int(2 * S))
    # energy cracks
    for side in (-1, 1):
        pts = [(cx + side * 22, cy + 22), (cx + side * 30, cy + 36), (cx + side * 26, cy + 46), (cx + side * 40, cy + 60)]
        comp(img, glow_layer(img.size, lambda g, pts=pts: g.line([(x * S, y * S) for x, y in pts], fill=p["glow"], width=int(1.2 * S)), 1.5, 2))
    text_fit(d, w / 2, 112, "SINGULARITY", FONT_BOLD, 100, 10, p["text"])
    emblem(d, w - 14, 14, 7, p["trim"], p["dark"], p["accent"])


def b_singularity(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    starfield(d, w, h, rng, 60, (230, 210, 255, 255))
    # crystalline wing silhouettes
    for side in (-1, 1):
        cx = w / 2
        pts = [(cx + side * 6, 40), (cx + side * 56, 8), (cx + side * 50, 34), (cx + side * 60, 46), (cx + side * 40, 60), (cx + side * 52, 78), (cx + side * 8, 64)]
        poly(d, pts, fill=p["plate"])
        for a, b in ((0, 1), (0, 3), (0, 5)):
            comp(img, glow_layer(img.size, lambda g, a=a, b=b: g.line([(pts[a][0] * S, pts[a][1] * S), (pts[b][0] * S, pts[b][1] * S)], fill=p["glow"], width=int(0.9 * S)), 1.2, 2))
    comp(img, glow_layer(img.size, lambda g: g.ellipse(sc(w / 2 - 7, 45, w / 2 + 7, 59), fill=p["accent"]), 3, 3))
    text_fit(d, w / 2, 98, "VOID CORE", FONT_BOLD, 100, 14, p["accent2"])
    text_fit(d, w / 2, 114, "EVENT HORIZON DIVISION", FONT_MED, 100, 5.5, p["text"])


def star_crown(d, img, cx, cy, s, p):
    """Original geometric 'star crown' sigil: halo ring, five crystal spires, jeweled band."""
    comp(img, glow_layer(img.size, lambda g: g.ellipse(sc(cx - s * 0.95, cy - s * 0.75, cx + s * 0.95, cy + s * 0.75), outline=p["glow"], width=int(1.5 * S)), 3, 2))
    spires = [(-0.72, 0.62), (-0.36, 0.88), (0, 1.15), (0.36, 0.88), (0.72, 0.62)]
    base_y = cy + s * 0.32
    for dx, hh in spires:
        x = cx + dx * s
        tip = (x, base_y - s * hh)
        poly(d, [(x - s * 0.17, base_y), tip, (x + s * 0.17, base_y)], fill=p["plate"])
        poly(d, [(x, base_y), tip, (x + s * 0.17, base_y)], fill=mix(p["plate"], (255, 255, 255, 255), 0.18))
        line(d, [(x - s * 0.17, base_y), tip, (x + s * 0.17, base_y)], 0.8, p["accent"])
        star(d, tip[0], tip[1] - s * 0.06, s * (0.13 if dx else 0.2), p["accent2"])
    rrect(d, cx - s * 0.92, base_y - 1, cx + s * 0.92, base_y + s * 0.34, 3, fill=p["trim"])
    rrect(d, cx - s * 0.92, base_y + s * 0.26, cx + s * 0.92, base_y + s * 0.34, 1, fill=mix(p["trim"], (0, 0, 0, 255), 0.3))
    for k, dx in enumerate((-0.6, -0.3, 0, 0.3, 0.6)):
        col = p["accent"] if k % 2 == 0 else p["glow"]
        comp(img, glow_layer(img.size, lambda g, dx=dx, col=col: g.ellipse(sc(cx + dx * s - 3, base_y + s * 0.13 - 3, cx + dx * s + 3, base_y + s * 0.13 + 3), fill=col), 1.5, 2))


def f_cosmic(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    # nebula blobs
    neb = Image.new("RGBA", img.size, (0, 0, 0, 0))
    nd = ImageDraw.Draw(neb)
    for _ in range(9):
        x, y, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(14, 30)
        circle(nd, x, y, r, fill=rng.choice([p["accent"], p["accent2"], p["glow"]])[:3] + (70,))
    comp(img, neb.filter(ImageFilter.GaussianBlur(10 * S)))
    starfield(d, w, h, rng, 80, (255, 255, 255, 255))
    star_crown(d, img, w / 2, 54, 32, p)
    # orbiting asteroids
    comp(img, rotated_ellipse_layer(img.size, w / 2, 50, 50, 14, -12, p["trim"][:3] + (160,), 0.7))
    for ang in (30, 160, 250):
        a = math.radians(ang)
        circle(d, w / 2 + 50 * math.cos(a), 50 + 14 * math.sin(a) - 10 * math.cos(a) * 0.2, 2.2, fill=p["trim"])
    text_fit(d, w / 2, 98, "COSMIC DOMINION", FONT_BOLD, 112, 10, p["text"])
    text_fit(d, w / 2, 110, "FORGED FROM COLLAPSED STARS", FONT_MED, 110, 5, p["accent2"])
    emblem(d, 14, 14, 7, p["trim"], p["dark"], p["accent2"])


def b_cosmic(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    neb = Image.new("RGBA", img.size, (0, 0, 0, 0))
    nd = ImageDraw.Draw(neb)
    for _ in range(8):
        circle(nd, rng.uniform(0, w), rng.uniform(0, h), rng.uniform(14, 30), fill=rng.choice([p["accent"], p["accent2"]])[:3] + (60,))
    comp(img, neb.filter(ImageFilter.GaussianBlur(10 * S)))
    starfield(d, w, h, rng, 90, (255, 255, 255, 255))
    # constellation
    pts = [(20, 30), (40, 18), (62, 26), (80, 14), (104, 24), (92, 46), (64, 52)]
    line(d, pts, 0.6, p["trim"][:3] + (180,))
    for x, y in pts:
        star(d, x, y, 2.8, p["accent2"], points=4, inner=0.35)
    text_fit(d, w / 2, 82, "THE UNIVERSE", FONT_BOLD, 110, 11, p["text"])
    text_fit(d, w / 2, 98, "BENDS AROUND YOU", FONT_BOLD, 110, 9, p["accent2"])


def f_gearworks(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    # blueprint grid
    for x in range(0, w, 8):
        d.line(sc(x, 0, x, h), fill=p["trim"][:3] + (40,), width=S // 2)
    for y in range(0, h, 8):
        d.line(sc(0, y, w, y), fill=p["trim"][:3] + (40,), width=S // 2)
    gear(d, 50, 50, 28, 12, p["accent"], hole=p["base1"])
    gear(d, 86, 70, 18, 9, p["accent2"], hole=p["base1"])
    gear(d, 92, 34, 11, 7, p["trim"], hole=p["base1"])
    d.rectangle(sc(14, 90, w - 14, 91), fill=p["trim"])
    text_fit(d, w / 2, 102, "MECHANICAL ENGINEER", FONT_BOLD, 112, 9, p["text"])
    text_fit(d, w / 2, 113, "τ = r × F", FONT_MED, 60, 7, p["accent2"])
    emblem(d, w - 14, 14, 7, p["trim"], p["dark"], p["accent"])


def b_gearworks(img, w, h, p, rng):
    d = ImageDraw.Draw(img)
    for x in range(0, w, 8):
        d.line(sc(x, 0, x, h), fill=p["trim"][:3] + (40,), width=S // 2)
    for y in range(0, h, 8):
        d.line(sc(0, y, w, y), fill=p["trim"][:3] + (40,), width=S // 2)
    # dimensioned part drawing
    rrect(d, 30, 20, 98, 60, 4, outline=p["trim"], width=1)
    circle(d, 64, 40, 10, outline=p["trim"], width=1)
    line(d, [(30, 66), (98, 66)], 0.6, p["accent2"])
    text_fit(d, 64, 71, "68.00 mm", FONT_MONO, 40, 4.5, p["accent2"])
    text_fit(d, w / 2, 92, "GEAR WORKS", FONT_BOLD, 110, 14, p["text"])
    text_fit(d, w / 2, 108, "MEASURE TWICE • CUT ONCE", FONT_MED, 110, 5.5, p["accent"])


# palette factory ----------------------------------------------------------
def pal(base1, base2, accent, accent2, trim, dark, text, plate=None, plate2=None, joint=None, glow=None, boot=None):
    d = dict(base1=hexc(base1), base2=hexc(base2), accent=hexc(accent), accent2=hexc(accent2),
             trim=hexc(trim), dark=hexc(dark), text=hexc(text))
    d["plate"] = hexc(plate) if plate else d["base1"]
    d["plate2"] = hexc(plate2) if plate2 else d["base2"]
    d["joint"] = hexc(joint) if joint else None
    d["glow"] = hexc(glow) if glow else None
    d["boot"] = hexc(boot) if boot else None
    return d


SHIRTS = [
    dict(file="lunar_commander_mk4_shirt", name="Lunar Commander Mk-IV",
         theme="Flagship armored suit top for the colony's commanding officer.",
         lore="Lead humanity's first permanent lunar settlement. Built for explorers, engineers, and visionaries.",
         front=f_commander, back=b_commander, sleeve="circuit", patch="moon",
         p=pal("#f4f7fb", "#dfe6ef", "#1fd6ff", "#7fe9ff", "#c3ccd8", "#13254a", "#13254a",
               plate="#ffffff", plate2="#e8edf4", joint="#9aa6b5", glow="#22e3ff")),
    dict(file="lunar_habitat_engineer_shirt", name="Lunar Habitat Engineer",
         theme="Hi-vis work shirt for the crews who build and maintain the colony's pressurized domes.",
         lore="Every dome on the Moon was raised by someone in this shirt.",
         front=f_habitat, back=b_habitat, sleeve="panels", patch="hex",
         p=pal("#ff8a1f", "#f26b0f", "#1d2433", "#e9f0f7", "#c9d2dc", "#1d2433", "#1d2433",
               plate="#b7bec8")),
    dict(file="quantum_hacker_hoodie_shirt", name="Quantum Hacker Hoodie",
         theme="Developer Elite hoodie — terminal window, binary rain and neon trim for programmers.",
         lore="Compiles at the speed of light. Debugs across parallel universes.",
         front=f_hacker, back=b_hacker, sleeve="code", patch="code",
         p=pal("#15171c", "#0b0c10", "#39ff88", "#00e5ff", "#2a2e37", "#0b0c10", "#e8fff1",
               plate="#1f232b")),
    dict(file="circuit_architect_shirt", name="Circuit Architect",
         theme="Green PCB with gold traces and a central processor — for electronics and hardware builders.",
         lore="Designs the nervous system of every machine on the colony.",
         front=f_circuit, back=b_circuit, sleeve="circuit", patch="chip",
         p=pal("#0f5d3a", "#0a4229", "#3ddc84", "#ffc94a", "#d4a52c", "#062618", "#f2fff6")),
    dict(file="orbital_mechanics_shirt", name="Orbital Mechanics",
         theme="Deep navy star chart with orbital ellipses, a glowing planet and the law of gravitation.",
         lore="Every launch window is a math problem. Solve it.",
         front=f_orbital, back=b_orbital, sleeve="orbit", patch="planet",
         p=pal("#0e1a3d", "#060c22", "#ffb547", "#8fb6ff", "#dfe7ff", "#060c22", "#ffffff")),
    dict(file="mars_rover_pilot_shirt", name="Mars Rover Pilot",
         theme="Rust-red Martian dunes with a six-wheeled science rover — for planetary explorers.",
         lore="Sol 1024. Still driving. Still discovering.",
         front=f_rover, back=b_rover, sleeve="stripes", patch="planet",
         p=pal("#c4532d", "#8e3318", "#f5d6a8", "#ffe08a", "#efe4d6", "#2a1610", "#fff4e6",
               plate="#a8431f", joint="#c7c7c7")),
    dict(file="robotics_crew_shirt", name="Robotics Crew",
         theme="Bold yellow-and-charcoal team shirt with a glowing robot face and hazard stripes.",
         lore="Build. Code. Compete. Repeat until it walks.",
         front=f_robotics, back=b_robotics, sleeve="hazard", patch="robot",
         p=pal("#2b2f36", "#1d2026", "#ffcc1a", "#ffe066", "#e6e8eb", "#14161a", "#ffffff",
               plate="#d9dde3", glow="#36c8ff")),
    dict(file="deep_space_telescope_shirt", name="Deep Space Observatory",
         theme="Gold segmented hexagonal mirror on a black starfield, with a spiral galaxy on the back.",
         lore="Looks back 13 billion years so we can see what comes next.",
         front=f_telescope, back=b_telescope, sleeve="stars", patch="hex",
         p=pal("#0b0b12", "#020205", "#f2b632", "#9ad0ff", "#cfa23a", "#020205", "#ffffff")),
    dict(file="singularity_core_shirt", name="Singularity Core",
         theme="Black hole with a glowing accretion disk and crystalline wings — matches the Void Core pet & Singularity Wings concepts.",
         lore="Nothing escapes the event horizon. Not even style.",
         front=f_singularity, back=b_singularity, sleeve="stars", patch="void",
         p=pal("#140a24", "#06030d", "#a64dff", "#3fd0ff", "#7a5aa8", "#06030d", "#f1e8ff",
               plate="#1e1233", glow="#c88bff")),
    dict(file="cosmic_dominion_shirt", name="Cosmic Dominion",
         theme="Indigo nebula with an original star-crown sigil and orbiting asteroids — matches the Cosmic Dominion Crown concept.",
         lore="A relic forged from the remnants of collapsed stars. The universe bends around its wearer.",
         front=f_cosmic, back=b_cosmic, sleeve="stars", patch="star",
         p=pal("#1a1450", "#0a0726", "#3d7bff", "#ffd36b", "#9fb4ff", "#0a0726", "#ffffff",
               plate="#2b2470", glow="#c04dff")),
]

# Gear Works is defined for future drops but the collection ships 10; keep it reachable:
EXTRA = dict(file="gear_works_engineer_shirt", name="Gear Works Engineer",
             theme="Blueprint grid with meshing gears and a dimensioned part drawing.",
             lore="Measure twice. Cut once. Launch forever.",
             front=f_gearworks, back=b_gearworks, sleeve="panels", patch="gear",
             p=pal("#1b4f8a", "#123a68", "#ff9a3c", "#ffd08a", "#cfe3ff", "#0b2340", "#ffffff"))

PANTS = [
    dict(file="lunar_commander_mk4_pants", name="Lunar Commander Mk-IV Pants",
         theme="Matching armored legs: white plating, metallic knee joints with cyan glow, silver boots.",
         sleeve="circuit", belt=True,
         p=pal("#eef2f7", "#d9e0ea", "#1fd6ff", "#7fe9ff", "#13254a", "#13254a", "#13254a",
               joint="#9aa6b5", glow="#22e3ff", boot="#9aa6b5")),
    dict(file="circuit_pants", name="Developer Elite Circuit Pants",
         theme="Matching Developer Elite pants: black with neon-green circuit traces and glowing cuffs.",
         sleeve="circuit", belt=True,
         p=pal("#15171c", "#0b0c10", "#39ff88", "#00e5ff", "#2a2e37", "#0b0c10", "#e8fff1",
               boot="#2a2e37")),
]


# ---------------------------------------------------------- rendering ----
def render(spec, pants=False):
    rng = random.Random(spec["file"])
    p = spec["p"]
    canvas = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    for part, faces in FACES.items():
        for key, (x, y, w, h) in faces.items():
            img = gradient(w, h, p["base1"], p["base2"])
            d = ImageDraw.Draw(img)
            if part == "torso":
                if key == "F":
                    if pants:
                        pants_waist(img, w, h, p, front=True)
                    else:
                        spec["front"](img, w, h, p, rng); collar(d, w, p); hem(d, w, h, p)
                elif key == "B":
                    if pants:
                        pants_waist(img, w, h, p, front=False)
                    else:
                        spec["back"](img, w, h, p, rng); hem(d, w, h, p)
                elif key in ("L", "R"):
                    style_side(img, w, h, p)
                    if pants:
                        d.rectangle(sc(0, 0, w, 10), fill=p["dark"])
                elif key == "U":
                    if pants:
                        d.rectangle(sc(0, 0, w * 1, h), fill=p["dark"])
                    else:
                        d.ellipse(sc(w / 2 - 20, h / 2 - 12, w / 2 + 20, h / 2 + 12), fill=p["trim"])
                        d.ellipse(sc(w / 2 - 15, h / 2 - 8, w / 2 + 15, h / 2 + 8), fill=p["dark"])
                elif key == "D":
                    d.rectangle(sc(0, 0, w, h), fill=p["trim"])
            else:
                if key in ("L", "R", "F", "B"):
                    style_sleeve(img, w, h, p, spec["sleeve"], rng, (part, key) in OUTER,
                                 spec.get("patch", "moon"), pants=pants)
                elif key == "U":
                    d.rectangle(sc(0, 0, w, h), fill=p["trim"] if not pants else p["base1"])
                elif key == "D":
                    d.rectangle(sc(0, 0, w, h), fill=(p.get("boot") or p["trim"]) if pants else p["trim"])
            canvas.paste(img, (x * S, y * S))
    out = canvas.resize((W, H), Image.LANCZOS)
    return out


def pants_waist(img, w, h, p, front):
    d = ImageDraw.Draw(img)
    d.rectangle(sc(0, 0, w, 12), fill=p["dark"])
    d.rectangle(sc(0, 12, w, 14), fill=p["accent"])
    if front:
        rrect(d, w / 2 - 10, 1, w / 2 + 10, 11, 2, fill=p["trim"])
        comp(img, glow_layer(img.size, lambda g: g.ellipse(sc(w / 2 - 3, 3, w / 2 + 3, 9), fill=p["accent"]), 1.5, 2))
        line(d, [(w / 2, 14), (w / 2, 40)], 0.8, p["dark"][:3] + (150,))
        emblem(d, 18, 30, 6, p["trim"], p["dark"], p["accent"])
    else:
        for x in (20, w - 34):
            rrect(d, x, 24, x + 14, 40, 2, outline=p["dark"], width=0.8)
    # hip piping into legs
    for x in (6, w - 8):
        d.rectangle(sc(x, 14, x + 2, h), fill=p["accent"][:3] + (160,))


def mockup(tex, scale=3, pants_tex=None):
    """Flat blocky-avatar front/back preview (generic grey avatar, no logos)."""
    def crop(part, key):
        x, y, w, h = FACES[part][key]
        return tex.crop((x, y, x + w, y + h))
    pad = 24
    fig_w, fig_h = 256, 64 + 128 + 128
    out = Image.new("RGBA", ((fig_w + pad * 2) * 2, fig_h + pad * 2 + 18), (0, 0, 0, 0))
    skin = (198, 202, 210, 255); leg = (92, 98, 110, 255)
    d = ImageDraw.Draw(out)
    f_label = ImageFont.truetype(FONT_BOLD, 13)
    for i, view in enumerate(("FRONT", "BACK")):
        ox, oy = pad + i * (fig_w + pad * 2), pad
        d.rounded_rectangle([ox + 96, oy, ox + 160, oy + 62], 10, fill=skin)
        if view == "FRONT":
            d.ellipse([ox + 112, oy + 22, ox + 120, oy + 32], fill=(40, 40, 50, 255))
            d.ellipse([ox + 136, oy + 22, ox + 144, oy + 32], fill=(40, 40, 50, 255))
            d.arc([ox + 114, oy + 30, ox + 142, oy + 48], 20, 160, fill=(40, 40, 50, 255), width=3)
            parts = [("rarm", "F", 0), ("torso", "F", 64), ("larm", "F", 192)]
            legs = [("rarm", "F", 64), ("larm", "F", 128)]
        else:
            parts = [("larm", "B", 0), ("torso", "B", 64), ("rarm", "B", 192)]
            legs = [("larm", "B", 64), ("rarm", "B", 128)]
        for part, key, dx in parts:
            out.paste(crop(part, key), (ox + dx, oy + 64))
        for part, key, dx in legs:
            if pants_tex is not None:
                x, y, w, h = FACES[part][key]
                out.paste(pants_tex.crop((x, y, x + w, y + h)), (ox + dx, oy + 192))
            else:
                d.rectangle([ox + dx, oy + 192, ox + dx + 63, oy + 319], fill=leg)
        d.text((ox + 128, oy + fig_h + 10), view, font=f_label, fill=(140, 150, 165, 255), anchor="mm")
    return out.resize((out.width * scale // 2, out.height * scale // 2), Image.NEAREST)


def pants_mockup(tex, scale=3):
    gray = Image.new("RGBA", (W, H), (150, 156, 168, 255))
    return mockup(gray, scale, pants_tex=tex)


def main():
    rendered = []
    for spec in SHIRTS:
        tex = render(spec)
        tex.save(os.path.join(OUT_SHIRTS, spec["file"] + ".png"), optimize=True)
        prev = mockup(tex)
        prev.save(os.path.join(OUT_PREV, spec["file"] + "_preview.png"), optimize=True)
        rendered.append((spec, tex, prev))
        print("shirt:", spec["file"])
    pants_tex = {}
    for spec in PANTS:
        tex = render(spec, pants=True)
        tex.save(os.path.join(OUT_PANTS, spec["file"] + ".png"), optimize=True)
        pants_tex[spec["file"]] = tex
        print("pants:", spec["file"])
    # matching-set previews
    sets = [("lunar_commander_mk4_shirt", "lunar_commander_mk4_pants", "lunar_commander_mk4_set"),
            ("quantum_hacker_hoodie_shirt", "circuit_pants", "developer_elite_set")]
    for shirt_file, pants_file, name in sets:
        tex = next(t for s, t, _ in rendered if s["file"] == shirt_file)
        mockup(tex, pants_tex=pants_tex[pants_file]).save(os.path.join(OUT_PREV, name + "_preview.png"), optimize=True)
    # collection contact sheet
    cols, cell_w, cell_h = 5, 300, 230
    sheet = Image.new("RGBA", (cols * cell_w, 2 * cell_h + 90), hexc("#0b1020"))
    d = ImageDraw.Draw(sheet)
    d.text((sheet.width // 2, 44), "JAKING  •  LUNAR COLONY COLLECTION", font=ImageFont.truetype(FONT_BOLD, 34),
           fill=hexc("#e8f6ff"), anchor="mm")
    f_name = ImageFont.truetype(FONT_BOLD, 15)
    for i, (spec, tex, prev) in enumerate(rendered):
        cx, cy = (i % cols) * cell_w, 90 + (i // cols) * cell_h
        d.rounded_rectangle([cx + 10, cy + 6, cx + cell_w - 10, cy + cell_h - 10], 16, fill=hexc("#141b30"))
        thumb = mockup(tex, scale=2)
        thumb.thumbnail((cell_w - 30, cell_h - 60), Image.LANCZOS)
        sheet.alpha_composite(thumb, (cx + (cell_w - thumb.width) // 2, cy + 18))
        d.text((cx + cell_w // 2, cy + cell_h - 30), spec["name"], font=f_name, fill=hexc("#cfe6ff"), anchor="mm")
    sheet.convert("RGB").save(os.path.join(OUT_PREV, "collection_sheet.png"), optimize=True)
    print("done")


if __name__ == "__main__":
    main()
