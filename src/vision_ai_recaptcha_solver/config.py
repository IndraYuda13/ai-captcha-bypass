from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SolverConfig:
    model_path: Path | str | None = None
    detection_model_path: Path | str | None = None
    download_dir: Path = Path('tmp/visionai-local')
    server_port: int = 8443
    proxy: str | None = None
    browser_path: str | None = None
    headless: bool = True
    timeout: float = 300.0
    max_attempts: int = 5
    human_delay_mean: float = 0.2
    human_delay_sigma: float = 0.1
    log_level: str = 'WARNING'
    persist_html: bool = False
    verbose: bool = False
    conf_threshold: float = 0.7
    min_confidence_threshold: float = 0.2
    fourth_cell_threshold: float = 0.7
    detection_conf_threshold: float = 0.6
    default_timeout: float = 10.0
    image_download_retries: int = 3
    image_download_retry_delay: float = 1.0
    register_signal_handlers: bool = True
    cleanup_tmp_on_close: bool = True
    _download_dir_explicit: bool = field(init=False, repr=False, default=False)

    def __post_init__(self) -> None:
        self.download_dir = Path(self.download_dir)
        self._download_dir_explicit = True
        if not 1 <= self.server_port <= 65535:
            raise ValueError(f'server_port must be between 1 and 65535, got {self.server_port}')
        if self.timeout <= 0:
            raise ValueError(f'timeout must be positive, got {self.timeout}')
        if self.max_attempts < 1:
            raise ValueError(f'max_attempts must be at least 1, got {self.max_attempts}')
        for value in (
            self.conf_threshold,
            self.min_confidence_threshold,
            self.fourth_cell_threshold,
            self.detection_conf_threshold,
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError('confidence thresholds must be between 0.0 and 1.0')
