from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot
from core.image_analyzer import ImageAnalyzer, ImageInfo
from core.optimizer import ImageOptimizer
from core.video_analyzer import VideoAnalyzer, VideoInfo
from models.folder_optimization_result import FolderOptimizationResult
from models.optimization_result import OptimizationResult

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS
OUTPUT_DIR_NAME = "DietFile"

class OptimizationWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object, int)
    failed = Signal(str)

    def __init__(self, optimizer: ImageOptimizer, info: ImageInfo | VideoInfo, target_bytes: int):
        super().__init__()
        self.optimizer = optimizer
        self.info = info
        self.target_bytes = target_bytes

    @Slot()
    def run(self):
        try:
            result = self.optimizer.optimize(self.info, self.target_bytes, self._handle_progress)
            self.finished.emit(result, self.target_bytes)
        except Exception as exc:
            self.failed.emit(str(exc))

    def _handle_progress(self, update):
        self.progress.emit(update.percent, update.message)

class FolderOptimizationWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, optimizer: ImageOptimizer, image_analyzer: ImageAnalyzer, video_analyzer: VideoAnalyzer, source_dir: str | Path, target_bytes: int, include_subfolders: bool):
        super().__init__()
        self.optimizer = optimizer
        self.image_analyzer = image_analyzer
        self.video_analyzer = video_analyzer
        self.source_dir = Path(source_dir)
        self.target_bytes = target_bytes
        self.include_subfolders = include_subfolders
        self.output_dir: Path | None = None

    @Slot()
    def run(self):
        try:
            result = self._optimize_folder()
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))

    def _optimize_folder(self) -> FolderOptimizationResult:
        files = self._collect_files()
        if not files: raise ValueError("선택한 폴더에 파일이 없습니다.")

        self.output_dir = self._create_output_dir()
        stats = {"supported": 0, "optimized": 0, "skipped": 0, "failed": 0, "original_size": 0, "optimized_size": 0}

        for index, path in enumerate(files):
            if not self._is_supported(path): continue
            stats["supported"] += 1
            self._progress(self._file_progress(index, len(files), 0), f"파일 분석 중... {index + 1}/{len(files)} · {path.name}")

            try:
                optimized_size, skipped = self._optimize_file(path, index, len(files))
                stats["original_size"] += path.stat().st_size
                stats["optimized_size"] += optimized_size
                stats["skipped" if skipped else "optimized"] += 1
            except Exception as exc:
                stats["failed"] += 1
                self._progress(self._file_progress(index, len(files), 100), f"최적화 실패 · {path.name} · {exc}")

        if stats["supported"] == 0: raise ValueError("선택한 폴더에서 지원하는 이미지 또는 비디오 파일을 찾지 못했습니다.")

        return FolderOptimizationResult(source_dir=self.source_dir, output_dir=self.output_dir, total_files=len(files), supported_files=stats["supported"], optimized_files=stats["optimized"], skipped_files=stats["skipped"], failed_files=stats["failed"], original_size_bytes=stats["original_size"], optimized_size_bytes=stats["optimized_size"])

    def _optimize_file(self, path: Path, index: int, total_files: int) -> tuple[int, bool]:
        info = self._analyze(path)
        original_size = info.size_bytes

        if original_size <= self.target_bytes:
            self._progress(self._file_progress(index, total_files, 100), f"건너뜀 · 이미 목표 용량 이하 · {path.name}")
            return original_size, True

        result = self.optimizer.optimize(info, self.target_bytes, lambda update: self._handle_file_progress(index, total_files, update.percent, update.message))
        output_path = self._build_output_path(path, result)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(result.data)
        self._progress(self._file_progress(index, total_files, 100), f"최적화 완료 · {index + 1}/{total_files} · {path.name}")
        return result.size_bytes, False

    def _collect_files(self) -> list[Path]:
        pattern = "**/*" if self.include_subfolders else "*"
        return sorted((path for path in self.source_dir.glob(pattern) if path.is_file() and not self._is_output_file(path)), key=lambda path: str(path).lower())

    @staticmethod
    def _is_supported(path: Path) -> bool:
        return path.suffix.lower() in SUPPORTED_EXTENSIONS

    def _analyze(self, path: Path) -> ImageInfo | VideoInfo:
        extension = path.suffix.lower()
        if extension in SUPPORTED_IMAGE_EXTENSIONS: return self.image_analyzer.analyze(path)
        if extension in SUPPORTED_VIDEO_EXTENSIONS: return self.video_analyzer.analyze(path)
        raise ValueError("지원하지 않는 파일 형식입니다.")

    def _create_output_dir(self) -> Path:
        output_dir = self.source_dir / OUTPUT_DIR_NAME
        index = 2
        while output_dir.exists():
            output_dir = self.source_dir / f"{OUTPUT_DIR_NAME} {index}"
            index += 1
        output_dir.mkdir(parents=True)
        return output_dir

    def _is_output_file(self, path: Path) -> bool:
        try:
            relative_path = path.relative_to(self.source_dir)
        except ValueError:
            return False

        if not relative_path.parts: return False
        first_part = relative_path.parts[0]
        return first_part == OUTPUT_DIR_NAME or (first_part.startswith(f"{OUTPUT_DIR_NAME} ") and first_part[len(OUTPUT_DIR_NAME) + 1:].isdigit())

    def _build_output_path(self, source_path: Path, result: OptimizationResult) -> Path:
        relative_path = source_path.relative_to(self.source_dir)
        original_size = self._format_size(source_path.stat().st_size).replace(" ", "")
        optimized_size = self._format_size(result.size_bytes).replace(" ", "")
        output_name = f"{original_size}_to_{optimized_size}_{relative_path.stem}{result.extension}"
        return self.output_dir / relative_path.parent / output_name

    def _handle_file_progress(self, index: int, total: int, percent: int, message: str):
        self._progress(self._file_progress(index, total, percent), f"{index + 1}/{total} · {message}")

    @staticmethod
    def _file_progress(index: int, total: int, percent: int) -> int:
        return int(((index + percent / 100) / max(1, total)) * 100)

    def _progress(self, percent: int, message: str):
        self.progress.emit(max(0, min(100, percent)), message)

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1_000 or unit == "GB": return f"{value:.2f} {unit}"
            value /= 1_000
        return f"{size} B"