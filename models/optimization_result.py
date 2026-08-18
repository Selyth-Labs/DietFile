from dataclasses import dataclass

@dataclass(frozen=True)
class OptimizationResult:
    data: bytes
    format_name: str
    extension: str
    size_bytes: int
    width: int
    height: int
    method: str
    quality: int | None = None
    colors: int | None = None
