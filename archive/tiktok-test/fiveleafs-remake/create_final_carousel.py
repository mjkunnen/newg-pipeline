"""
Create the final "Can't wait to..." TikTok carousel (Concept 1) using board remakes.
4 slides:
  Slide 1: Single photo + "Can't wait to drink..."
  Slide 2: Single photo + "Can't wait to party..."
  Slide 3: 2x2 grid + "Can't wait to get fly this weekend?"
  Slide 4: NEWGARMENTS product collage (archive sale)
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

BASE = Path(__file__).parent
OUTPUT = BASE / "final_carousel"
OUTPUT.mkdir(exist_ok=True)

BOARD_REMAKES = BASE / "board_remakes"
PRODUCT_REFS = Path(__file__).parent.parent.parent / "content-library" / "product-refs"

W, H = 1080, 1920

FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
]

def load_font(size):
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def fit_image(img, target_w, target_h):
    img_ratio = img.width / img.height
    target_ratio = target_w / target_h
    if img_ratio > target_ratio:
        new_w = int(img.height * target_ratio)
        left = (img.width - new_w) // 2
        img = img.crop((left, 0, left + new_w, img.height))
    else:
        new_h = int(img.width / target_ratio)
        top = (img.height - new_h) // 2
        img = img.crop((0, top, img.width, top + new_h))
    return img.resize((target_w, target_h), Image.LANCZOS)


def draw_text_outline(draw, pos, text, font, fill="white", outline="black", width=4):
    x, y = pos
    for dx in range(-width, width + 1):
        for dy in range(-width, width + 1):
            if dx*dx + dy*dy <= width*width:
                draw.text((x+dx, y+dy), text, font=font, fill=outline)
    draw.text(pos, text, font=font, fill=fill)


def centered_text(draw, y, text, font, fill="white", outline="black", canvas_w=W):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (canvas_w - tw) // 2
    draw_text_outline(draw, (x, y), text, font, fill=fill, outline=outline)


def make_single_photo_slide(image_path, text_lines, text_pos="center"):
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    try:
        img = Image.open(image_path).convert("RGB")
        img = fit_image(img, W, H)
        canvas.paste(img, (0, 0))
    except Exception as e:
        print(f"  Warning: Could not load {image_path}: {e}")
    draw = ImageDraw.Draw(canvas)
    font = load_font(72)
    if text_pos == "center":
        total_h = len(text_lines) * 90
        start_y = (H - total_h) // 2
    elif text_pos == "bottom":
        start_y = H - len(text_lines) * 90 - 200
    else:
        start_y = 150
    for line in text_lines:
        centered_text(draw, start_y, line, font)
        start_y += 90
    return canvas


def make_grid_slide(images, text_lines):
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    gap = 6
    cw = (W - gap) // 2
    ch = (H - gap) // 2
    positions = [(0, 0), (cw + gap, 0), (0, ch + gap), (cw + gap, ch + gap)]
    for i, pos in enumerate(positions):
        if i < len(images):
            try:
                img = Image.open(images[i]).convert("RGB")
                img = fit_image(img, cw, ch)
                canvas.paste(img, pos)
            except Exception as e:
                print(f"  Warning: Could not load {images[i]}: {e}")
    draw = ImageDraw.Draw(canvas)
    font = load_font(68)
    total_h = len(text_lines) * 85
    start_y = (H - total_h) // 2
    for line in text_lines:
        centered_text(draw, start_y, line, font)
        start_y += 85
    return canvas


def make_product_collage():
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    font_h = load_font(72)
    font_sub = load_font(36)
    font_cta = load_font(68)
    font_warn = load_font(34)

    # Header
    centered_text(draw, 30, "ARCHIVE SALE", font_h, fill=(0, 0, 0), outline=(255, 255, 255))
    for i, line in enumerate(["UP TO 88% OFF + FREE WORLDWIDE", "SHIPPING + FREE GIFTS"]):
        centered_text(draw, 115 + i * 44, line, font_sub, fill=(0, 0, 0), outline=(255, 255, 255))

    # Products
    tops = ["checkered-zipper-gray.png", "checkered-zipper-black.png",
            "zip-hoodie-y2k-dark-green.png", "zip-hoodie-y2k-pink.png", "zip-hoodie-y2k-black.png"]
    bottoms = ["embroidered-striped-jeans.png", "graphic-lining-jeans.png"]
    shoes = ["fur-graphic-sneakers.webp", "ocean-stars-sneaker.jpg"]

    def paste_product(name, x, y, sz, rot=0):
        try:
            p = Image.open(PRODUCT_REFS / name).convert("RGBA")
            p.thumbnail((sz, sz), Image.LANCZOS)
            if rot:
                p = p.rotate(rot, expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))
            canvas.paste(p, (x - p.width // 2, y - p.height // 2), p)
        except:
            pass

    # Top section - hoodies layered
    top_positions = [(130, 520, 520, -12), (950, 540, 480, 10),
                     (320, 500, 560, 5), (580, 480, 580, -3), (800, 510, 540, -6)]
    for i, name in enumerate(tops):
        if i < len(top_positions):
            px, py, sz, rot = top_positions[i]
            paste_product(name, px, py, sz, rot)

    # Middle CTA
    centered_text(draw, 800, "NEWGRMTNS GOT YOU!", font_cta, fill=(255, 220, 0), outline=(0, 0, 0))

    # Bottom - jeans
    for i, name in enumerate(bottoms):
        px, py, sz, rot = [(280, 1220, 620, -4), (800, 1220, 620, 4)][i]
        paste_product(name, px, py, sz, rot)

    # Shoes
    for i, name in enumerate(shoes):
        px, py, sz, rot = [(540, 1480, 400, 0), (160, 1450, 300, -8)][i]
        paste_product(name, px, py, sz, rot)

    # Warning text
    centered_text(draw, H - 100, "Website closes when stock is gone", font_warn,
                  fill=(200, 160, 0), outline=(255, 255, 255))
    return canvas


# ============================================================
# BUILD THE CAROUSEL
# ============================================================

# Best remakes for each slide:
# Slide 1 (single): remake_5 (black Y2K, great mirror selfie with graffiti text)
# Slide 2 (single): remake_2 (green Y2K, mirror selfie with hand sign)
# Slide 3 (grid): remake_3, remake_7, remake_4, remake_8 (best variety)

print("Building 'Can't wait to...' carousel...")

# Slide 1: "Can't wait to drink..."
slide1 = make_single_photo_slide(
    BOARD_REMAKES / "remake_5.png",
    ["Can't wait to drink..."],
    text_pos="center"
)
slide1.save(OUTPUT / "slide1.png", quality=95)
print("  Slide 1 saved")

# Slide 2: "Can't wait to party..."
slide2 = make_single_photo_slide(
    BOARD_REMAKES / "remake_2.png",
    ["Can't wait to party..."],
    text_pos="center"
)
slide2.save(OUTPUT / "slide2.png", quality=95)
print("  Slide 2 saved")

# Slide 3: "Can't wait to get fly this weekend?"
slide3 = make_grid_slide(
    [BOARD_REMAKES / "remake_3.png",   # black checkered
     BOARD_REMAKES / "remake_7.png",   # green Y2K
     BOARD_REMAKES / "remake_4.png",   # pink Y2K
     BOARD_REMAKES / "remake_8.png"],  # gray checkered street
    ["Can't wait to get fly", "this weekend?"]
)
slide3.save(OUTPUT / "slide3.png", quality=95)
print("  Slide 3 saved")

# Slide 4: Product collage
slide4 = make_product_collage()
slide4.save(OUTPUT / "slide4.png", quality=95)
print("  Slide 4 saved")

print(f"\nAll 4 slides saved to: {OUTPUT}")
