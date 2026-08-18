import mimetypes
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageOps

SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
CHANNELS_BY_MODE = {"1": 1, "L": 1, "LA": 2, "RGB": 3, "RGBA": 4, "CMYK": 4}
SIXTEEN_BIT_MODES = {"I;16", "I;16L", "I;16B", "I;16N"}

@dataclass(frozen=True)
class ImageInfo:
    path: Path
    filename: str
    extension: str
    mime_type: str
    format_name: str
    size_bytes: int
    width: int
    height: int
    mode: str
    channels: int | None
    bits: int | None
    is_animated: bool
    frame_count: int
    duration: float | None

class ImageAnalyzer:
    def analyze(self, path: str | Path) -> ImageInfo:
        image_path = Path(path)

        with Image.open(image_path) as image:
            format_name = (image.format or "").upper()
            self._validate_format(format_name)

            is_animated = getattr(image, "is_animated", False)
            frame_count = getattr(image, "n_frames", 1)

            return ImageInfo(
                path=image_path,
                filename=image_path.name,
                extension=image_path.suffix.lower(),
                mime_type=self._get_mime_type(image_path, format_name),
                format_name=format_name,
                size_bytes=image_path.stat().st_size,
                width=image.width,
                height=image.height,
                mode=image.mode,
                channels=CHANNELS_BY_MODE.get(image.mode),
                bits=self._bits_per_channel(image),
                is_animated=is_animated,
                frame_count=frame_count,
                duration=self._get_duration(image) if is_animated else None,
            )

    def load_normalized(self, path: str | Path) -> Image.Image:
        with Image.open(path) as image:
            image.load()
            return ImageOps.exif_transpose(image).copy()

    @staticmethod
    def _validate_format(format_name: str) -> None:
        if format_name not in SUPPORTED_FORMATS:
            raise ValueError("지원하지 않는 이미지 형식입니다. JPEG/JPG, PNG, WebP 또는 GIF를 선택해 주세요.")

    @staticmethod
    def _get_mime_type(image_path: Path, format_name: str) -> str:
        return mimetypes.guess_type(image_path.name)[0] or f"image/{format_name.lower()}"

    @staticmethod
    def _get_duration(image: Image.Image) -> float | None:
        duration = image.info.get("duration")
        if duration is None:
            return None

        try:
            return float(duration) * image.n_frames / 1000
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _bits_per_channel(image: Image.Image) -> int | None:
        if image.mode in SIXTEEN_BIT_MODES:
            return 16
        if image.mode == "F":
            return 32
        return 8