"""Add a soft glow around bright, saturated areas of a render (for the night sign)."""
import sys
from PIL import Image, ImageChops, ImageFilter

src, dst = sys.argv[1], sys.argv[2]
img = Image.open(src).convert('RGB')
bright = img.point(lambda v: 0 if v < 170 else int((v - 170) * 255 / 85))
glow = bright.filter(ImageFilter.GaussianBlur(28))
glow2 = bright.filter(ImageFilter.GaussianBlur(8))
out = ImageChops.add(img, ImageChops.multiply(glow, Image.new('RGB', img.size, (210, 210, 210))))
out = ImageChops.add(out, ImageChops.multiply(glow2, Image.new('RGB', img.size, (110, 110, 110))))
out.save(dst)
print('bloom ->', dst)
