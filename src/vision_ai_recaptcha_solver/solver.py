from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from PIL import Image
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from vision_ai_recaptcha_solver.browser.adapter import get_adapter
from vision_ai_recaptcha_solver.browser.factory import create_replicator_session, create_selenium_session
from vision_ai_recaptcha_solver.browser.session import BrowserSession
from vision_ai_recaptcha_solver.captcha.dynamic_handler import DynamicCaptchaHandler
from vision_ai_recaptcha_solver.captcha.selection_handler import SelectionCaptchaHandler
from vision_ai_recaptcha_solver.captcha.square_handler import SquareCaptchaHandler
from vision_ai_recaptcha_solver.config import SolverConfig
from vision_ai_recaptcha_solver.types import CaptchaType, RecaptchaTraceEntry


@dataclass
class RecaptchaV2Result:
    status: str
    verified: bool
    token: str = ''
    stage: str = 'init'
    message: str = ''
    trace: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'status': self.status,
            'verified': self.verified,
            'token': self.token,
            'stage': self.stage,
            'message': self.message,
            'trace': self.trace,
            'artifacts': self.artifacts,
        }


class RecaptchaSolver:
    def __init__(self, config: SolverConfig | None = None) -> None:
        self.config = config or SolverConfig()
        self.selection_handler = SelectionCaptchaHandler(self.config)
        self.dynamic_handler = DynamicCaptchaHandler(self.config)
        self.square_handler = SquareCaptchaHandler(self.config)

    def _unwrap_driver(self, driver_or_session: Any):
        if isinstance(driver_or_session, BrowserSession):
            return driver_or_session.browser, driver_or_session
        return driver_or_session, None

    def _get_adapter(self, browser: Any):
        return get_adapter(browser)

    def new_result(self) -> RecaptchaV2Result:
        return RecaptchaV2Result(status='error', verified=False, stage='init', message='recaptchav2 engine started')

    def append_trace(self, result: RecaptchaV2Result, **kwargs: Any) -> None:
        entry = RecaptchaTraceEntry(**kwargs)
        result.trace.append({
            'round': entry.round,
            'target': entry.target,
            'tile_count': entry.tile_count,
            'new_clicks': entry.new_clicks,
            'selected_tiles': entry.selected_tiles,
            'checkbox_verified': entry.checkbox_verified,
            'note': entry.note,
        })

    def checkbox_verified(self, driver: Any, timeout: int = 8) -> bool:
        return self._get_adapter(driver).get_checkbox_checked(driver, timeout=timeout)

    def wait_challenge_ready(self, driver: Any, timeout: int = 8):
        return self._get_adapter(driver).get_challenge_elements(driver, timeout=timeout)

    def extract_target_keyword_from_dom(self, driver: Any) -> str:
        return self._get_adapter(driver).get_target_keyword(driver, timeout=5)

    def is_verify_button_disabled(self, driver: Any, timeout: int = 2) -> bool:
        try:
            if self._get_adapter(driver).kind == 'selenium':
                frame = self._get_adapter(driver).get_challenge_frame(driver, timeout=timeout)
                if frame is None:
                    return False
                button = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.ID, 'recaptcha-verify-button')))
                disabled = button.get_attribute('disabled')
                driver.switch_to.default_content()
                return disabled is not None
            frame = self._get_adapter(driver).get_challenge_frame(driver, timeout=timeout)
            if not frame:
                return False
            button = frame.ele('#recaptcha-verify-button', timeout=1)
            if not button:
                return False
            return button.attr('disabled') is not None
        except Exception:
            try:
                driver.switch_to.default_content()
            except Exception:
                pass
            return False

    def wait_for_verify_result(self, driver: Any, timeout: float = 8.0) -> bool:
        start = time.time()
        time.sleep(0.1)
        while time.time() - start < timeout:
            if self.checkbox_verified(driver, timeout=1):
                return True
            if not self.is_verify_button_disabled(driver, timeout=1):
                time.sleep(0.2)
                return self.checkbox_verified(driver, timeout=2)
            time.sleep(0.1)
        return self.checkbox_verified(driver, timeout=2)

    def click_reload_button(self, driver: Any, timeout: int = 3) -> bool:
        try:
            if self._get_adapter(driver).kind == 'selenium':
                frame = self._get_adapter(driver).get_challenge_frame(driver, timeout=timeout)
                if frame is None:
                    return False
                button = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.ID, 'recaptcha-reload-button')))
                try:
                    button.click()
                except Exception:
                    driver.execute_script('arguments[0].click();', button)
                driver.switch_to.default_content()
                return True
            frame = self._get_adapter(driver).get_challenge_frame(driver, timeout=timeout)
            if not frame:
                return False
            button = frame.ele('#recaptcha-reload-button', timeout=1)
            if not button:
                return False
            button.click()
            return True
        except Exception:
            try:
                driver.switch_to.default_content()
            except Exception:
                pass
            return False

    def challenge_still_open(self, driver: Any) -> bool:
        try:
            return self._get_adapter(driver).has_challenge_open(driver, timeout=3)
        except Exception:
            return False

    def extract_token(self, driver: Any) -> str:
        driver.switch_to.default_content()
        try:
            token = driver.execute_script("""
            const el = document.getElementById('g-recaptcha-response');
            return el ? (el.value || '') : '';
            """)
            return (token or '').strip()
        except Exception:
            return ''

    def composite_dynamic_cells(self, base_grid: Image.Image, changed_cells: list[int], current_urls: list[str], cols: int) -> Image.Image:
        merged = base_grid.copy()
        width, height = merged.size
        rows = max(1, (len(current_urls) + cols - 1) // cols)
        tile_w = width // cols
        tile_h = height // rows
        for cell_num in changed_cells:
            idx = cell_num - 1
            if idx >= len(current_urls):
                continue
            try:
                resp = requests.get(current_urls[idx], timeout=10)
                resp.raise_for_status()
                patch = Image.open(BytesIO(resp.content)).convert('RGB')
            except Exception:
                continue
            patch = patch.resize((tile_w, tile_h))
            row = idx // cols
            col = idx % cols
            merged.paste(patch, (col * tile_w, row * tile_h))
        return merged

    def determine_captcha_type(self, driver: Any) -> CaptchaType:
        title = self._get_adapter(driver).get_challenge_title(driver).lower()
        if 'squares' in title:
            return CaptchaType.SQUARE_4X4
        if 'none' in title:
            return CaptchaType.DYNAMIC_3X3
        return CaptchaType.SELECTION_3X3

    def choose_handler(self, captcha_type: CaptchaType):
        if captcha_type == CaptchaType.DYNAMIC_3X3:
            return self.dynamic_handler
        if captcha_type == CaptchaType.SQUARE_4X4:
            return self.square_handler
        return self.selection_handler

    def click_selected_tiles(self, driver: Any, selected_tiles: list[int], result: RecaptchaV2Result, round_no: int) -> None:
        adapter = self._get_adapter(driver)
        for i in sorted(selected_tiles):
            clicked = False
            for attempt_click in range(3):
                try:
                    instruction, table = self.wait_challenge_ready(driver, timeout=5)
                    all_tiles = adapter.get_table_tiles(table)
                    if i >= len(all_tiles):
                        self.append_trace(result, round=round_no, note=f'tile index {i} missing after refresh')
                        break
                    tile = all_tiles[i]
                    if adapter.kind == 'selenium':
                        try:
                            ActionChains(driver).move_to_element(tile).pause(0.1).click().perform()
                            clicked = True
                        except Exception:
                            try:
                                driver.execute_script('arguments[0].click();', tile)
                                clicked = True
                            except Exception as exc:
                                self.append_trace(result, round=round_no, note=f'fallback click failed on tile {i}: {exc}')
                        driver.switch_to.default_content()
                    else:
                        try:
                            tile.click()
                            clicked = True
                        except Exception as exc:
                            self.append_trace(result, round=round_no, note=f'native drission click failed on tile {i}: {exc}')
                    if clicked:
                        time.sleep(random.uniform(0.25, 0.6))
                        break
                except Exception as click_exc:
                    self.append_trace(result, round=round_no, note=f'click retry {attempt_click + 1} failed on tile {i}: {click_exc}')
                    try:
                        driver.switch_to.default_content()
                    except Exception:
                        pass
                    time.sleep(0.35)
            if not clicked:
                self.append_trace(result, round=round_no, note=f'click failed on tile {i}')

    def solve(self, *, driver, provider='gemini-cli', model=None, max_rounds=5, screenshots_dir='screenshots', ask_recaptcha_instructions_with_provider=None, check_tile_for_object=None, debug=True, **kwargs: Any) -> dict[str, Any]:
        result = self.new_result()
        Path(screenshots_dir).mkdir(parents=True, exist_ok=True)
        result.stage = 'open_demo'
        driver, _session = self._unwrap_driver(driver)

        if ask_recaptcha_instructions_with_provider is None or check_tile_for_object is None:
            result.message = 'required callbacks missing for recaptchav2 engine'
            return result.to_dict()

        visionai_rank_grid_tiles = None
        if provider == 'visionai-local':
            try:
                from vision_ai_recaptcha_solver.visionai_subprocess import visionai_rank_grid_tiles_subprocess as _rank
                visionai_rank_grid_tiles = _rank
                result.trace.append({'round': 0, 'target': '', 'tile_count': 0, 'new_clicks': 0, 'selected_tiles': [], 'checkbox_verified': False, 'note': 'visionai subprocess helper ok'})
            except Exception as exc:
                visionai_rank_grid_tiles = None
                result.trace.append({'round': 0, 'target': '', 'tile_count': 0, 'new_clicks': 0, 'selected_tiles': [], 'checkbox_verified': False, 'note': f'visionai helper failed: {exc}'})

        try:
            adapter = self._get_adapter(driver)
            page_url = kwargs.get('page_url') or kwargs.get('pageUrl') or 'https://2captcha.com/demo/recaptcha-v2'
            adapter.open(driver, page_url)
            result.stage = 'bootstrap_checkbox'
            adapter.click_checkbox(driver, timeout=10)
            time.sleep(2)

            if self.checkbox_verified(driver, timeout=4):
                result.verified = True
                result.token = self.extract_token(driver)
                result.status = 'success'
                result.stage = 'verified'
                result.message = 'checkbox solved without image challenge'
                self.append_trace(result, round=0, checkbox_verified=True, note='checkbox solved directly')
                return result.to_dict()

            clicked_tile_indices = set()
            last_object_name = ''
            num_last_clicks = 0
            non_matching_cache = set()
            previous_urls: list[str] = []
            base_grid_img = None

            for attempt in range(max_rounds):
                round_no = attempt + 1
                result.stage = 'challenge_round'
                try:
                    instruction_element, table = self.wait_challenge_ready(driver, timeout=10)
                    time.sleep(0.35)
                    current_urls = self._get_adapter(driver).get_image_urls(driver, timeout=2)
                except Exception:
                    self.append_trace(result, round=round_no, note='no challenge iframe found, moving to final verification')
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

                object_name = self.extract_target_keyword_from_dom(driver)
                if not object_name and Path(instruction_path).exists():
                    object_name = ask_recaptcha_instructions_with_provider(instruction_path, provider, model)
                    self.append_trace(result, round=round_no, note=f'instruction fallback provider used: {provider}')
                if not object_name:
                    result.stage = 'keyword_missing'
                    result.message = 'failed to extract target keyword from challenge'
                    self.append_trace(result, round=round_no, note='target keyword missing from DOM and fallback')
                    return result.to_dict()

                is_new_object = object_name.lower() != last_object_name.lower()
                if is_new_object or num_last_clicks >= 3:
                    clicked_tile_indices = set()
                    last_object_name = object_name

                captcha_type = self.determine_captcha_type(driver)
                handler = self.choose_handler(captcha_type)
                handler_result = handler.solve(
                    result=result,
                    round_no=round_no,
                    driver=driver,
                    table=table,
                    adapter=self._get_adapter(driver),
                    provider=provider,
                    model=model,
                    object_name=object_name,
                    screenshots_dir=screenshots_dir,
                    current_urls=current_urls,
                    previous_urls=previous_urls,
                    append_trace=self.append_trace,
                    check_tile_for_object=check_tile_for_object,
                    visionai_rank_grid_tiles=visionai_rank_grid_tiles,
                    composite_dynamic_cells=self.composite_dynamic_cells,
                    base_grid_img=base_grid_img,
                    non_matching_cache=non_matching_cache,
                    By=By,
                    by_tag_td=(By.TAG_NAME, 'td'),
                )

                if captcha_type == CaptchaType.DYNAMIC_3X3:
                    selected_tiles, base_grid_img = handler_result
                else:
                    selected_tiles = handler_result

                current_attempt_tiles = set(selected_tiles)
                new_tiles_to_click = current_attempt_tiles - clicked_tile_indices
                num_last_clicks = len(new_tiles_to_click)
                self.append_trace(
                    result,
                    round=round_no,
                    target=object_name,
                    tile_count=len(self._get_adapter(driver).get_table_tiles(table)),
                    new_clicks=len(new_tiles_to_click),
                    selected_tiles=sorted(list(current_attempt_tiles)),
                    checkbox_verified=False,
                    note=f'round analyzed urls={len(current_urls)}'
                )

                if not current_attempt_tiles:
                    if self.click_reload_button(driver, timeout=3):
                        self.append_trace(result, round=round_no, target=object_name, note='no cells clicked, challenge reloaded to match reference behavior')
                        clicked_tile_indices = set()
                        previous_urls = []
                        base_grid_img = None
                        time.sleep(1.0)
                        continue
                    self.append_trace(result, round=round_no, target=object_name, note='no cells clicked and reload unavailable')

                self.click_selected_tiles(driver, list(new_tiles_to_click), result, round_no)
                clicked_tile_indices.update(new_tiles_to_click)

                driver.switch_to.default_content()
                time.sleep(1.25)
                if self.checkbox_verified(driver, timeout=4):
                    result.verified = True
                    result.token = self.extract_token(driver)
                    result.status = 'success'
                    result.stage = 'verified'
                    result.message = 'main checkbox verified after tile clicks'
                    self.append_trace(result, round=round_no, checkbox_verified=True, note='checkbox verified after tile clicks')
                    return result.to_dict()

                challenge_open = self.challenge_still_open(driver)
                if challenge_open:
                    try:
                        switch_to_challenge_frame(driver, timeout=5)
                        verify_button = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.ID, 'recaptcha-verify-button')))
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", verify_button)
                        time.sleep(0.2)
                        try:
                            verify_button.click()
                        except Exception:
                            driver.execute_script('arguments[0].click();', verify_button)
                        driver.switch_to.default_content()
                        if self.wait_for_verify_result(driver, timeout=8.0):
                            result.verified = True
                            result.token = self.extract_token(driver)
                            result.status = 'success'
                            result.stage = 'verified'
                            result.message = 'main checkbox verified after verify-button settle wait'
                            self.append_trace(result, round=round_no, checkbox_verified=True, note='main checkbox verified after verify settle wait')
                            return result.to_dict()
                        time.sleep(0.4)
                    except Exception as verify_exc:
                        driver.switch_to.default_content()
                        self.append_trace(result, round=round_no, note=f'verify click not usable: {verify_exc}')
                else:
                    self.append_trace(result, round=round_no, note='challenge closed after clicks, skipping verify button')

                if self.checkbox_verified(driver, timeout=4):
                    result.verified = True
                    result.token = self.extract_token(driver)
                    result.status = 'success'
                    result.stage = 'verified'
                    result.message = 'main checkbox verified'
                    self.append_trace(result, round=round_no, checkbox_verified=True, note='main checkbox verified')
                    return result.to_dict()

                if self.challenge_still_open(driver):
                    self.append_trace(result, round=round_no, note='challenge still open after verify settle wait, continue next round')
                    previous_urls = current_urls or previous_urls
                    continue

                previous_urls = current_urls or previous_urls
                self.append_trace(result, round=round_no, note='challenge disappeared without verified checkbox')

            result.stage = 'incomplete'
            result.message = 'recaptcha_v2 did not reach verified state within current round budget'
            return result.to_dict()
        except Exception as exc:
            result.stage = 'exception'
            result.message = str(exc)
            self.append_trace(result, round=len(result.trace) + 1, note=f'exception: {exc}')
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

    def solve_with_selenium_session(self, **kwargs: Any) -> dict[str, Any]:
        from vision_ai_recaptcha_solver.browser.factory import cleanup_selenium_session

        session = create_selenium_session()
        try:
            return self.solve(driver=session, **kwargs)
        finally:
            cleanup_selenium_session(session)

    def solve_with_replicator_session(
        self,
        *,
        website_key: str,
        website_url: str,
        is_invisible: bool = False,
        action: str | None = None,
        is_enterprise: bool = False,
        api_domain: str = 'google.com',
        bypass_domain_check: bool = True,
        use_ssl: bool = True,
        cookies: list[dict[str, Any]] | None = None,
        user_agent: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        session = create_replicator_session(
            website_key=website_key,
            website_url=website_url,
            is_invisible=is_invisible,
            action=action,
            is_enterprise=is_enterprise,
            api_domain=api_domain,
            bypass_domain_check=bypass_domain_check,
            use_ssl=use_ssl,
            cookies=cookies,
            user_agent=user_agent,
            headless=self.config.headless,
            download_dir=str(self.config.download_dir),
            server_port=self.config.server_port,
            proxy=self.config.proxy,
            browser_path=self.config.browser_path,
            persist_html=self.config.persist_html,
        )
        try:
            return self.solve(driver=session, page_url=website_url, **kwargs)
        finally:
            session.close()
