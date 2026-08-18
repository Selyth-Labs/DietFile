import json
import mimetypes
import subprocess
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_VIDEO_FORMATS = {"MP4", "MOV", "MKV", "WEBM", "AVI"}

@dataclass(frozen=True)
class VideoInfo:
    path: Path
    filename: str
    extension: str
    mime_type: str
    format_name: str
    size_bytes: int
    width: int
    height: int
    duration: float
    fps: float | None
    video_codec: str | None
    video_bitrate: int | None
    audio_codec: str | None
    audio_bitrate: int | None

class VideoAnalyzer:
    def analyze(self, path: str | Path) -> VideoInfo:
        video_path = Path(path)
        self._validate_path(video_path)
        format_name, streams, format_info = self._probe(video_path)
        self._validate_format(format_name)
        video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
        audio_stream = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
        if video_stream is None: raise ValueError("비디오 스트림을 찾을 수 없습니다.")
        return VideoInfo(path=video_path, filename=video_path.name, extension=video_path.suffix.lower(), mime_type=self._get_mime_type(video_path), format_name=format_name, size_bytes=video_path.stat().st_size, width=int(video_stream.get("width") or 0), height=int(video_stream.get("height") or 0), duration=self._parse_float(video_stream.get("duration") or format_info.get("duration")), fps=self._parse_fps(video_stream.get("r_frame_rate")), video_codec=video_stream.get("codec_name"), video_bitrate=self._parse_int(video_stream.get("bit_rate")), audio_codec=audio_stream.get("codec_name") if audio_stream else None, audio_bitrate=self._parse_int(audio_stream.get("bit_rate")) if audio_stream else None)

    @staticmethod
    def _validate_path(video_path: Path) -> None:
        if not video_path.is_file(): raise ValueError("비디오 파일을 찾을 수 없습니다.")

    @staticmethod
    def _validate_format(format_name: str) -> None:
        if format_name not in SUPPORTED_VIDEO_FORMATS: raise ValueError("지원하지 않는 비디오 형식입니다. MP4, MOV, MKV, WebM 또는 AVI를 선택해 주세요.")

    @staticmethod
    def _get_mime_type(video_path: Path) -> str:
        return mimetypes.guess_type(video_path.name)[0] or f"video/{video_path.suffix.lstrip('.').lower()}"

    @staticmethod
    def _probe(path: Path) -> tuple[str, list[dict], dict]:
        try:
            process = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], capture_output=True, text=True, check=True)
        except FileNotFoundError as exc:
            raise RuntimeError("ffprobe를 찾을 수 없습니다. FFmpeg를 설치해 주세요.") from exc
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or "비디오 정보를 분석할 수 없습니다."
            raise RuntimeError(message) from exc

        try:
            data = json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("ffprobe의 분석 결과를 읽을 수 없습니다.") from exc

        format_info = data.get("format", {})
        format_name = str(format_info.get("format_name", "")).split(",")[0].upper()
        return format_name, data.get("streams", []), format_info

    @staticmethod
    def _parse_int(value) -> int | None:
        try: return int(float(value)) if value is not None else None
        except (TypeError, ValueError): return None

    @staticmethod
    def _parse_float(value) -> float:
        try: return float(value)
        except (TypeError, ValueError): return 0.0

    @staticmethod
    def _parse_fps(value) -> float | None:
        if not value or value in {"0/0", "N/A"}: return None
        try:
            numerator, denominator = value.split("/", 1)
            if float(denominator) == 0: return None
            return float(numerator) / float(denominator)
        except (TypeError, ValueError, ZeroDivisionError): return None