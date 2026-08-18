import io
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from PIL import Image
from core.image_analyzer import ImageAnalyzer, ImageInfo
from core.video_analyzer import VideoInfo
from models.optimization_result import OptimizationResult

@dataclass(frozen=True)
class ProgressUpdate:
    percent: int
    message: str

class ImageOptimizer:
    IMAGE_OPTIMIZERS = {"JPEG": "_optimize_jpeg", "PNG": "_optimize_png", "WEBP": "_optimize_webp", "GIF": "_optimize_gif"}
    VIDEO_CONTAINERS = {".mp4": "mp4", ".mov": "mov", ".mkv": "matroska", ".webm": "webm", ".avi": "avi"}
    GIF_COLOR_VALUES = (256, 224, 192, 160, 128, 96, 64, 32)
    PNG_COLOR_VALUES = (256, 192, 128, 96, 64, 48, 32, 24, 16, 12, 8, 4, 2)

    def __init__(self, analyzer: ImageAnalyzer | None = None):
        self.analyzer = analyzer or ImageAnalyzer()

    def optimize(self, info: ImageInfo | VideoInfo, target_bytes: int, progress=None) -> OptimizationResult:
        self._validate_target(info, target_bytes)
        if isinstance(info, VideoInfo): return self._optimize_video(info, target_bytes, progress)
        return self._optimize_image(info, target_bytes, progress)

    def _optimize_image(self, info: ImageInfo, target_bytes: int, progress) -> OptimizationResult:
        image = self.analyzer.load_normalized(info.path)
        self._progress(progress, 8, "이미지 분석 중...")
        optimizer_name = self.IMAGE_OPTIMIZERS.get(info.format_name)
        if optimizer_name is None: raise ValueError("지원하지 않는 이미지 형식입니다.")
        return getattr(self, optimizer_name)(image, info, target_bytes, progress)

    @staticmethod
    def _validate_target(info: ImageInfo | VideoInfo, target_bytes: int):
        if target_bytes <= 0: raise ValueError("목표 용량은 0보다 커야 합니다.")
        if target_bytes >= info.size_bytes: raise ValueError("목표 용량은 현재 파일보다 작아야 합니다.")

    def _optimize_jpeg(self, image: Image.Image, info: ImageInfo, target_bytes: int, progress) -> OptimizationResult:
        return self._optimize_lossy_image(image.convert("RGB"), target_bytes, progress, self._encode_jpeg, "JPEG", ".jpg", "품질 자동 조정", "품질 자동 조정 + 해상도 조정", "최적화 방법 탐색 중...")

    def _optimize_webp(self, image: Image.Image, info: ImageInfo, target_bytes: int, progress) -> OptimizationResult:
        image = image.convert("RGBA" if "A" in image.mode else "RGB")
        return self._optimize_lossy_image(image, target_bytes, progress, self._encode_webp, "WEBP", ".webp", "품질 자동 조정", "품질 자동 조정 + 해상도 조정", "WebP 최적화 방법 탐색 중...")

    def _optimize_lossy_image(self, image: Image.Image, target_bytes: int, progress, encoder, format_name: str, extension: str, quality_method: str, resize_method: str, progress_message: str) -> OptimizationResult:
        self._progress(progress, 20, progress_message)
        candidate = self._find_quality(image, target_bytes, encoder, format_name.title() if format_name == "WEBP" else format_name, progress, 20, 65)
        if candidate:
            quality, data = candidate
            return self._create_result(data, format_name, extension, image.width, image.height, quality_method, quality=quality, progress=progress, message="목표 용량을 만족하는 최적 품질을 찾았습니다.")
        self._progress(progress, 68, "품질 조절만으로 부족해 해상도를 조정합니다...")
        scales = self._generate_scales()
        for index, scale in enumerate(scales):
            percent = self._scale_progress(index, len(scales), 68, 94)
            resized = self._resize(image, scale)
            self._progress(progress, percent, f"해상도 조정 중... {resized.width:,} × {resized.height:,}")
            candidate = self._find_quality(resized, target_bytes, encoder, format_name.title() if format_name == "WEBP" else format_name, progress, percent, min(94, percent + 5))
            if candidate:
                quality, data = candidate
                return self._create_result(data, format_name, extension, resized.width, resized.height, resize_method, quality=quality, progress=progress, message="목표 용량을 만족하는 최적 결과를 찾았습니다.")
        raise ValueError("이미지를 목표 용량까지 줄일 수 없습니다. 목표 용량을 조금 높여 주세요.")

    def _optimize_png(self, image: Image.Image, info: ImageInfo, target_bytes: int, progress) -> OptimizationResult:
        self._progress(progress, 20, "최적화 방법 탐색 중...")
        data = self._encode_png(image)
        if len(data) <= target_bytes: return self._create_result(data, "PNG", ".png", image.width, image.height, "무손실 PNG 최적화", progress=progress, message="무손실 PNG 최적화만으로 목표 용량을 만족했습니다.")
        self._progress(progress, 35, "색상 수를 조정하면서 목표 용량을 탐색 중...")
        candidate = self._find_png_palette(image, target_bytes, progress, 35, 60)
        if candidate:
            colors, data = candidate
            return self._create_result(data, "PNG", ".png", image.width, image.height, "PNG 최적화 + 색상 수 조정", colors=colors, progress=progress, message="목표 용량을 만족하는 최적 색상 수를 찾았습니다.")
        return self._optimize_png_with_resize(image, target_bytes, progress)

    def _optimize_png_with_resize(self, image: Image.Image, target_bytes: int, progress) -> OptimizationResult:
        self._progress(progress, 62, "색상 조절만으로 부족해 해상도를 조정합니다...")
        scales = self._generate_scales(start=0.95, minimum=0.05, factor=0.90)
        for index, scale in enumerate(scales):
            percent = self._scale_progress(index, len(scales), 62, 94)
            resized = self._resize(image, scale)
            self._progress(progress, percent, f"해상도 조정 중... {resized.width:,} × {resized.height:,}")
            candidate = self._find_png_palette(resized, target_bytes, progress, percent, min(94, percent + 4))
            if candidate:
                colors, data = candidate
                return self._create_result(data, "PNG", ".png", resized.width, resized.height, "PNG 최적화 + 색상 수 + 해상도 조정", colors=colors, progress=progress, message="목표 용량을 만족하는 최적 결과를 찾았습니다.")
            data = self._encode_png(resized)
            if len(data) <= target_bytes: return self._create_result(data, "PNG", ".png", resized.width, resized.height, "PNG 최적화 + 해상도 조정", progress=progress, message="목표 용량을 만족하는 최적 결과를 찾았습니다.")
        raise ValueError("이미지를 목표 용량까지 줄일 수 없습니다. 목표 용량을 조금 높여 주세요.")

    def _optimize_gif(self, image: Image.Image, info: ImageInfo, target_bytes: int, progress) -> OptimizationResult:
        self._progress(progress, 20, "GIF 최적화 방법 탐색 중...")
        if info.size_bytes <= target_bytes: return self._create_result(info.path.read_bytes(), "GIF", ".gif", info.width, info.height, "원본 유지", colors=256, progress=progress, message="원본 GIF가 이미 목표 용량 이하입니다.")
        frames, durations, loop = self._load_gif_frames(info.path)
        self._progress(progress, 30, "GIF 전체 프레임을 분석하는 중...")
        for index, colors in enumerate(self.GIF_COLOR_VALUES):
            percent = self._scale_progress(index, len(self.GIF_COLOR_VALUES), 30, 65)
            self._progress(progress, percent, f"GIF 공통 색상 팔레트 생성 중... {colors}색")
            data = self._encode_gif_with_common_palette(frames, durations, loop, colors)
            if len(data) <= target_bytes: return self._create_result(data, "GIF", ".gif", frames[0].width, frames[0].height, "GIF 최적화 + 공통 색상 팔레트", colors=colors, progress=progress, message="목표 용량을 만족하는 최적 GIF를 찾았습니다.")
        return self._optimize_gif_with_resize(frames, durations, loop, target_bytes, progress)

    def _optimize_gif_with_resize(self, frames: list[Image.Image], durations: list[int], loop: int, target_bytes: int, progress) -> OptimizationResult:
        self._progress(progress, 68, "색상 조절만으로 부족해 해상도를 조정합니다...")
        scales = self._generate_scales(start=0.95, minimum=0.10, factor=0.90)
        for index, scale in enumerate(scales):
            percent = self._scale_progress(index, len(scales), 68, 94)
            resized_frames = [self._resize(frame, scale) for frame in frames]
            self._progress(progress, percent, f"GIF 해상도 조정 중... {resized_frames[0].width:,} × {resized_frames[0].height:,}")
            for colors in self.GIF_COLOR_VALUES:
                data = self._encode_gif_with_common_palette(resized_frames, durations, loop, colors)
                if len(data) <= target_bytes: return self._create_result(data, "GIF", ".gif", resized_frames[0].width, resized_frames[0].height, "GIF 최적화 + 공통 색상 팔레트 + 해상도 조정", colors=colors, progress=progress, message="목표 용량을 만족하는 최적 GIF를 찾았습니다.")
        raise ValueError("GIF를 목표 용량까지 줄일 수 없습니다. 목표 용량을 조금 높여 주세요.")

    @staticmethod
    def _load_gif_frames(path: Path) -> tuple[list[Image.Image], list[int], int]:
        frames, durations = [], []
        with Image.open(path) as image:
            loop = int(image.info.get("loop", 0))
            for frame_index in range(getattr(image, "n_frames", 1)):
                image.seek(frame_index)
                frames.append(image.convert("RGBA").copy())
                durations.append(max(20, int(image.info.get("duration", 100))))
        if not frames: raise ValueError("GIF 프레임을 읽을 수 없습니다.")
        return frames, durations, loop

    @staticmethod
    def _build_gif_palette(frames: list[Image.Image], colors: int) -> Image.Image:
        sample_count = min(len(frames), 24)
        step = max(1, len(frames) // sample_count)
        sample_width = 256
        sample_height = max(1, round(frames[0].height * sample_width / frames[0].width))
        samples = []
        for index in range(0, len(frames), step):
            samples.append(frames[index].convert("RGB").resize((sample_width, sample_height), Image.Resampling.BILINEAR))
            if len(samples) >= sample_count: break
        sheet = Image.new("RGB", (sample_width, sample_height * len(samples)))
        for index, sample in enumerate(samples): sheet.paste(sample, (0, index * sample_height))
        return sheet.quantize(colors=max(2, colors), method=Image.Quantize.MEDIANCUT)

    @staticmethod
    def _quantize_gif_frames(frames: list[Image.Image], palette: Image.Image) -> list[Image.Image]:
        result, palette_data = [], palette.getpalette()
        for frame in frames:
            quantized = frame.convert("RGB").quantize(palette=palette, dither=Image.Dither.FLOYDSTEINBERG)
            quantized.putpalette(palette_data)
            result.append(quantized)
        return result

    @classmethod
    def _encode_gif_with_common_palette(cls, frames: list[Image.Image], durations: list[int], loop: int, colors: int) -> bytes:
        quantized_frames = cls._quantize_gif_frames(frames, cls._build_gif_palette(frames, colors))
        buffer = io.BytesIO()
        first, *rest = quantized_frames
        first.save(buffer, format="GIF", save_all=True, append_images=rest, duration=durations, loop=loop, optimize=True)
        return buffer.getvalue()

    def _optimize_video(self, info: VideoInfo, target_bytes: int, progress) -> OptimizationResult:
        self._progress(progress, 10, "비디오 분석 중...")
        self._validate_video_info(info)
        container = self._video_container(info.extension.lower())
        audio_bitrate = self._select_audio_bitrate(info, target_bytes)
        total_bitrate = max(100_000, int((target_bytes * 8 * 0.94) / info.duration))
        video_bitrate = max(50_000, total_bitrate - audio_bitrate)
        self._progress(progress, 35, f"비디오 비트레이트를 {video_bitrate // 1000:,} kbps로 설정했습니다.")
        result_path = self._encode_video(info.path, container, video_bitrate, audio_bitrate, progress, 35, 78)
        actual_size = result_path.stat().st_size
        result_path, actual_size, video_bitrate = self._fit_video_to_target(result_path, actual_size, info, container, video_bitrate, audio_bitrate, target_bytes, progress)
        try:
            data = result_path.read_bytes()
        finally:
            result_path.unlink(missing_ok=True)
        self._progress(progress, 100, "목표 용량을 만족하는 최적 비디오를 찾았습니다.")
        return OptimizationResult(data=data, format_name=info.format_name, extension=info.extension, size_bytes=len(data), width=info.width, height=info.height, method=f"비트레이트 자동 조정 ({video_bitrate // 1000:,} kbps)")

    def _fit_video_to_target(self, result_path: Path, actual_size: int, info: VideoInfo, container: str, video_bitrate: int, audio_bitrate: int, target_bytes: int, progress):
        if actual_size <= target_bytes: return result_path, actual_size, video_bitrate
        for attempt in range(4):
            ratio = target_bytes / actual_size
            video_bitrate = max(50_000, int(video_bitrate * ratio * 0.94))
            start = 82 + attempt * 4
            end = min(96, 86 + attempt * 3)
            self._progress(progress, start, f"비트레이트 재조정 중... {video_bitrate // 1000:,} kbps")
            result_path.unlink(missing_ok=True)
            result_path = self._encode_video(info.path, container, video_bitrate, audio_bitrate, progress, start, end)
            actual_size = result_path.stat().st_size
            if actual_size <= target_bytes: break
        if actual_size > target_bytes:
            result_path.unlink(missing_ok=True)
            raise ValueError("비디오를 목표 용량까지 줄일 수 없습니다. 목표 용량을 조금 높여 주세요.")
        return result_path, actual_size, video_bitrate

    @staticmethod
    def _validate_video_info(info: VideoInfo):
        if info.duration <= 0: raise ValueError("비디오 재생 시간을 확인할 수 없습니다.")
        if info.width <= 0 or info.height <= 0: raise ValueError("비디오 해상도를 확인할 수 없습니다.")

    @classmethod
    def _video_container(cls, extension: str) -> str:
        container = cls.VIDEO_CONTAINERS.get(extension)
        if container is None: raise ValueError("지원하지 않는 비디오 형식입니다.")
        return container

    @staticmethod
    def _select_audio_bitrate(info: VideoInfo, target_bytes: int) -> int:
        if not info.audio_codec: return 0
        if target_bytes < 5_000_000: return 64_000
        if target_bytes < 20_000_000: return 96_000
        return min(128_000, info.audio_bitrate or 128_000)

    def _encode_video(self, source: Path, container: str, video_bitrate: int, audio_bitrate: int, progress, start: int, end: int) -> Path:
        suffix = "." + {"matroska": "mkv"}.get(container, container)
        fd, output_name = tempfile.mkstemp(prefix="dietfile_", suffix=suffix)
        os.close(fd)
        output_path = Path(output_name)
        command = ["ffmpeg", "-y", "-v", "error", "-i", str(source), "-map", "0:v:0", "-c:v", "libx264", "-b:v", str(video_bitrate), "-maxrate", str(video_bitrate), "-bufsize", str(video_bitrate * 2), "-preset", "medium"]
        command.extend(["-map", "0:a:0?", "-c:a", "aac", "-b:a", str(audio_bitrate)] if audio_bitrate > 0 else ["-an"])
        command.extend(["-progress", "pipe:1", "-nostats", str(output_path)])
        self._progress(progress, start, "비디오 인코딩 중...")
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except FileNotFoundError as exc:
            output_path.unlink(missing_ok=True)
            raise RuntimeError("FFmpeg를 찾을 수 없습니다. FFmpeg를 설치해 주세요.") from exc
        try:
            self._read_video_progress(process, source, progress, start, end)
            stderr = process.stderr.read().strip() if process.stderr else ""
            return_code = process.wait()
        except Exception:
            process.kill()
            process.wait()
            output_path.unlink(missing_ok=True)
            raise
        if return_code != 0 or not output_path.exists():
            output_path.unlink(missing_ok=True)
            raise RuntimeError(stderr or "비디오 인코딩에 실패했습니다.")
        return output_path

    def _read_video_progress(self, process, source: Path, progress, start: int, end: int):
        duration = max(1.0, self._probe_duration(source))
        while True:
            line = process.stdout.readline() if process.stdout else ""
            if not line:
                if process.poll() is not None: break
                continue
            if not line.startswith("out_time_ms="): continue
            try:
                current_time = int(line.split("=", 1)[1]) / 1_000_000
                percent = start + int(min(1.0, current_time / duration) * (end - start))
                self._progress(progress, percent, "비디오 인코딩 중...")
            except (ValueError, OSError):
                continue

    @staticmethod
    def _probe_duration(path: Path) -> float:
        try:
            process = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], capture_output=True, text=True, check=True)
            return float(process.stdout.strip())
        except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
            return 1.0

    def _find_quality(self, image: Image.Image, target_bytes: int, encoder, format_name: str, progress, start: int, end: int):
        low, high, best = 1, 100, None
        while low <= high:
            quality = (low + high) // 2
            try:
                data = encoder(image, quality)
            except OSError:
                data = None
            if data is not None and len(data) <= target_bytes:
                best = (quality, data)
                low = quality + 1
            else:
                high = quality - 1
            percent = min(end, start + int((quality / 100) * (end - start)))
            self._progress(progress, percent, f"최적 품질 계산 중... {format_name} 품질 {quality}")
        return best

    def _find_png_palette(self, image: Image.Image, target_bytes: int, progress, start=35, end=62):
        has_alpha = "A" in image.mode or "transparency" in image.info
        source = image.convert("RGBA" if has_alpha else "RGB")
        for index, colors in enumerate(self.PNG_COLOR_VALUES):
            try:
                candidate = source.quantize(colors=colors, method=Image.Quantize.FASTOCTREE if has_alpha else Image.Quantize.MEDIANCUT)
                data = self._encode_png(candidate)
            except OSError:
                continue
            percent = self._scale_progress(index, len(self.PNG_COLOR_VALUES), start, end)
            self._progress(progress, percent, f"최적 색상 수 계산 중... {colors}색")
            if len(data) <= target_bytes: return colors, data
        return None

    @staticmethod
    def _generate_scales(start=0.98, minimum=0.10, factor=0.92):
        scales = []
        scale = start
        while scale >= minimum:
            scales.append(scale)
            scale *= factor
        if not scales or scales[-1] > minimum: scales.append(minimum)
        return scales

    @staticmethod
    def _scale_progress(index: int, total: int, start: int, end: int) -> int:
        return start + int((index / max(1, total - 1)) * (end - start))

    @staticmethod
    def _create_result(data: bytes, format_name: str, extension: str, width: int, height: int, method: str, progress=None, message: str = "최적화가 완료되었습니다.", quality: int | None = None, colors: int | None = None) -> OptimizationResult:
        result = OptimizationResult(data=data, format_name=format_name, extension=extension, size_bytes=len(data), width=width, height=height, method=method, quality=quality, colors=colors)
        if progress: progress(ProgressUpdate(percent=100, message=message))
        return result

    @staticmethod
    def _encode_jpeg(image: Image.Image, quality: int) -> bytes:
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=max(1, min(100, quality)), optimize=False, progressive=False, subsampling=2)
        return buffer.getvalue()

    @staticmethod
    def _encode_webp(image: Image.Image, quality: int) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format="WEBP", quality=max(1, min(100, quality)), method=6, lossless=False)
        return buffer.getvalue()

    @staticmethod
    def _encode_png(image: Image.Image) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True, compress_level=9)
        return buffer.getvalue()

    @staticmethod
    def _resize(image: Image.Image, scale: float) -> Image.Image:
        width = max(1, round(image.width * scale))
        height = max(1, round(image.height * scale))
        return image.resize((width, height), Image.Resampling.LANCZOS)

    @staticmethod
    def _progress(callback, percent: int, message: str):
        if callback: callback(ProgressUpdate(percent=max(0, min(100, percent)), message=message))