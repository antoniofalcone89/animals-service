"""Generate placeholder images for all animals."""

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Rarity level color palette (level -> (bg_color, accent_color))
LEVEL_COLORS = {
    1:  ("#4CAF50", "#388E3C"),   # Green - very common
    2:  ("#66BB6A", "#43A047"),
    3:  ("#29B6F6", "#0288D1"),   # Blue - common
    4:  ("#42A5F5", "#1565C0"),
    5:  ("#AB47BC", "#7B1FA2"),   # Purple - moderate
    6:  ("#7E57C2", "#4527A0"),
    7:  ("#FF7043", "#D84315"),   # Orange - rare
    8:  ("#EF5350", "#C62828"),   # Red - rare
    9:  ("#FFD740", "#F9A825"),   # Gold - very rare
    10: ("#FFD700", "#FF6F00"),   # Bright gold - legendary
}

EMOJI_MAP = {
    "Dog": "🐕", "Cat": "🐈", "Chicken": "🐔", "Cow": "🐄", "Sheep": "🐑",
    "Pig": "🐖", "Horse": "🐎", "Goat": "🐐", "Duck": "🦆", "Pigeon": "🐦",
    "Sparrow": "🐦", "Rat": "🐀", "Fox": "🦊", "Deer": "🦌", "Rabbit": "🐇",
    "Squirrel": "🐿️", "Raccoon": "🦝", "Hedgehog": "🦔", "Badger": "🦡",
    "Coyote": "🐺", "Eagle": "🦅", "Owl": "🦉", "Beaver": "🦫",
    "Flamingo": "🦩", "Red Panda": "🐾", "Koala": "🐨", "Penguin": "🐧",
    "Otter": "🦦", "Sloth": "🦥", "Chameleon": "🦎", "Porcupine": "🦔",
    "Toucan": "🐦", "Capybara": "🐾", "Manta Ray": "🐟", "Platypus": "🐾",
    "Seahorse": "🐟", "Armadillo": "🐾", "Wolf": "🐺", "Snow Leopard": "🐆",
    "Pangolin": "🐾", "Axolotl": "🐾", "Narwhal": "🐋", "Okapi": "🐾",
    "Clouded Leopard": "🐆", "Quokka": "🐾", "Cassowary": "🐦",
    "Gharial": "🐊", "Saola": "🐾", "Fossa": "🐾", "Aye-Aye": "🐒",
    "Numbat": "🐾", "Dugong": "🐋", "Kakapo": "🦜", "Vaquita": "🐬",
    "Javan Rhino": "🦏", "Philippine Eagle": "🦅", "Amur Leopard": "🐆",
    "Sumatran Orangutan": "🦧", "Red Wolf": "🐺",
    "Yangtze Finless Porpoise": "🐬", "Northern Hairy-Nosed Wombat": "🐾",
    "Cross River Gorilla": "🦍", "Hainan Gibbon": "🐒",
}

WIDTH, HEIGHT = 400, 400


def draw_star(draw, cx, cy, outer_r, inner_r, points, fill):
    """Draw a star shape."""
    coords = []
    for i in range(points * 2):
        angle = math.pi / 2 + i * math.pi / points
        r = outer_r if i % 2 == 0 else inner_r
        coords.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
    draw.polygon(coords, fill=fill)


def generate_image(animal: dict, output_dir: Path):
    """Generate a single animal placeholder image."""
    level = animal["level"]
    name = animal["name"]
    bg, accent = LEVEL_COLORS[level]

    img = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(img)

    # Draw decorative circle
    draw.ellipse([100, 50, 300, 250], fill=accent)

    # Draw emoji in center
    emoji = EMOJI_MAP.get(name, "🐾")
    try:
        emoji_font = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", 80)
        bbox = draw.textbbox((0, 0), emoji, font=emoji_font)
        ew = bbox[2] - bbox[0]
        eh = bbox[3] - bbox[1]
        draw.text(((WIDTH - ew) / 2, 100 - eh / 2 + 20), emoji, font=emoji_font, embedded_color=True)
    except Exception:
        # Fallback: draw a simple shape instead
        draw.ellipse([160, 100, 240, 180], fill="white")

    # Draw animal name
    try:
        name_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
    except Exception:
        name_font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), name, font=name_font)
    tw = bbox[2] - bbox[0]
    draw.text(((WIDTH - tw) / 2, 275), name, fill="white", font=name_font)

    # Draw rarity label
    rarity_labels = {
        1: "Common", 2: "Common", 3: "Uncommon", 4: "Uncommon",
        5: "Moderate", 6: "Moderate", 7: "Rare", 8: "Rare",
        9: "Very Rare", 10: "Legendary",
    }
    label = f"★ {rarity_labels[level]} (Lv.{level})"
    try:
        label_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    except Exception:
        label_font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label, font=label_font)
    lw = bbox[2] - bbox[0]
    draw.text(((WIDTH - lw) / 2, 315), label, fill="#FFFFFFCC", font=label_font)

    # Draw stars for level 9-10
    if level >= 9:
        for i in range(3):
            sx = 140 + i * 60
            draw_star(draw, sx, 365, 12, 5, 5, "#FFD700")

    # Build filename from image_url in data
    url = animal["image_url"]
    filename = url.split("/")[-1]
    img.save(output_dir / filename, "JPEG", quality=90)


def main():
    data_file = Path(__file__).parent / "data" / "animals.json"
    output_dir = Path(__file__).parent / "static" / "images"
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(data_file) as f:
        animals = json.load(f)

    for animal in animals:
        generate_image(animal, output_dir)
        print(f"  ✓ {animal['name']}")

    print(f"\nGenerated {len(animals)} images in {output_dir}")


if __name__ == "__main__":
    main()
