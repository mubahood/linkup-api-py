"""
Tests for backend/shared/storage/image_compress.py.
"""
import io
import unittest

from backend.shared.storage.image_compress import compress_image, MAX_DIMENSION


def _photo_like_jpeg(width, height, quality=95):
    """A large, high-entropy JPEG — real photos compress far better than
    noise, but noise gives a size-heavy baseline that still shrinks
    meaningfully once resized, which is what these tests actually check."""
    from PIL import Image
    import random
    rng = random.Random(42)
    img = Image.new('RGB', (width, height))
    # A smooth gradient plus a little noise mimics a real photo far better
    # than pure random noise (which resists compression almost entirely).
    pixels = img.load()
    for x in range(0, width, 4):
        for y in range(0, height, 4):
            r = (x * 255) // width
            g = (y * 255) // height
            b = 128 + rng.randint(-20, 20)
            for dx in range(4):
                for dy in range(4):
                    if x + dx < width and y + dy < height:
                        pixels[x + dx, y + dy] = (r, g, b)
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=quality)
    return buf.getvalue()


class CompressImageTests(unittest.TestCase):
    def test_rejects_non_image_bytes(self):
        with self.assertRaises(ValueError):
            compress_image(b'this is not an image, just text pretending to be one')

    def test_rejects_empty_bytes(self):
        with self.assertRaises(ValueError):
            compress_image(b'')

    def test_returns_webp_and_shrinks_a_large_photo(self):
        original = _photo_like_jpeg(3000, 2000)
        compressed, ext = compress_image(original)
        self.assertEqual(ext, 'webp')
        self.assertLess(len(compressed), len(original))

        from PIL import Image
        out = Image.open(io.BytesIO(compressed))
        self.assertEqual(out.format, 'WEBP')

    def test_caps_resolution_at_max_dimension(self):
        original = _photo_like_jpeg(4000, 3000)
        compressed, _ext = compress_image(original)

        from PIL import Image
        out = Image.open(io.BytesIO(compressed))
        self.assertLessEqual(max(out.size), MAX_DIMENSION)
        # aspect ratio preserved (4000:3000 == 4:3)
        self.assertAlmostEqual(out.size[0] / out.size[1], 4000 / 3000, places=2)

    def test_leaves_small_image_dimensions_untouched(self):
        original = _photo_like_jpeg(400, 300)
        compressed, _ext = compress_image(original)

        from PIL import Image
        out = Image.open(io.BytesIO(compressed))
        self.assertEqual(out.size, (400, 300))

    def test_applies_exif_orientation(self):
        from PIL import Image
        img = Image.new('RGB', (600, 400), color=(200, 100, 50))
        buf = io.BytesIO()
        exif = img.getexif()
        exif[0x0112] = 6  # "rotate 90 CW" orientation tag
        img.save(buf, 'JPEG', exif=exif)
        original = buf.getvalue()

        compressed, _ext = compress_image(original)
        out = Image.open(io.BytesIO(compressed))
        # A 90-degree rotation swaps width and height.
        self.assertEqual(out.size, (400, 600))

    def test_converts_palette_mode_image(self):
        from PIL import Image
        img = Image.new('P', (200, 150))
        img.putpalette([i % 256 for i in range(768)])
        buf = io.BytesIO()
        img.save(buf, 'PNG')
        original = buf.getvalue()

        compressed, ext = compress_image(original)
        out = Image.open(io.BytesIO(compressed))
        self.assertIn(out.mode, ('RGB', 'RGBA'))

    def test_preserves_alpha_channel(self):
        from PIL import Image
        img = Image.new('RGBA', (200, 150), (255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, 'PNG')
        original = buf.getvalue()

        compressed, ext = compress_image(original)
        out = Image.open(io.BytesIO(compressed)).convert('RGBA')
        self.assertEqual(out.getpixel((0, 0))[3], 128)

    def test_never_returns_something_bigger_than_the_input(self):
        from PIL import Image
        img = Image.new('RGB', (1, 1), color=(10, 20, 30))
        buf = io.BytesIO()
        img.save(buf, 'JPEG')
        original = buf.getvalue()

        compressed, _ext = compress_image(original)
        self.assertLessEqual(len(compressed), len(original))


if __name__ == '__main__':
    unittest.main()
