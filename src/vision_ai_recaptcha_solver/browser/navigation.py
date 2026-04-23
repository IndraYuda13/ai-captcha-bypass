from __future__ import annotations

import time
from typing import Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def get_checkbox_iframe(driver: Any, timeout: float = 10.0):
    driver.switch_to.default_content()
    frame = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, "//iframe[@title='reCAPTCHA']")))
    return frame


def get_challenge_iframe(driver: Any, timeout: float = 10.0):
    end = time.time() + timeout
    while time.time() < end:
        driver.switch_to.default_content()
        frames = driver.find_elements(By.TAG_NAME, 'iframe')
        for frame in frames:
            title = (frame.get_attribute('title') or '').lower()
            src = (frame.get_attribute('src') or '').lower()
            if 'challenge' in title or 'bframe' in src or 'challenge expires in two minutes' in title:
                return frame
        time.sleep(0.1)
    return None


def switch_to_challenge_frame(driver: Any, timeout: float = 10.0):
    frame = get_challenge_iframe(driver, timeout)
    if frame is None:
        return None
    driver.switch_to.default_content()
    driver.switch_to.frame(frame)
    return frame


def is_solved(driver: Any, timeout: float = 4.0) -> bool:
    driver.switch_to.default_content()
    frame = get_checkbox_iframe(driver, timeout)
    driver.switch_to.frame(frame)
    try:
        anchor = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.ID, 'recaptcha-anchor')))
        return (anchor.get_attribute('aria-checked') or '').lower() == 'true'
    finally:
        driver.switch_to.default_content()


def get_target_keyword(driver: Any) -> str:
    selectors = [
        (By.CSS_SELECTOR, '.rc-imageselect-payload strong'),
        (By.CSS_SELECTOR, '.rc-imageselect-desc strong'),
        (By.CSS_SELECTOR, '.rc-imageselect-desc-no-canonical strong'),
    ]
    for by, selector in selectors:
        for elem in driver.find_elements(by, selector):
            text = (elem.text or '').strip().lower()
            if text:
                return text
    return ''


def get_challenge_title(driver: Any) -> str:
    try:
        elem = driver.find_element(By.CLASS_NAME, 'rc-imageselect-instructions')
        return (elem.text or '').strip()
    except Exception:
        return ''


def get_captcha_image_urls(driver: Any) -> list[str]:
    selectors = ['#rc-imageselect-target img', '.rc-image-tile-wrapper img', '.rc-imageselect-tile img']
    for selector in selectors:
        urls = []
        for elem in driver.find_elements(By.CSS_SELECTOR, selector):
            src = (elem.get_attribute('src') or '').strip()
            if src:
                urls.append(src)
        if urls:
            return urls
    return []
