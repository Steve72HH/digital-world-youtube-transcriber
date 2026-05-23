from pathlib import Path
from PIL import Image


base = Path(__file__).resolve().parent
logo = base / "assets" / "logo.png"
icon = base / "assets" / "logo.ico"

image = Image.open(logo).convert("RGBA")
image.save(icon, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(icon)
