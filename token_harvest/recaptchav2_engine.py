"""Thin wrapper over the new VisionAI-style solver package."""

from __future__ import annotations

from typing import Any, Dict, Optional

from vision_ai_recaptcha_solver.solver import RecaptchaSolver


def solve_recaptcha_v2(
    *,
    driver,
    provider: str = 'gemini-cli',
    model: Optional[str] = None,
    max_rounds: int = 5,
    screenshots_dir: str = 'screenshots',
    ask_recaptcha_instructions_with_provider=None,
    check_tile_for_object=None,
    debug: bool = True,
    **kwargs: Any,
) -> Dict[str, Any]:
    solver = RecaptchaSolver()
    return solver.solve(
        driver=driver,
        provider=provider,
        model=model,
        max_rounds=max_rounds,
        screenshots_dir=screenshots_dir,
        ask_recaptcha_instructions_with_provider=ask_recaptcha_instructions_with_provider,
        check_tile_for_object=check_tile_for_object,
        debug=debug,
        **kwargs,
    )
