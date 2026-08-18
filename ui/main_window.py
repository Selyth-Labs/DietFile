from pathlib import Path
from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QProgressBar, QVBoxLayout, QWidget, QCheckBox
from core.image_analyzer import ImageAnalyzer, ImageInfo
from core.optimizer import ImageOptimizer
from core.video_analyzer import VideoAnalyzer, VideoInfo
from models.folder_optimization_result import FolderOptimizationResult
from models.optimization_result import OptimizationResult
from ui.workers import FolderOptimizationWorker, OptimizationWorker

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
SUPPORTED_FILE_FILTER = "지원 파일 (*.jpg *.jpeg *.png *.webp *.gif *.mp4 *.mov *.mkv *.webm *.avi);;이미지 파일 (*.jpg *.jpeg *.png *.webp *.gif);;비디오 파일 (*.mp4 *.mov *.mkv *.webm *.avi)"
SUPPORTED_FORMAT_TEXT = "JPEG / PNG / WebP / GIF / MP4 / MOV / MKV / WebM / AVI"
SIZE_MULTIPLIERS = {"B": 1, "KB": 1_000, "MB": 1_000_000, "GB": 1_000_000_000}

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DietFile")
        self.setMinimumSize(560, 660)
        self.resize(620, 720)
        self.image_analyzer = ImageAnalyzer()
        self.video_analyzer = VideoAnalyzer()
        self.optimizer = ImageOptimizer(self.image_analyzer)
        self.info: ImageInfo | VideoInfo | None = None
        self.result: OptimizationResult | None = None
        self.folder_result: FolderOptimizationResult | None = None
        self.selected_folder: Path | None = None
        self.selection_mode = "file"
        self.thread: QThread | None = None
        self.worker = None
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(12)

        title = QLabel("DietFile")
        title.setObjectName("titleLabel")
        outer.addWidget(title)

        subtitle = QLabel("원하는 용량만 지정하면 파일이나 폴더가 알아서 최적화됩니다.")
        subtitle.setObjectName("subtitleLabel")
        outer.addWidget(subtitle)
        outer.addSpacing(8)

        selection_buttons = QHBoxLayout()
        self.select_button = QPushButton("파일 선택")
        self.select_button.setMinimumHeight(42)
        self.select_button.clicked.connect(self._select_file)
        selection_buttons.addWidget(self.select_button)

        self.folder_button = QPushButton("폴더 선택")
        self.folder_button.setMinimumHeight(42)
        self.folder_button.clicked.connect(self._select_folder)
        selection_buttons.addWidget(self.folder_button)
        outer.addLayout(selection_buttons)

        self.subfolder_checkbox = QCheckBox("하위 폴더 포함")
        self.subfolder_checkbox.setChecked(False)
        outer.addWidget(self.subfolder_checkbox)

        self.file_label = QLabel("선택된 파일\n-")
        self.file_label.setWordWrap(True)
        self.file_label.setObjectName("fileLabel")
        outer.addWidget(self.file_label)
        outer.addSpacing(2)

        self.info_frame = QGroupBox("파일 정보")
        info_layout = QGridLayout(self.info_frame)
        info_layout.setContentsMargins(14, 14, 14, 14)
        info_layout.setHorizontalSpacing(16)
        info_layout.setVerticalSpacing(8)
        self.info_labels = {}

        for row, (key, title) in enumerate([("format", "형식"), ("mime", "MIME 타입"), ("size", "현재 용량"), ("resolution", "해상도"), ("details", "상세 정보")]):
            label = QLabel(title)
            value = QLabel("-")
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value.setWordWrap(True)
            info_layout.addWidget(label, row, 0)
            info_layout.addWidget(value, row, 1)
            self.info_labels[key] = value

        info_layout.setColumnStretch(1, 1)
        outer.addWidget(self.info_frame)

        target_layout = QHBoxLayout()
        target_layout.setContentsMargins(0, 6, 0, 0)
        target_label = QLabel("목표 용량")
        target_label.setObjectName("targetLabel")
        target_layout.addWidget(target_label)
        target_layout.addStretch()

        self.target_entry = QLineEdit("10 MB")
        self.target_entry.setFixedWidth(150)
        self.target_entry.setPlaceholderText("예: 10 MB")
        target_layout.addWidget(self.target_entry)
        outer.addLayout(target_layout)

        self.optimize_button = QPushButton("최적화 시작")
        self.optimize_button.setMinimumHeight(42)
        self.optimize_button.setEnabled(False)
        self.optimize_button.clicked.connect(self._start_optimization)
        outer.addWidget(self.optimize_button)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        outer.addWidget(self.progress)

        self.status_label = QLabel("파일 또는 폴더를 선택해 주세요.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)

        self.result_frame = QGroupBox("최적화 결과")
        result_layout = QVBoxLayout(self.result_frame)
        result_layout.setContentsMargins(14, 14, 14, 14)

        self.result_label = QLabel("-")
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        result_layout.addWidget(self.result_label)
        result_layout.addStretch()

        buttons = QHBoxLayout()
        self.save_button = QPushButton("저장 위치 선택")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._save_result)

        self.reoptimize_button = QPushButton("다시 최적화")
        self.reoptimize_button.setEnabled(False)
        self.reoptimize_button.clicked.connect(self._start_optimization)

        buttons.addWidget(self.save_button)
        buttons.addWidget(self.reoptimize_button)
        result_layout.addLayout(buttons)
        outer.addWidget(self.result_frame, 1)

        self._apply_stylesheet()

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow {
                background: palette(window);
            }
            QLabel#titleLabel {
                font-size: 28px;
                font-weight: 700;
            }
            QLabel#subtitleLabel {
                color: #777777;
                font-size: 13px;
            }
            QLabel#fileLabel {
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#targetLabel {
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#statusLabel {
                color: #666666;
            }
            QGroupBox {
                font-weight: 600;
            }
            QPushButton {
                padding: 8px 12px;
            }
            QLineEdit {
                padding: 7px 9px;
            }
            QProgressBar {
                min-height: 8px;
                max-height: 18px;
            }
        """)

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", SUPPORTED_FILE_FILTER)
        if not path: return

        file_path = Path(path)
        try:
            self.info = self._analyze_file(file_path)
        except Exception as exc:
            QMessageBox.critical(self, "파일 선택 실패", str(exc))
            return

        self.selection_mode = "file"
        self.selected_folder = None
        self.folder_result = None
        self.result = None
        self.subfolder_checkbox.setEnabled(False)
        self.file_label.setText(f"선택된 파일\n{self.info.filename}")
        self._update_file_info()
        self._reset_result_state()
        self.optimize_button.setEnabled(True)
        self.status_label.setText("목표 용량을 입력한 뒤 최적화를 시작하세요.")

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if not folder: return

        self.selection_mode = "folder"
        self.selected_folder = Path(folder)
        self.info = None
        self.result = None
        self.folder_result = None
        self.subfolder_checkbox.setEnabled(True)
        self.file_label.setText(f"선택된 폴더\n{self.selected_folder}")
        self._update_folder_info()
        self._reset_result_state()
        self.optimize_button.setEnabled(True)
        self.status_label.setText("목표 용량을 입력한 뒤 폴더 최적화를 시작하세요.")

    def _update_file_info(self):
        if self.info is None: return

        self.info_frame.setTitle("이미지 정보" if isinstance(self.info, ImageInfo) else "비디오 정보")
        self.info_labels["format"].setText(self.info.format_name)
        self.info_labels["mime"].setText(self.info.mime_type)
        self.info_labels["size"].setText(self._format_size(self.info.size_bytes))
        self.info_labels["resolution"].setText(f"{self.info.width:,} × {self.info.height:,}")
        self.info_labels["details"].setText(self._format_image_details() if isinstance(self.info, ImageInfo) else self._format_video_details())

    def _format_image_details(self) -> str:
        return f"{self.info.mode} / {self.info.channels or '-'}채널 / {self.info.bits or '-'}bit"

    def _format_video_details(self) -> str:
        fps = f"{self.info.fps:.2f} FPS" if self.info.fps is not None else "FPS -"
        duration = self._format_duration(self.info.duration)
        video_codec = self.info.video_codec or "-"
        audio_codec = self.info.audio_codec or "없음"
        return f"{duration} / {fps}\n영상 코덱: {video_codec} / 오디오 코덱: {audio_codec}"

    def _update_folder_info(self):
        self.info_frame.setTitle("폴더 정보")
        self.info_labels["format"].setText("지원 형식 자동 탐색")
        self.info_labels["mime"].setText("-")
        self.info_labels["size"].setText("-")
        self.info_labels["resolution"].setText("-")
        self.info_labels["details"].setText(SUPPORTED_FORMAT_TEXT)

    def _start_optimization(self):
        if self.thread is not None: return

        try:
            target_bytes = self._parse_size(self.target_entry.text())
        except ValueError as exc:
            QMessageBox.warning(self, "목표 용량 확인", str(exc))
            return

        if target_bytes < 1000:
            QMessageBox.warning(self, "목표 용량 확인", "목표 용량은 최소 1 KB 이상으로 입력해 주세요.")
            return

        if self.selection_mode == "file":
            if not self.info: return
            if target_bytes >= self.info.size_bytes:
                QMessageBox.warning(self, "목표 용량 확인", "목표 용량은 현재 파일보다 작아야 합니다.")
                return
            self._start_file_optimization(target_bytes)
            return

        if not self.selected_folder: return
        self._start_folder_optimization(target_bytes)

    def _start_file_optimization(self, target_bytes: int):
        self._set_working(True)
        self.progress.setValue(0)
        self.status_label.setText("최적화 준비 중...")
        self.thread = QThread()
        self.worker = OptimizationWorker(self.optimizer, self.info, target_bytes)
        self._start_worker(self.worker, self._optimization_done, self._optimization_failed)

    def _start_folder_optimization(self, target_bytes: int):
        self._set_working(True)
        self.progress.setValue(0)
        self.status_label.setText("폴더의 지원 파일을 탐색하는 중...")
        self.thread = QThread()
        self.worker = FolderOptimizationWorker(self.optimizer, self.image_analyzer, self.video_analyzer, self.selected_folder, target_bytes, self.subfolder_checkbox.isChecked())
        self._start_worker(self.worker, self._folder_optimization_done, self._folder_optimization_failed)

    def _start_worker(self, worker, finished_callback, failed_callback):
        worker.moveToThread(self.thread)
        self.thread.started.connect(worker.run)
        worker.progress.connect(self._update_progress)
        worker.finished.connect(finished_callback)
        worker.failed.connect(failed_callback)
        worker.finished.connect(self._finish_worker)
        worker.failed.connect(self._finish_worker)
        self.thread.finished.connect(self._clear_worker)
        self.thread.start()

    def _optimization_done(self, result: OptimizationResult, target_bytes: int):
        self.result = result
        self.progress.setValue(100)
        self.status_label.setText("최적화 완료 · 결과 파일 검증 완료")

        reduction = self.info.size_bytes - result.size_bytes
        reduction_rate = reduction / self.info.size_bytes * 100
        target_status = "목표 용량 이하" if result.size_bytes <= target_bytes else "목표 용량 초과"
        optimization_info = self._get_optimization_info(result)
        resolution = f"{self.info.width:,} × {self.info.height:,} → {result.width:,} × {result.height:,}"

        self.result_label.setText(f"{self._format_size(self.info.size_bytes)} → {self._format_size(result.size_bytes)} ({reduction_rate:.1f}% 감소)\n{resolution}\n{result.format_name} · {optimization_info}\n{target_status}")
        self._set_working(False)
        self.save_button.setEnabled(True)
        self.reoptimize_button.setEnabled(True)

    def _get_optimization_info(self, result: OptimizationResult) -> str:
        if isinstance(self.info, ImageInfo):
            if result.format_name in {"JPEG", "WEBP"} and result.quality is not None: return f"품질 {result.quality}"
            if result.format_name in {"PNG", "GIF"} and result.colors is not None: return f"{result.colors}색"
        return result.method

    def _folder_optimization_done(self, result: FolderOptimizationResult):
        self.folder_result = result
        self.progress.setValue(100)
        reduction = result.reduction_bytes
        reduction_rate = result.reduction_rate
        self.status_label.setText("폴더 최적화 완료")
        self.result_label.setText(f"폴더 최적화 완료\n\n전체 파일: {result.total_files}개\n지원 파일: {result.supported_files}개\n최적화 완료: {result.optimized_files}개\n건너뜀: {result.skipped_files}개\n실패: {result.failed_files}개\n\n총 용량\n{self._format_size(result.original_size_bytes)} → {self._format_size(result.optimized_size_bytes)}\n{self._format_size(reduction)} 감소 ({reduction_rate:.1f}% 감소)\n\n결과 폴더\n{result.output_dir}")
        self._set_working(False)
        self.save_button.setEnabled(False)
        self.reoptimize_button.setEnabled(True)

    def _optimization_failed(self, message: str):
        self._set_working(False)
        self.status_label.setText("최적화에 실패했습니다.")
        QMessageBox.critical(self, "최적화 실패", message)

    def _folder_optimization_failed(self, message: str):
        self._set_working(False)
        self.status_label.setText("폴더 최적화에 실패했습니다.")
        QMessageBox.critical(self, "폴더 최적화 실패", message)

    def _analyze_file(self, path: Path) -> ImageInfo | VideoInfo:
        extension = path.suffix.lower()
        if extension in SUPPORTED_IMAGE_EXTENSIONS: return self.image_analyzer.analyze(path)
        if extension in SUPPORTED_VIDEO_EXTENSIONS: return self.video_analyzer.analyze(path)
        raise ValueError("지원하지 않는 파일 형식입니다.")

    def _reset_result_state(self):
        self.save_button.setEnabled(False)
        self.reoptimize_button.setEnabled(False)
        self.progress.setValue(0)
        self.result_label.setText("-")

    def _finish_worker(self, *_):
        if self.thread and self.thread.isRunning(): self.thread.quit()

    def _clear_worker(self):
        if self.worker: self.worker.deleteLater()
        if self.thread: self.thread.deleteLater()
        self.worker = None
        self.thread = None

    def _update_progress(self, percent: int, message: str):
        self.progress.setValue(percent)
        self.status_label.setText(message)

    def _save_result(self):
        if not self.result or not self.info: return

        original_size = self._format_size(self.info.size_bytes).replace(" ", "")
        optimized_size = self._format_size(self.result.size_bytes).replace(" ", "")
        default_name = f"{original_size}_to_{optimized_size}_{Path(self.info.filename).stem}{self.result.extension}"
        path, _ = QFileDialog.getSaveFileName(self, "최적화 결과 저장", default_name, f"{self.result.format_name} (*{self.result.extension})")
        if not path: return

        try:
            with open(path, "wb") as file: file.write(self.result.data)
            QMessageBox.information(self, "저장 완료", f"최적화 결과를 저장했습니다.\n\n{path}")
        except OSError as exc:
            QMessageBox.critical(self, "저장 실패", str(exc))

    def _set_working(self, working: bool):
        self.select_button.setEnabled(not working)
        self.folder_button.setEnabled(not working)
        self.subfolder_checkbox.setEnabled(not working and self.selection_mode == "folder")
        self.optimize_button.setEnabled(not working and (self.info is not None or self.selected_folder is not None))
        self.reoptimize_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.target_entry.setEnabled(not working)

    @staticmethod
    def _parse_size(value: str) -> int:
        text = value.strip().upper().replace(",", "")
        parts = text.split()
        if len(parts) == 1:
            number, unit = parts[0], "MB"
        elif len(parts) == 2:
            number, unit = parts
        else:
            raise ValueError("용량은 예: 10 MB, 500 KB처럼 입력해 주세요.")

        try:
            amount = float(number)
        except ValueError:
            raise ValueError("목표 용량은 숫자로 입력해 주세요.")

        if amount <= 0: raise ValueError("목표 용량은 0보다 커야 합니다.")
        if unit not in SIZE_MULTIPLIERS: raise ValueError("지원 단위는 B, KB, MB, GB입니다.")
        return int(amount * SIZE_MULTIPLIERS[unit])

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1_000 or unit == "GB": return f"{value:.2f} {unit}"
            value /= 1_000
        return f"{size} B"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        total_seconds = max(0, int(seconds))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours: return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "작업 진행 중", "최적화 작업이 끝난 후 프로그램을 종료해 주세요.")
            event.ignore()
            return
        event.accept()