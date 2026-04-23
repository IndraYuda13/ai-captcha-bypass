from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from vision_ai_recaptcha_solver.config import SolverConfig


class BaseCaptchaHandler(ABC):
    def __init__(self, config: SolverConfig):
        self.config = config

    @abstractmethod
    def solve(self, **kwargs: Any):
        raise NotImplementedError
