from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class FolderOptimizationResult:
    source_dir: Path
    output_dir: Path
    total_files: int
    supported_files: int
    optimized_files: int
    skipped_files: int
    failed_files: int
    original_size_bytes: int
    optimized_size_bytes: int

    @property
    def reduction_bytes(self) -> int:
        return self.original_size_bytes - self.optimized_size_bytes

    @property
    def reduction_rate(self) -> float:
        if self.original_size_bytes <= 0:
            return 0.0
        return self.reduction_bytes / self.original_size_bytes * 100