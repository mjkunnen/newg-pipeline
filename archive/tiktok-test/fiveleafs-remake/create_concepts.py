"""
Generate 4 carousel concept previews based on competitor research.
Each concept shows all slides side-by-side as a horizontal strip for easy comparison.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

BASE = Path(__file__).parent
OUTPUT = BASE / "concepts"
OUTPUT.mkdir(exist_ok=True)

REMAKES = BASE / "remakes"
PRODUCT_REFS = Path(__file__).parent.parent.parent / "content-library" / "product-refs"

W, H = 1080, 1920  # TikTok slide size

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


def make_grid_slide(images, text, bg=(0,0,0)):
    """2x2 grid with text overlay."""
    canvas = Image.new("RGB", (W, H), bg)
    gap = 6
    cw = (W - gap) // 2
    ch = (H - gap) // 2
    positions = [(0,0), (cw+gap,0), (0,ch+gap), (cw+gap,ch+gap)]
    for i, pos in enumerate(positions):
        if i < len(images):
            try:
                img = Image.open(images[i]).convert("RGB")
                img = fit_image(img, cw, ch)
                canvas.paste(img, pos)
            except:
                pass
    draw = ImageDraw.Draw(canvas)
    font = load_font(72)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    tx = (W - tw) // 2
    ty = (H - bbox[3] + bbox[1]) // 2
    draw_text_outline(draw, (tx, ty), text, font)
    return canvas


def make_single_photo_slide(image_path, text_lines, text_pos="center"):
    """Single full photo with text overlay."""
    canvas = Image.new("RGB", (W, H), (0,0,0))
    try:
        img = Image.open(image_path).convert("RGB")
        img = fit_image(img, W, H)
        canvas.paste(img, (0, 0))
    except:
        pass
    draw = ImageDraw.Draw(canvas)
    font = load_font(64)
    if text_pos == "center":
        total_h = len(text_lines) * 78
        start_y = (H - total_h) // 2
    elif text_pos == "bottom":
        start_y = H - len(text_lines) * 78 - 200
    else:
        start_y = 150
    for line in text_lines:
        centered_text(draw, start_y, line, font)
        start_y += 78
    return canvas


def make_product_collage():
    """Product collage in NEWGARMENTS style."""
    canvas = Image.new("RGB", (W, H), (255,255,255))
    draw = ImageDraw.Draw(canvas)

    font_h = load_font(72)
    font_sub = load_font(36)
    font_cta = load_font(68)
    font_warn = load_font(34)

    # Header
    centered_text(draw, 30, "ARCHIVE SALE", font_h, fill=(0,0,0), outline=(255,255,255))
    for i, line in enumerate(["UP TO 88% OFF + FREE WORLDWIDE", "SHIPPING + FREE GIFTS"]):
        centered_text(draw, 115 + i*44, line, font_sub, fill=(0,0,0), outline=(255,255,255))

    # Products
    tops = ["checkered-zipper-gray.png", "checkered-zipper-black.png", "zip-hoodie-y2k-dark-green.png", "zip-hoodie-y2k-pink.png", "zip-hoodie-y2k-black.png"]
    bottoms = ["embroidered-striped-jeans.png", "graphic-lining-jeans.png"]
    shoes = ["fur-graphic-sneakers.webp", "ocean-stars-sneaker.jpg"]

    positions_tops = [(130,520,520,-12),(950,540,480,10),(320,500,560,5),(580,480,580,-3),(800,510,540,-6)]
    for i, name in enumerate(tops):
        if i < len(positions_tops):
            px, py, sz, rot = positions_tops[i]
            try:
                p = Image.open(PRODUCT_REFS / name).convert("RGBA")
                p.thumbnail((sz, sz), Image.LANCZOS)
                if rot:
                    p = p.rotate(rot, expand=True, resample=Image.BICUBIC, fillcolor=(0,0,0,0))
                canvas.paste(p, (px - p.width//2, py - p.height//2), p)
            except:
                pass

    centered_text(draw, 800, "NEWGRMTNS GOT YOU!", font_cta, fill=(255,220,0), outline=(0,0,0))

    for i, name in enumerate(bottoms):
        px, py, sz, rot = [(280,1220,620,-4),(800,1220,620,4)][i]
        try:
            p = Image.open(PRODUCT_REFS / name).convert("RGBA")
            p.thumbnail((sz, sz), Image.LANCZOS)
            if rot:
                p = p.rotate(rot, expand=True, resample=Image.BICUBIC, fillcolor=(0,0,0,0))
            canvas.paste(p, (px - p.width//2, py - p.height//2), p)
        except:
            pass

    for i, name in enumerate(shoes):
        px, py, sz, rot = [(540,1480,400,0),(160,1450,300,-8)][i]
        try:
            p = Image.open(PRODUCT_REFS / name).convert("RGBA")
            p.thumbnail((sz, sz), Image.LANCZOS)
            if rot:
                p = p.rotate(rot, expand=True, resample=Image.BICUBIC, fillcolor=(0,0,0,0))
            canvas.paste(p, (px - p.width//2, py - p.height//2), p)
        except:
            pass

    centered_text(draw, H-100, "Website closes when stock is gone", font_warn, fill=(200,160,0), outline=(255,255,255))
    return canvas


def make_product_flatlay(product_names, title_text):
    """Clean product flatlay on white bg with title."""
    canvas = Image.new("RGB", (W, H), (255,255,255))
    draw = ImageDraw.Draw(canvas)
    font_title = load_font(56)
    centered_text(draw, 60, title_text, font_title, fill=(0,0,0), outline=(255,255,255))

    cols = 3
    rows = (len(product_names) + cols - 1) // cols
    img_sz = 300
    gap_x = (W - cols * img_sz) // (cols + 1)
    gap_y = 40
    start_y = 160

    for i, name in enumerate(product_names):
        r = i // cols
        c = i % cols
        x = gap_x + c * (img_sz + gap_x)
        y = start_y + r * (img_sz + gap_y)
        try:
            p = Image.open(PRODUCT_REFS / name).convert("RGBA")
            p.thumbnail((img_sz, img_sz), Image.LANCZOS)
            px = x + (img_sz - p.width) // 2
            py = y + (img_sz - p.height) // 2
            canvas.paste(p, (px, py), p)
        except:
            pass

    # Bottom branding
    font_brand = load_font(48)
    centered_text(draw, H - 150, "NEWGARMENTS", font_brand, fill=(30,30,30), outline=(255,255,255))
    font_tag = load_font(28)
    centered_text(draw, H - 90, "not made for everyone.", font_tag, fill=(120,120,120), outline=(255,255,255))
    return canvas


def save_concept_strip(slides, name, concept_title):
    """Save individual slides + a horizontal preview strip."""
    # Save individual slides
    for i, slide in enumerate(slides):
        slide.save(OUTPUT / f"{name}_slide{i+1}.png", quality=95)

    # Create preview strip
    thumb_w = 360
    thumb_h = 640
    gap = 20
    strip_w = len(slides) * thumb_w + (len(slides) - 1) * gap + 40
    strip_h = thumb_h + 120

    strip = Image.new("RGB", (strip_w, strip_h), (30, 30, 30))
    draw = ImageDraw.Draw(strip)

    # Title
    font_t = load_font(32)
    draw.text((20, 15), concept_title, font=font_t, fill=(255,255,255))

    # Slide labels
    font_label = load_font(20)
    for i, slide in enumerate(slides):
        x = 20 + i * (thumb_w + gap)
        y = 60
        thumb = slide.resize((thumb_w, thumb_h), Image.LANCZOS)
        strip.paste(thumb, (x, y))
        # Slide number
        draw.text((x + 5, y + 5), f"Slide {i+1}", font=font_label, fill=(255,255,0))

    strip.save(OUTPUT / f"{name}_preview.png", quality=95)
    print(f"Saved concept: {name} ({len(slides)} slides)")


# ============================================================
# CONCEPT 1: "Can't wait to..." storytelling (bewezen 6.6M views)
# ============================================================
remakes = sorted(REMAKES.glob("remake_pin*.png"))
c1_slides = []

# Slide 1: Single photo + hook text
c1_slides.append(make_single_photo_slide(
    remakes[0] if remakes else REMAKES / "remake_1_1.png",
    ["Can't wait to drink..."],
    text_pos="center"
))

# Slide 2: Same style + text progression
c1_slides.append(make_single_photo_slide(
    remakes[1] if len(remakes) > 1 else REMAKES / "remake_1_2.png",
    ["Can't wait to party..."],
    text_pos="center"
))

# Slide 3: 2x2 grid + "Can't wait to get fly?"
grid_imgs = [remakes[i] if i < len(remakes) else REMAKES / "remake_1_1.png" for i in range(2, 6)]
c1_slides.append(make_grid_slide(
    grid_imgs,
    "Can't wait to get fly\nthis weekend?"
))

# Slide 4: Product collage
c1_slides.append(make_product_collage())

save_concept_strip(c1_slides, "concept1_storytelling",
    "CONCEPT 1: \"Can't wait to...\" Storytelling (Five Leafs #2 format — 6.6M views)")


# ============================================================
# CONCEPT 2: "These fits >>" Product-first (bewezen 23.2M views)
# ============================================================
c2_slides = []

# Slide 1: Clean product flatlay - hoodies
c2_slides.append(make_product_flatlay(
    ["checkered-zipper-gray.png", "checkered-zipper-black.png", "checkered-zipper-red.png",
     "zip-hoodie-y2k-dark-green.png", "zip-hoodie-y2k-black.png", "zip-hoodie-y2k-pink.png"],
    "These hoodies >>"
))

# Slide 2: Clean product flatlay - jeans + shoes
c2_slides.append(make_product_flatlay(
    ["embroidered-striped-jeans.png", "graphic-lining-jeans.png",
     "fur-graphic-sneakers.webp", "ocean-stars-sneaker.jpg"],
    "Complete the fit >>"
))

# Slide 3: Outfit grid showing combinations
c2_slides.append(make_grid_slide(
    [remakes[i] if i < len(remakes) else REMAKES / "remake_1_1.png" for i in [0, 3, 5, 7]],
    "On body >>"
))

# Slide 4: Archive sale collage
c2_slides.append(make_product_collage())

save_concept_strip(c2_slides, "concept2_product_first",
    "CONCEPT 2: \"These fits >>\" Product-First (Five Leafs #1 format — 23.2M views)")


# ============================================================
# CONCEPT 3: "You want this style?" Aspiratie format (huidige + verbeterd)
# ============================================================
c3_slides = []

# Slide 1: Single aspirational photo + hook
c3_slides.append(make_single_photo_slide(
    remakes[2] if len(remakes) > 2 else REMAKES / "remake_2_3.png",
    ["I know you want", "this style..."],
    text_pos="bottom"
))

# Slide 2: Grid + "But it's too expensive?"
c3_slides.append(make_grid_slide(
    [remakes[i] if i < len(remakes) else REMAKES / "remake_1_1.png" for i in [0, 4, 6, 7]],
    "But it's too expensive?"
))

# Slide 3: Grid + "Don't worry"
c3_slides.append(make_grid_slide(
    [remakes[i] if i < len(remakes) else REMAKES / "remake_1_2.png" for i in [1, 3, 5, 2]],
    "Don't worry, we got you!"
))

# Slide 4: Product collage
c3_slides.append(make_product_collage())

save_concept_strip(c3_slides, "concept3_aspiration",
    "CONCEPT 3: \"I know you want this style\" Aspiratie Format (verbeterd 4-slide)")


# ============================================================
# CONCEPT 4: "How I want to dress" Mood format
# ============================================================
c4_slides = []

# Slide 1: Single moody photo + text
c4_slides.append(make_single_photo_slide(
    remakes[6] if len(remakes) > 6 else REMAKES / "remake_2_4.png",
    ["How I want to dress", "every single day..."],
    text_pos="center"
))

# Slide 2: Another photo + "Clean fits inspo"
c4_slides.append(make_single_photo_slide(
    remakes[4] if len(remakes) > 4 else REMAKES / "remake_1_1.png",
    ["Clean fits inspo"],
    text_pos="bottom"
))

# Slide 3: Grid of all fits
c4_slides.append(make_grid_slide(
    [remakes[i] if i < len(remakes) else REMAKES / "remake_1_1.png" for i in [0, 2, 5, 7]],
    "All from one brand..."
))

# Slide 4: Product collage with sale
c4_slides.append(make_product_collage())

save_concept_strip(c4_slides, "concept4_mood",
    "CONCEPT 4: \"How I want to dress\" Mood Format (trending hook)")


print(f"\nAll concepts saved to: {OUTPUT}")
print("Preview strips show all slides side-by-side for easy comparison.")
