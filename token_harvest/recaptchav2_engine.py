"""Experimental callable reCAPTCHA v2 engine.

This module now owns the structured result contract and a first real migration of
control flow from the old CLI-centric `recaptcha_v2_test()` implementation.
It is still incomplete, but no longer only a placeholder.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from PIL import Image
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, WebDriverException


@dataclass
class RecaptchaV2TraceEntry:
    round: int
    target: str = ""
    tile_count: int = 0
    new_clicks: int = 0
    selected_tiles: List[int] = field(default_factory=list)
    checkbox_verified: bool = False
    note: str = ""


@dataclass
class RecaptchaV2Result:
    status: str
    verified: bool
    token: str = ""
    stage: str = "init"
    message: str = ""
    trace: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "verified": self.verified,
            "token": self.token,
            "stage": self.stage,
            "message": self.message,
            "trace": self.trace,
            "artifacts": self.artifacts,
        }


def new_result() -> RecaptchaV2Result:
    return RecaptchaV2Result(
        status="error",
        verified=False,
        stage="init",
        message="recaptchav2 engine started",
    )


def append_trace(result: RecaptchaV2Result, **kwargs: Any) -> None:
    entry = RecaptchaV2TraceEntry(**kwargs)
    result.trace.append({
        "round": entry.round,
        "target": entry.target,
        "tile_count": entry.tile_count,
        "new_clicks": entry.new_clicks,
        "selected_tiles": entry.selected_tiles,
        "checkbox_verified": entry.checkbox_verified,
        "note": entry.note,
    })


def _checkbox_verified(driver, timeout: int = 8) -> bool:
    driver.switch_to.default_content()
    frame = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, "//iframe[@title='reCAPTCHA']")))
    driver.switch_to.frame(frame)
    try:
        anchor = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.ID, 'recaptcha-anchor')))
        checked = (anchor.get_attribute('aria-checked') or '').lower()
        return checked == 'true'
    finally:
        driver.switch_to.default_content()


def _switch_to_challenge_frame(driver, timeout: int = 8):
    driver.switch_to.default_content()
    frame = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, "//iframe[contains(@title, 'recaptcha challenge') or contains(@title, 'challenge expires in two minutes')]"))
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", frame)
    time.sleep(0.35)
    driver.switch_to.frame(frame)
    return frame


def _wait_challenge_ready(driver, timeout: int = 8):
    table = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, "//table[contains(@class, 'rc-imageselect-table')]"))
    )
    instruction = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'rc-imageselect-instructions'))
    )
    return instruction, table


def _extract_target_keyword_from_dom(driver) -> str:
    selectors = [
        (By.CSS_SELECTOR, '.rc-imageselect-payload strong'),
        (By.CSS_SELECTOR, '.rc-imageselect-desc strong'),
        (By.CSS_SELECTOR, '.rc-imageselect-desc-no-canonical strong'),
    ]
    for by, selector in selectors:
        try:
            elems = driver.find_elements(by, selector)
            for elem in elems:
                text = (elem.text or '').strip().lower()
                if text:
                    return text
        except Exception:
            continue
    return ''


def _challenge_still_open(driver) -> bool:
    try:
        _switch_to_challenge_frame(driver, timeout=3)
        _wait_challenge_ready(driver, timeout=3)
        driver.switch_to.default_content()
        return True
    except Exception:
        driver.switch_to.default_content()
        return False


def _extract_token(driver) -> str:
    driver.switch_to.default_content()
    try:
        token = driver.execute_script(
            """
            const el = document.getElementById('g-recaptcha-response');
            return el ? (el.value || '') : '';
            """
        )
        return (token or '').strip()
    except Exception:
        return ''


def _get_challenge_image_urls(driver) -> List[str]:
    selectors = [
        "#rc-imageselect-target img",
        ".rc-image-tile-wrapper img",
        ".rc-imageselect-tile img",
    ]
    urls: List[str] = []
    for selector in selectors:
        try:
            elems = driver.find_elements(By.CSS_SELECTOR, selector)
            urls = []
            for elem in elems:
                src = (elem.get_attribute('src') or '').strip()
                if src:
                    urls.append(src)
            if urls:
                return urls
        except Exception:
            continue
    return urls


def _download_image_bytes(url: str) -> Optional[Image.Image]:
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert('RGB')
    except Exception:
        return None


def _composite_dynamic_cells(base_grid: Image.Image, changed_cells: List[int], current_urls: List[str], cols: int) -> Image.Image:
    merged = base_grid.copy()
    width, height = merged.size
    rows = max(1, (len(current_urls) + cols - 1) // cols)
    tile_w = width // cols
    tile_h = height // rows
    for cell_num in changed_cells:
        idx = cell_num - 1
        if idx >= len(current_urls):
            continue
        patch = _download_image_bytes(current_urls[idx])
        if patch is None:
            continue
        patch = patch.resize((tile_w, tile_h))
        row = idx // cols
        col = idx % cols
        merged.paste(patch, (col * tile_w, row * tile_h))
    return merged


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
    **_kwargs: Any,
) -> Dict[str, Any]:
    result = new_result()
    Path(screenshots_dir).mkdir(parents=True, exist_ok=True)
    result.stage = 'open_demo'

    if ask_recaptcha_instructions_with_provider is None or check_tile_for_object is None:
        result.message = 'required callbacks missing for recaptchav2 engine'
        return result.to_dict()

    try:
        page_url = _kwargs.get('page_url') or _kwargs.get('pageUrl') or 'https://2captcha.com/demo/recaptcha-v2'
        driver.get(page_url)
        result.stage = 'bootstrap_checkbox'
        recaptcha_frame = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//iframe[@title='reCAPTCHA']")))
        driver.switch_to.frame(recaptcha_frame)
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, 'recaptcha-checkbox-border'))).click()
        driver.switch_to.default_content()
        time.sleep(2)

        if _checkbox_verified(driver, timeout=4):
            result.verified = True
            result.token = _extract_token(driver)
            result.status = 'success'
            result.stage = 'verified'
            result.message = 'checkbox solved without image challenge'
            append_trace(result, round=0, checkbox_verified=True, note='checkbox solved directly')
            return result.to_dict()

        clicked_tile_indices = set()
        last_object_name = ''
        num_last_clicks = 0
        non_matching_cache = set()
        previous_urls: List[str] = []
        base_grid_img: Optional[Image.Image] = None

        for attempt in range(max_rounds):
            round_no = attempt + 1
            result.stage = 'challenge_round'
            try:
                _switch_to_challenge_frame(driver, timeout=5)
                instruction_element, table = _wait_challenge_ready(driver, timeout=10)
            except Exception:
                append_trace(result, round=round_no, note='no challenge iframe found, moving to final verification')
                break

            instruction_path = f'{screenshots_dir}/recaptcha_instruction_{round_no}.png'
            try:
                instruction_element.screenshot(instruction_path)
            except Exception:
                try:
                    table.screenshot(instruction_path)
                except Exception:
                    pass
            if Path(instruction_path).exists():
                result.artifacts.append(instruction_path)

            object_name = _extract_target_keyword_from_dom(driver)
            if not object_name and Path(instruction_path).exists():
                object_name = ask_recaptcha_instructions_with_provider(instruction_path, provider, model)
                append_trace(result, round=round_no, note=f'instruction fallback provider used: {provider}')
            if not object_name:
                append_trace(result, round=round_no, note='target keyword missing from DOM and fallback')
                result.stage = 'keyword_missing'
                result.message = 'failed to extract target keyword from challenge'
                return result.to_dict()

            is_new_object = object_name.lower() != last_object_name.lower()
            if is_new_object or num_last_clicks >= 3:
                clicked_tile_indices = set()
                last_object_name = object_name

            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", table)
            time.sleep(0.5)
            all_tiles = WebDriverWait(driver, 10).until(lambda d: table.find_elements(By.TAG_NAME, 'td'))
            current_urls = _get_challenge_image_urls(driver)
            grid_path = f'{screenshots_dir}/recaptcha_grid_{round_no}.png'
            table.screenshot(grid_path)
            result.artifacts.append(grid_path)
            grid_img = Image.open(grid_path).convert('RGB')
            grid_width, grid_height = grid_img.size
            tile_count = len(all_tiles)
            if tile_count == 16:
                cols = 4
                rows = 4
            elif tile_count == 9:
                cols = 3
                rows = 3
            else:
                cols = 4 if tile_count >= 16 else 3
                rows = max(1, (tile_count + cols - 1) // cols)
            tile_w = grid_width // cols
            tile_h = grid_height // rows

            selected_tiles = []
            if provider == 'visionai-local':
                try:
                    from visionai_local import visionai_rank_grid_tiles
                    ranked = visionai_rank_grid_tiles(grid_path, object_name, cols)
                    ranked_sorted = sorted(ranked, key=lambda x: x[1], reverse=True)
                    for cell_num, confidence in ranked_sorted:
                        tile_index = cell_num - 1
                        append_trace(result, round=round_no, note=f'visionai tile {tile_index} conf={confidence:.4f}')

                    if cols == 4:
                        selected_tiles = [cell_num - 1 for cell_num, confidence in ranked_sorted if confidence >= 0.7]
                    else:
                        if base_grid_img is not None and previous_urls and current_urls and len(current_urls) == len(previous_urls):
                            changed_cells = []
                            for idx, prev_url in enumerate(previous_urls):
                                if idx < len(current_urls) and current_urls[idx] != prev_url and (idx + 1) not in non_matching_cache:
                                    changed_cells.append(idx + 1)
                            if changed_cells:
                                merged = _composite_dynamic_cells(base_grid_img, changed_cells, current_urls, cols)
                                merged.save(grid_path)
                                grid_img = merged
                                ranked_sorted = sorted(visionai_rank_grid_tiles(grid_path, object_name, cols), key=lambda x: x[1], reverse=True)
                                for cell_num, confidence in ranked_sorted:
                                    append_trace(result, round=round_no, note=f'visionai dynamic tile {cell_num - 1} conf={confidence:.4f}')
                                selected_tiles = [cell_num - 1 for cell_num, confidence in ranked_sorted if (cell_num in changed_cells and confidence >= 0.7)]
                            else:
                                selected_tiles = []
                        else:
                            top3 = ranked_sorted[:3]
                            if len(top3) < 3 or any(conf < 0.2 for _, conf in top3):
                                append_trace(result, round=round_no, note='visionai top3 confidence below minimum threshold')
                                selected_tiles = []
                            else:
                                selected_tiles = [cell_num - 1 for cell_num, _ in top3]
                                if len(ranked_sorted) >= 4 and ranked_sorted[3][1] >= 0.7:
                                    selected_tiles.append(ranked_sorted[3][0] - 1)
                                base_grid_img = grid_img.copy()
                                for cell_num, _ in ranked_sorted:
                                    if (cell_num - 1) not in selected_tiles:
                                        non_matching_cache.add(cell_num)
                except Exception as exc:
                    append_trace(result, round=round_no, note=f'visionai-local fallback to per-tile due to error: {exc}')

            if not selected_tiles:
                for i in range(tile_count):
                    tile_path = f'{screenshots_dir}/tile_{round_no}_{i}.png'
                    row = i // cols
                    col = i % cols
                    left = col * tile_w
                    top = row * tile_h
                    right = (col + 1) * tile_w if col < cols - 1 else grid_width
                    bottom = (row + 1) * tile_h if row < rows - 1 else grid_height
                    grid_img.crop((left, top, right, bottom)).save(tile_path)
                    result.artifacts.append(tile_path)
                    _idx, should_click = check_tile_for_object((i, tile_path, object_name, provider, model))
                    if should_click:
                        selected_tiles.append(i)

            current_attempt_tiles = set(selected_tiles)
            new_tiles_to_click = current_attempt_tiles - clicked_tile_indices
            num_last_clicks = len(new_tiles_to_click)
            append_trace(
                result,
                round=round_no,
                target=object_name,
                tile_count=tile_count,
                new_clicks=len(new_tiles_to_click),
                selected_tiles=sorted(list(current_attempt_tiles)),
                checkbox_verified=False,
                note='round analyzed'
            )

            for i in sorted(list(new_tiles_to_click)):
                clicked = False
                for attempt_click in range(3):
                    try:
                        _switch_to_challenge_frame(driver, timeout=5)
                        _instruction, live_table = _wait_challenge_ready(driver, timeout=5)
                        all_tiles = live_table.find_elements(By.TAG_NAME, 'td')
                        if i >= len(all_tiles):
                            append_trace(result, round=round_no, note=f'tile index {i} missing after refresh')
                            break
                        tile = all_tiles[i]
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tile)
                        time.sleep(0.15)
                        if tile.is_displayed() and tile.is_enabled():
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", tile)
                            driver.execute_script("window.scrollBy(0, -120);")
                            time.sleep(0.12)
                            try:
                                tile.click()
                            except (StaleElementReferenceException, TimeoutException):
                                raise
                            except Exception:
                                try:
                                    ActionChains(driver).move_to_element(tile).pause(0.1).click().perform()
                                except Exception:
                                    try:
                                        driver.execute_script("arguments[0].click();", tile)
                                    except Exception:
                                        cell = tile.find_element(By.CSS_SELECTOR, '.rc-image-tile-target, .rc-imageselect-tile')
                                        driver.execute_script("arguments[0].click();", cell)
                            clicked = True
                            time.sleep(random.uniform(0.25, 0.6))
                            driver.switch_to.default_content()
                            break
                    except Exception as click_exc:
                        append_trace(result, round=round_no, note=f'click retry {attempt_click + 1} failed on tile {i}: {click_exc}')
                        driver.switch_to.default_content()
                        time.sleep(0.35)
                if not clicked:
                    append_trace(result, round=round_no, note=f'click failed on tile {i}')

            clicked_tile_indices.update(new_tiles_to_click)
            previous_urls = current_urls or previous_urls

            driver.switch_to.default_content()
            time.sleep(1.25)
            if _checkbox_verified(driver, timeout=4):
                result.verified = True
                result.token = _extract_token(driver)
                result.status = 'success'
                result.stage = 'verified'
                result.message = 'main checkbox verified after tile clicks'
                append_trace(result, round=round_no, checkbox_verified=True, note='checkbox verified after tile clicks')
                return result.to_dict()

            challenge_open = _challenge_still_open(driver)
            should_try_verify = True
            if tile_count == 9 and len(new_tiles_to_click) > 0:
                should_try_verify = False
                append_trace(result, round=round_no, note='3x3 dynamic board, wait for refresh before verify')

            if challenge_open and should_try_verify:
                try:
                    _switch_to_challenge_frame(driver, timeout=5)
                    verify_button = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.ID, 'recaptcha-verify-button')))
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", verify_button)
                    time.sleep(0.2)
                    try:
                        verify_button.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", verify_button)
                    driver.switch_to.default_content()
                    time.sleep(1.5)
                except Exception as verify_exc:
                    driver.switch_to.default_content()
                    append_trace(result, round=round_no, note=f'verify click not usable: {verify_exc}')
            elif not challenge_open:
                append_trace(result, round=round_no, note='challenge closed after clicks, skipping verify button')

            if _checkbox_verified(driver, timeout=4):
                result.verified = True
                result.token = _extract_token(driver)
                result.status = 'success'
                result.stage = 'verified'
                result.message = 'main checkbox verified'
                append_trace(result, round=round_no, checkbox_verified=True, note='main checkbox verified')
                return result.to_dict()

            if _challenge_still_open(driver):
                append_trace(result, round=round_no, note='challenge still open after verify path, continue next round')
                continue

            append_trace(result, round=round_no, note='challenge disappeared without verified checkbox')

        result.stage = 'incomplete'
        result.message = 'recaptcha_v2 did not reach verified state within current round budget'
        return result.to_dict()
    except Exception as exc:
        result.stage = 'exception'
        detail = str(exc)
        if isinstance(exc, WebDriverException):
            try:
                detail = f'{exc.__class__.__name__}: {exc.msg}'
            except Exception:
                detail = str(exc)
        result.message = detail
        append_trace(result, round=len(result.trace) + 1, note=f'exception: {detail}')
        try:
            crash_path = f'{screenshots_dir}/exception_page.png'
            driver.save_screenshot(crash_path)
            result.artifacts.append(crash_path)
        except Exception:
            pass
        try:
            page_path = f'{screenshots_dir}/exception_page.html'
            Path(page_path).write_text(driver.page_source, encoding='utf-8')
            result.artifacts.append(page_path)
        except Exception:
            pass
        return result.to_dict()
