from __future__ import annotations

import time
from typing import Any


class BrowserAdapter:
    kind = 'base'

    def open(self, browser: Any, url: str) -> None:
        raise NotImplementedError

    def get_challenge_title(self, browser: Any) -> str:
        raise NotImplementedError

    def get_checkbox_checked(self, browser: Any, timeout: float = 8.0) -> bool:
        raise NotImplementedError

    def click_checkbox(self, browser: Any, timeout: float = 10.0) -> None:
        raise NotImplementedError

    def has_challenge_open(self, browser: Any, timeout: float = 5.0) -> bool:
        raise NotImplementedError

    def get_challenge_frame(self, browser: Any, timeout: float = 5.0):
        raise NotImplementedError

    def get_challenge_elements(self, browser: Any, timeout: float = 8.0):
        raise NotImplementedError

    def get_target_keyword(self, browser: Any, timeout: float = 5.0) -> str:
        raise NotImplementedError

    def get_table_tiles(self, table: Any) -> list[Any]:
        raise NotImplementedError

    def get_image_urls(self, browser: Any, timeout: float = 5.0) -> list[str]:
        raise NotImplementedError

    def capture_element(self, element: Any, path: str) -> None:
        raise NotImplementedError


class SeleniumAdapter(BrowserAdapter):
    kind = 'selenium'

    def open(self, browser: Any, url: str) -> None:
        browser.get(url)

    def get_challenge_title(self, browser: Any) -> str:
        try:
            elem = browser.find_element('class name', 'rc-imageselect-instructions')
            return (elem.text or '').strip()
        except Exception:
            return ''

    def get_checkbox_checked(self, browser: Any, timeout: float = 8.0) -> bool:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        browser.switch_to.default_content()
        frame = WebDriverWait(browser, timeout).until(EC.presence_of_element_located((By.XPATH, "//iframe[@title='reCAPTCHA']")))
        browser.switch_to.frame(frame)
        try:
            anchor = WebDriverWait(browser, timeout).until(EC.presence_of_element_located((By.ID, 'recaptcha-anchor')))
            return (anchor.get_attribute('aria-checked') or '').lower() == 'true'
        finally:
            browser.switch_to.default_content()

    def click_checkbox(self, browser: Any, timeout: float = 10.0) -> None:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        browser.switch_to.default_content()
        frame = WebDriverWait(browser, timeout).until(EC.presence_of_element_located((By.XPATH, "//iframe[@title='reCAPTCHA']")))
        browser.switch_to.frame(frame)
        checkbox = WebDriverWait(browser, timeout).until(EC.element_to_be_clickable((By.CLASS_NAME, 'recaptcha-checkbox-border')))
        checkbox.click()
        browser.switch_to.default_content()

    def has_challenge_open(self, browser: Any, timeout: float = 5.0) -> bool:
        from selenium.webdriver.common.by import By

        end = time.time() + timeout
        while time.time() < end:
            browser.switch_to.default_content()
            frames = browser.find_elements(By.TAG_NAME, 'iframe')
            for frame in frames:
                title = (frame.get_attribute('title') or '').lower()
                src = (frame.get_attribute('src') or '').lower()
                if 'challenge' in title or 'bframe' in src or 'challenge expires in two minutes' in title:
                    return True
            time.sleep(0.1)
        return False

    def get_challenge_frame(self, browser: Any, timeout: float = 5.0):
        from selenium.webdriver.common.by import By

        end = time.time() + timeout
        while time.time() < end:
            browser.switch_to.default_content()
            frames = browser.find_elements(By.TAG_NAME, 'iframe')
            for frame in frames:
                title = (frame.get_attribute('title') or '').lower()
                src = (frame.get_attribute('src') or '').lower()
                if 'challenge' in title or 'bframe' in src or 'challenge expires in two minutes' in title:
                    browser.switch_to.frame(frame)
                    return frame
            time.sleep(0.1)
        return None

    def get_challenge_elements(self, browser: Any, timeout: float = 8.0):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        self.get_challenge_frame(browser, timeout=timeout)
        table = WebDriverWait(browser, timeout).until(EC.presence_of_element_located((By.XPATH, "//table[contains(@class, 'rc-imageselect-table')]")))
        instruction = WebDriverWait(browser, timeout).until(EC.presence_of_element_located((By.CLASS_NAME, 'rc-imageselect-instructions')))
        return instruction, table

    def get_target_keyword(self, browser: Any, timeout: float = 5.0) -> str:
        from selenium.webdriver.common.by import By

        self.get_challenge_frame(browser, timeout=timeout)
        selectors = [
            (By.CSS_SELECTOR, '.rc-imageselect-payload strong'),
            (By.CSS_SELECTOR, '.rc-imageselect-desc strong'),
            (By.CSS_SELECTOR, '.rc-imageselect-desc-no-canonical strong'),
        ]
        for by, selector in selectors:
            try:
                elems = browser.find_elements(by, selector)
                for elem in elems:
                    text = (elem.text or '').strip().lower()
                    if text:
                        return text
            except Exception:
                continue
        return ''

    def get_table_tiles(self, table: Any) -> list[Any]:
        return table.find_elements('tag name', 'td')

    def get_image_urls(self, browser: Any, timeout: float = 5.0) -> list[str]:
        selectors = ['#rc-imageselect-target img', '.rc-image-tile-wrapper img', '.rc-imageselect-tile img']
        for selector in selectors:
            urls = []
            for elem in browser.find_elements('css selector', selector):
                src = (elem.get_attribute('src') or '').strip()
                if src:
                    urls.append(src)
            if urls:
                return urls
        return []

    def capture_element(self, element: Any, path: str) -> None:
        element.screenshot(path)


class DrissionAdapter(BrowserAdapter):
    kind = 'drission'

    def _tab(self, browser: Any):
        if hasattr(browser, 'latest_tab'):
            return browser.latest_tab
        if hasattr(browser, 'tab'):
            return browser.tab
        return browser

    def _frame_candidates(self, browser: Any):
        tab = self._tab(browser)
        return tab.eles('t:iframe')

    def _checkbox_frame(self, browser: Any, timeout: float = 5.0):
        tab = self._tab(browser)
        deadline = time.time() + timeout
        while time.time() < deadline:
            for iframe in self._frame_candidates(browser):
                title = (iframe.attr('title') or '').lower()
                if 'recaptcha' in title and 'challenge' not in title:
                    try:
                        return tab.get_frame(iframe)
                    except Exception:
                        continue
            time.sleep(0.2)
        return None

    def _challenge_frame(self, browser: Any, timeout: float = 5.0):
        tab = self._tab(browser)
        deadline = time.time() + timeout
        while time.time() < deadline:
            for iframe in self._frame_candidates(browser):
                title = (iframe.attr('title') or '').lower()
                src = (iframe.attr('src') or '').lower()
                if 'challenge' in title or 'bframe' in src or 'challenge expires in two minutes' in title:
                    try:
                        return tab.get_frame(iframe)
                    except Exception:
                        continue
            time.sleep(0.2)
        return None

    def open(self, browser: Any, url: str) -> None:
        self._tab(browser).get(url)

    def get_challenge_title(self, browser: Any) -> str:
        frame = self._challenge_frame(browser, timeout=5.0)
        if not frame:
            return ''
        try:
            el = frame.ele('.rc-imageselect-instructions', timeout=2)
            return (el.text or '').strip() if el else ''
        except Exception:
            return ''

    def get_checkbox_checked(self, browser: Any, timeout: float = 8.0) -> bool:
        frame = self._checkbox_frame(browser, timeout=timeout)
        if not frame:
            return False
        try:
            anchor = frame.ele('#recaptcha-anchor', timeout=2)
            if not anchor:
                return False
            return ((anchor.attr('aria-checked') or '').lower() == 'true')
        except Exception:
            return False

    def click_checkbox(self, browser: Any, timeout: float = 10.0) -> None:
        frame = self._checkbox_frame(browser, timeout=timeout)
        if not frame:
            raise RuntimeError('failed to locate checkbox frame in drission adapter')
        box = frame.ele('.recaptcha-checkbox-border', timeout=3)
        if not box:
            raise RuntimeError('failed to locate checkbox element in drission adapter')
        box.click()

    def has_challenge_open(self, browser: Any, timeout: float = 5.0) -> bool:
        return self._challenge_frame(browser, timeout=timeout) is not None

    def get_challenge_frame(self, browser: Any, timeout: float = 5.0):
        return self._challenge_frame(browser, timeout=timeout)

    def get_challenge_elements(self, browser: Any, timeout: float = 8.0):
        frame = self._challenge_frame(browser, timeout=timeout)
        if not frame:
            raise RuntimeError('challenge frame not found in drission adapter')
        instruction = frame.ele('.rc-imageselect-instructions', timeout=2)
        table = frame.ele('xpath://table[contains(@class, "rc-imageselect-table")]', timeout=2)
        if not instruction or not table:
            raise RuntimeError('challenge elements not found in drission adapter')
        return instruction, table

    def get_target_keyword(self, browser: Any, timeout: float = 5.0) -> str:
        frame = self._challenge_frame(browser, timeout=timeout)
        if not frame:
            return ''
        selectors = [
            '.rc-imageselect-payload strong',
            '.rc-imageselect-desc strong',
            '.rc-imageselect-desc-no-canonical strong',
            'tag:strong',
        ]
        for selector in selectors:
            try:
                el = frame.ele(selector, timeout=1)
                if el and (el.text or '').strip():
                    return (el.text or '').strip().lower()
            except Exception:
                continue
        return ''

    def get_table_tiles(self, table: Any) -> list[Any]:
        for selector in ['tag:td', 'css:td', '.rc-image-tile-wrapper']:
            try:
                tiles = table.eles(selector)
                if tiles:
                    return list(tiles)
            except Exception:
                continue
        return []

    def get_image_urls(self, browser: Any, timeout: float = 5.0) -> list[str]:
        frame = self._challenge_frame(browser, timeout=timeout)
        if not frame:
            return []
        for selector in ['tag:img', '#rc-imageselect-target img', '.rc-image-tile-wrapper img', '.rc-imageselect-tile img']:
            try:
                imgs = frame.eles(selector)
                urls = [src for src in [((img.attr('src') or '').strip()) for img in imgs] if src]
                if urls:
                    return urls
            except Exception:
                continue
        return []

    def capture_element(self, element: Any, path: str) -> None:
        element.get_screenshot(path=path)


def get_adapter(browser: Any) -> BrowserAdapter:
    if hasattr(browser, 'get') and hasattr(browser, 'switch_to'):
        return SeleniumAdapter()
    return DrissionAdapter()
