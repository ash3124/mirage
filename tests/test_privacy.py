from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile
import unittest

import imagehash
from PIL import Image

from app.errors import ApiError
from app.schemas import ErrorCode, MetadataReport
from app.services.privacy import process_image


def make_jpeg(
    size: tuple[int, int] = (40, 24),
    *,
    orientation: int | None = None,
    include_metadata: bool = False,
    include_gps: bool = False,
) -> bytes:
    image = Image.new("RGB", size, color=(70, 120, 180))
    exif = Image.Exif()
    if orientation is not None:
        exif[274] = orientation
    if include_metadata:
        exif[271] = "Mirage Camera"
        exif[272] = "Model X"
        exif[306] = "2026:10:25 09:00:00"
        exif[305] = "Editor"
        exif[315] = "Photographer"
        exif[33432] = "Copyright"
    if include_gps:
        exif[34853] = {1: "N", 2: (51.0, 0.0, 0.0)}

    output = BytesIO()
    image.save(output, format="JPEG", exif=exif)
    return output.getvalue()


class PrivacyTests(unittest.TestCase):
    def test_process_image_orients_resizes_strips_metadata_and_hashes_working_png(
        self,
    ) -> None:
        source_bytes = make_jpeg(
            orientation=6,
            include_metadata=True,
            include_gps=True,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "original.png"
            processed = process_image(source_bytes, output_path, max_side_px=32)

            self.assertEqual((processed.width, processed.height), (16, 32))
            self.assertTrue(output_path.is_file())
            with Image.open(output_path) as working:
                self.assertEqual(working.format, "PNG")
                self.assertEqual(working.size, (16, 32))
                self.assertEqual(len(working.getexif()), 0)
                expected_hash = str(imagehash.phash(working.convert("RGB")))

            self.assertEqual(processed.phash_original, expected_hash)
            self.assertEqual(processed.phash_original, processed.phash_original.lower())
            self.assertEqual(
                processed.metadata_report,
                MetadataReport(
                    had_gps=True,
                    removed=[
                        "GPS location",
                        "Camera model",
                        "Capture date",
                        "Editing software",
                        "Creator/copyright",
                    ],
                ),
            )

    def test_process_image_limits_longest_side_and_rounds_dimensions_down(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            processed = process_image(
                make_jpeg((101, 65)),
                Path(temp_dir) / "original.png",
                max_side_px=64,
            )

        self.assertEqual((processed.width, processed.height), (64, 40))
        self.assertLessEqual(max(processed.width, processed.height), 64)
        self.assertEqual(processed.width % 8, 0)
        self.assertEqual(processed.height % 8, 0)

    def test_process_image_rejects_invalid_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ApiError) as context:
                process_image(b"not an image", Path(temp_dir) / "original.png", 512)
        self.assertEqual(context.exception.code, ErrorCode.INVALID_IMAGE)

    def test_process_image_rejects_upload_over_ten_megabytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ApiError) as context:
                process_image(
                    b"x" * (10 * 1024 * 1024 + 1),
                    Path(temp_dir) / "original.png",
                    512,
                )
        self.assertEqual(context.exception.code, ErrorCode.TOO_LARGE)

    def test_process_image_rejects_dimensions_that_cannot_form_valid_working_size(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ApiError) as context:
                process_image(
                    make_jpeg((7, 32)),
                    Path(temp_dir) / "original.png",
                    512,
                )
        self.assertEqual(context.exception.code, ErrorCode.INVALID_IMAGE)

    def test_process_image_requires_positive_max_side(self) -> None:
        with self.assertRaises(ValueError):
            process_image(make_jpeg(), Path("unused.png"), max_side_px=0)


if __name__ == "__main__":
    unittest.main()
