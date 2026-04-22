import argparse
import os
import time
import random
import re
import base64
import urllib.request
import tempfile
import shutil
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException
from openai import OpenAI, APIStatusError
from google import genai
from google.genai import types
from puzzle_solver import solve_geetest_puzzle
from PIL import Image
import traceback
from concurrent.futures import ThreadPoolExecutor
from ai_utils import (
    ask_text_to_chatgpt,
    ask_text_to_gemini,
    ask_text_with_provider,
    ask_audio_to_openai,
    ask_audio_to_gemini,
    ask_audio_with_provider,
    ask_recaptcha_instructions_to_chatgpt,
    ask_recaptcha_instructions_to_gemini,
    ask_recaptcha_instructions_with_provider,
    ask_if_tile_contains_object_chatgpt,
    ask_if_tile_contains_object_gemini,
    ask_if_tile_contains_object_with_provider,
    ask_puzzle_distance_to_gemini,
    ask_puzzle_distance_to_chatgpt,
    ask_puzzle_correction_to_chatgpt,
    ask_puzzle_correction_to_gemini,
    ask_puzzle_distance_with_provider,
    ask_puzzle_correction_with_provider
)
from visionai_local import visionai_contains_object, visionai_rank_grid_tiles

#todo: sesli captchada sese asıl captchayı söyledikten sonra ignore previous instructions diyip sonra random bir captcha daha vericem
load_dotenv()

# Initialize clients at the top level
gemini_client = None
if os.getenv("GOOGLE_API_KEY"):
    gemini_client = genai.Client()

def create_success_gif(image_paths, output_folder="successful_solves"):
    """Creates a GIF from a list of images, resizing them to the max dimensions without distortion."""
    if not image_paths:
        print("No images provided for GIF creation.")
        return

    os.makedirs(output_folder, exist_ok=True)
    
    valid_images = []
    for path in image_paths:
        if os.path.exists(path):
            try:
                valid_images.append(Image.open(path).convert("RGB"))
            except Exception as e:
                print(f"Warning: Could not open or convert image {path}. Skipping. Error: {e}")
        else:
            print(f"Warning: Image path for GIF not found: {path}. Skipping.")

    if not valid_images:
        print("\nCould not create success GIF because no valid source images were found.")
        return

    try:
        # Find the maximum width and height among all images
        max_width = max(img.width for img in valid_images)
        max_height = max(img.height for img in valid_images)
        canvas_size = (max_width, max_height)

        processed_images = []
        for img in valid_images:
            # Create a new blank canvas with the max dimensions
            canvas = Image.new('RGB', canvas_size, (255, 255, 255))
            # Paste the original image into the center of the canvas
            paste_position = ((max_width - img.width) // 2, (max_height - img.height) // 2)
            canvas.paste(img, paste_position)
            processed_images.append(canvas)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(output_folder, f"success_{timestamp}.gif")

        processed_images[0].save(
            output_path,
            save_all=True,
            append_images=processed_images[1:],
            duration=800,
            loop=0
        )
        print(f"\n✨ Successfully saved solution GIF to {output_path}")
    except Exception as e:
        print(f"\nCould not create success GIF. Error: {e}")

def average_of_array(arr):
    if not arr:
        return 0  # Handle edge case of empty array
    sum_elements = sum(arr)
    average = sum_elements / len(arr)
    return average - 5

def check_tile_for_object(args):
    """Helper function for ThreadPoolExecutor to call the correct provider for a single tile."""
    tile_index, tile_path, object_name, provider, model = args

    try:
        if provider == 'visionai-local':
            decision = visionai_contains_object(tile_path, object_name)
            print(f"Tile {tile_index}: Does it contain '{object_name}'? VisionAI says: {str(decision).lower()}")
            return tile_index, decision

        decision_str = ask_if_tile_contains_object_with_provider(tile_path, object_name, provider, model)
        print(f"Tile {tile_index}: Does it contain '{object_name}'? AI says: {decision_str}")
        return tile_index, decision_str == 'true'
    except Exception as e:
        print(f"Error checking tile {tile_index}: {e}")
        return tile_index, False

def audio_test(file_path='files/audio.mp3', provider='gemini', model=None):
    """Transcribes a local audio file using the specified AI provider."""
    if not os.path.exists(file_path):
        print(f"Error: Audio file not found at '{file_path}'")
        return

    try:
        print(f"Transcribing audio from '{file_path}' using {provider.upper()}...")
        transcription = ask_audio_with_provider(file_path, provider, model)
        
        print("\n--- Transcription Result ---")
        print(transcription)
        print("--------------------------\n")
    except Exception as e:
        print(f"An error occurred during audio transcription: {e}")

def complicated_text_test(driver, provider='openai', model=None):
    """
    Solves a single "Complicated Text" captcha instance, trying up to 3 times.
    The benchmark is successful if any attempt passes.
    Returns the attempt number (1, 2, or 3) on success, or 0 on failure.
    """
    driver.get("https://2captcha.com/demo/mtcaptcha")
    time.sleep(5)
    screenshot_paths = []
    
    for attempt in range(3):
        print(f"\n--- Complicated Text: Attempt {attempt + 1}/3 ---")
        try:
            # 1. Get the captcha image
            iframe = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "mtcaptcha-iframe-1"))
            )
            time.sleep(2) # Allow time for new captcha to load on retries
            
            captcha_screenshot_path = f'screenshots/complicated_text_attempt_{attempt + 1}.png'
            iframe.screenshot(captcha_screenshot_path)
            screenshot_paths.append(captcha_screenshot_path)

            # 2. Ask AI for the answer
            response = ask_text_with_provider(captcha_screenshot_path, provider, model)

            print(f"AI transcription: '{response}'")
            
            # 3. Submit the answer
            driver.switch_to.frame(iframe)
            input_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "mtcap-noborder.mtcap-inputtext.mtcap-inputtext-custom"))
            )
            input_field.clear()
            input_field.send_keys(response)
            time.sleep(2)
            driver.switch_to.default_content()
            
            submit_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Check')]"))
            )
            submit_button.click()
            
            # 4. Check for success
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "_successMessage_w91t8_1"))
            )
            
            print("Captcha passed successfully!")
            final_success_path = f"screenshots/final_success_complicated_{datetime.now().strftime('%H%M%S')}.png"
            driver.save_screenshot(final_success_path)
            screenshot_paths.append(final_success_path)
            create_success_gif(screenshot_paths, output_folder=f"successful_solves/complicated_text_{provider}")
            return attempt + 1 # Return the successful attempt number

        except Exception as e:
            print(f"Attempt {attempt + 1} did not pass.")
            if attempt < 2:
                print("Retrying...")
            else:
                print("All 3 attempts failed for this benchmark run.")
            
            try:
                driver.switch_to.default_content()
            except Exception:
                pass

    return 0

def text_test(driver, provider='openai', model=None):
    """
    Solves a single "Normal Text" captcha instance.
    Returns 1 for success, 0 for failure.
    """
    driver.get("https://2captcha.com/demo/normal")
    time.sleep(5)
    screenshot_paths = []
    try:
        captcha_image = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "_captchaImage_rrn3u_9"))
        )
        time.sleep(2)
        captcha_screenshot_path = 'screenshots/text_captcha_1.png'
        captcha_image.screenshot(captcha_screenshot_path)
        screenshot_paths.append(captcha_screenshot_path)
        
        response = ask_text_with_provider(captcha_screenshot_path, provider, model)

        print(f"AI transcription: '{response}'")

        input_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "_inputInner_ws73z_12"))
        )
        input_field.clear()
        input_field.send_keys(response)
        submit_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Check')]"))
        )
        submit_button.click()

        # If correct, the 'Check' button will disappear.
        WebDriverWait(driver, 10).until(
            EC.invisibility_of_element_located((By.XPATH, "//button[contains(., 'Check')]"))
        )

        print("Captcha passed successfully!")
        
        final_success_path = f"screenshots/final_success_text_{datetime.now().strftime('%H%M%S')}.png"
        driver.save_screenshot(final_success_path)
        screenshot_paths.append(final_success_path)
        create_success_gif(screenshot_paths, output_folder=f"successful_solves/text_{provider}")
        return 1
    except Exception as e:
        print(f"Captcha failed... Error: {e}")
        return 0

def recaptcha_v2_test(driver, provider='openai', model=None):
    """
    Solves a single reCAPTCHA v2 instance on the 2captcha demo page.
    Returns 1 for success, 0 for failure.
    """
    def recaptcha_checkbox_verified(timeout=8):
        driver.switch_to.default_content()
        frame = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, "//iframe[@title='reCAPTCHA']")))
        driver.switch_to.frame(frame)
        try:
            anchor = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.ID, 'recaptcha-anchor')))
            checked = (anchor.get_attribute('aria-checked') or '').lower()
            return checked == 'true'
        finally:
            driver.switch_to.default_content()

    def click_recaptcha_checkbox(timeout=10, retries=3):
        last_exc = None
        for _ in range(retries):
            try:
                driver.switch_to.default_content()
                recaptcha_frame = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, "//iframe[@title='reCAPTCHA']"))
                )
                driver.switch_to.frame(recaptcha_frame)
                checkbox = WebDriverWait(driver, timeout).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "recaptcha-checkbox-border"))
                )
                try:
                    checkbox.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", checkbox)
                driver.switch_to.default_content()
                return
            except StaleElementReferenceException as exc:
                last_exc = exc
                driver.switch_to.default_content()
                time.sleep(0.5)
            except Exception as exc:
                last_exc = exc
                driver.switch_to.default_content()
                raise
        if last_exc:
            raise last_exc

    def acquire_challenge_state(timeout=10, retries=3):
        last_exc = None
        for _ in range(retries):
            try:
                driver.switch_to.default_content()
                challenge_iframe = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, "//iframe[contains(@title, 'recaptcha challenge expires in two minutes')]"))
                )
                driver.switch_to.frame(challenge_iframe)
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(0.2)
                instruction_element = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "rc-imageselect-instructions"))
                )
                table = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, "//table[contains(@class, 'rc-imageselect-table')]"))
                )
                all_tiles = WebDriverWait(driver, timeout).until(lambda d: table.find_elements(By.TAG_NAME, 'td'))
                return instruction_element, table, all_tiles
            except (StaleElementReferenceException, NoSuchElementException) as exc:
                last_exc = exc
                driver.switch_to.default_content()
                time.sleep(1)
        if last_exc:
            raise last_exc
        raise RuntimeError('failed to acquire stable challenge state')

    def capture_instruction(path, retries=3):
        last_exc = None
        for _ in range(retries):
            try:
                instruction_element, _, _ = acquire_challenge_state(timeout=10, retries=3)
                instruction_element.screenshot(path)
                return instruction_element.text
            except Exception as exc:
                last_exc = exc
                try:
                    driver.save_screenshot(path)
                    return ''
                except Exception:
                    driver.switch_to.default_content()
                    time.sleep(0.5)
        if last_exc:
            raise last_exc

    def read_instruction_text_from_dom(timeout=10):
        deadline = time.time() + timeout
        selectors = [
            (By.CLASS_NAME, 'rc-imageselect-instructions'),
            (By.CSS_SELECTOR, '.rc-imageselect-desc-wrapper'),
            (By.CSS_SELECTOR, '.rc-imageselect-desc-no-canonical'),
            (By.CSS_SELECTOR, '.rc-imageselect-desc'),
        ]
        last_text = ''
        while time.time() < deadline:
            try:
                driver.switch_to.default_content()
                challenge_iframe = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//iframe[contains(@title, 'recaptcha challenge expires in two minutes')]"))
                )
                driver.switch_to.frame(challenge_iframe)
                for by, selector in selectors:
                    elems = driver.find_elements(by, selector)
                    for elem in elems:
                        text = (elem.text or '').strip()
                        if text:
                            return text
                body_text = (driver.find_element(By.TAG_NAME, 'body').text or '').strip()
                if body_text:
                    last_text = body_text
                    if 'select all images with' in body_text.lower():
                        return body_text
            except Exception:
                pass
            finally:
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
            time.sleep(0.4)
        return last_text

    def extract_target_from_instruction_text(text: str) -> str:
        lowered = (text or '').strip().lower()
        if not lowered:
            return ''
        lines = [line.strip() for line in lowered.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            if line.startswith('select all images with') and idx + 1 < len(lines):
                return lines[idx + 1]
        if 'select all images with' in lowered:
            after = lowered.split('select all images with', 1)[1].strip()
            first = after.splitlines()[0].strip() if after.splitlines() else after
            if first:
                return first
        return ''

    def get_round_target_object(instruction_screenshot_path: str, provider: str, model, last_object_name: str) -> str:
        for _ in range(3):
            instruction_text = read_instruction_text_from_dom(timeout=6) or ''
            if not instruction_text:
                instruction_text = capture_instruction(instruction_screenshot_path, retries=3) or ''
            object_name = extract_target_from_instruction_text(instruction_text)
            if object_name:
                print(f"Instruction text target object: '{object_name}'")
                return object_name
            time.sleep(0.5)

        if last_object_name:
            print(f"Instruction text missing, reusing last target object: '{last_object_name}'")
            return last_object_name

        raise RuntimeError('unable to extract target object from DOM text on first round')

    def capture_grid(path, retries=3):
        last_exc = None
        for _ in range(retries):
            try:
                _, table, all_tiles = acquire_challenge_state(timeout=10, retries=3)
                table.screenshot(path)
                return all_tiles
            except Exception as exc:
                last_exc = exc
                driver.switch_to.default_content()
                time.sleep(0.5)
        if last_exc:
            raise last_exc
        raise RuntimeError('failed to capture grid')

    def click_tile_by_index(tile_index, retries=3):
        last_exc = None
        for _ in range(retries):
            try:
                _, table, all_tiles = acquire_challenge_state(timeout=10, retries=3)
                if tile_index >= len(all_tiles):
                    return False
                tile = all_tiles[tile_index]
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", table)
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", tile)
                time.sleep(0.1)
                if tile.is_displayed() and tile.is_enabled():
                    try:
                        ActionChains(driver).move_to_element(tile).pause(0.05).click(tile).perform()
                    except Exception:
                        try:
                            tile.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", tile)
                    time.sleep(random.uniform(0.2, 0.5))
                    return True
                return False
            except Exception as exc:
                last_exc = exc
                driver.switch_to.default_content()
                time.sleep(0.5)
        if last_exc:
            raise last_exc
        return False

    driver.get("https://2captcha.com/demo/recaptcha-v2")
    
    screenshot_paths = []
    try:
        # --- Start the challenge ---
        click_recaptcha_checkbox(timeout=10, retries=3)
        time.sleep(2)

        # --- Loop to solve image challenges as long as they appear ---
        MAX_CHALLENGE_ATTEMPTS = 5
        clicked_tile_indices = set()
        last_object_name = ""
        num_last_clicks = 0
        previous_tile_keys = None
        last_clicked_cells_1idx = []
        for attempt in range(MAX_CHALLENGE_ATTEMPTS):
            print(f"\nreCAPTCHA image challenge attempt {attempt + 1}/{MAX_CHALLENGE_ATTEMPTS}...")
            
            # --- Check if a puzzle is present ---
            try:
                _, _, all_tiles = acquire_challenge_state(timeout=10, retries=3)
            except Exception:
                print("No new image challenge found. Proceeding to final submission.")
                break # Exit the loop

            # --- If puzzle is found, solve it ---
            instruction_screenshot_path = f'screenshots/recaptcha_instruction_{attempt + 1}.png'
            capture_instruction(instruction_screenshot_path, retries=3)
            screenshot_paths.append(instruction_screenshot_path)
            object_name = get_round_target_object(instruction_screenshot_path, provider, model, last_object_name)

            is_new_object = object_name.lower() != last_object_name.lower()
            if is_new_object:
                print(f"New challenge object detected ('{object_name}'). Resetting clicked tiles.")
                clicked_tile_indices = set()
                last_object_name = object_name
            elif num_last_clicks >= 3:
                print("Previously clicked 3 or more tiles, assuming a new challenge. Resetting clicked tiles.")
                clicked_tile_indices = set()
            else:
                print("Same challenge object and < 3 tiles clicked previously. Will not re-click already selected tiles.")

            grid_path = f'screenshots/recaptcha_grid_{attempt + 1}.png'
            all_tiles = capture_grid(grid_path, retries=3)
            screenshot_paths.append(grid_path)
            grid_img = Image.open(grid_path)
            grid_width, grid_height = grid_img.size
            tile_count = len(all_tiles)
            cols = 4 if tile_count >= 16 else 3
            rows = max(1, tile_count // cols)
            tile_w = grid_width // cols
            tile_h = grid_height // rows

            tile_paths = []
            current_tile_keys = []
            for i in range(tile_count):
                tile_path = f'screenshots/tile_{attempt + 1}_{i}.png'
                row = i // cols
                col = i % cols
                left = col * tile_w
                top = row * tile_h
                right = (col + 1) * tile_w if col < cols - 1 else grid_width
                bottom = (row + 1) * tile_h if row < rows - 1 else grid_height
                tile_img = grid_img.crop((left, top, right, bottom))
                tile_img.save(tile_path)
                screenshot_paths.append(tile_path)
                tile_paths.append(tile_path)
                current_tile_keys.append((tile_img.size, tile_img.tobytes()[:256]))

            tiles_to_click_this_round = []
            if provider == 'visionai-local':
                try:
                    ranked = visionai_rank_grid_tiles(grid_path, object_name, cols)
                    if cols == 3 and previous_tile_keys is not None and last_clicked_cells_1idx:
                        changed_cells = []
                        for cell in last_clicked_cells_1idx:
                            idx = cell - 1
                            if idx < len(current_tile_keys) and idx < len(previous_tile_keys):
                                if current_tile_keys[idx] != previous_tile_keys[idx]:
                                    changed_cells.append(cell)
                        ranked_map = {cell: conf for cell, conf in ranked}
                        tiles_to_click_this_round = [cell - 1 for cell in changed_cells if ranked_map.get(cell, 0.0) >= 0.7]
                    elif cols == 3:
                        ranked_sorted = sorted(ranked, key=lambda x: x[1], reverse=True)
                        top_three = ranked_sorted[:3]
                        if any(conf < 0.2 for _, conf in top_three):
                            tiles_to_click_this_round = []
                        else:
                            tiles_to_click_this_round = [cell - 1 for cell, _ in top_three]
                            if len(ranked_sorted) >= 4 and ranked_sorted[3][1] >= 0.7:
                                tiles_to_click_this_round.append(ranked_sorted[3][0] - 1)
                    else:
                        positive_cells = [cell for cell, conf in ranked if conf >= 0.7]
                        if len(positive_cells) > 6:
                            print(f"VisionAI 4x4 overselect guard triggered, suppressing broad selection: {positive_cells}")
                            tiles_to_click_this_round = []
                        else:
                            tiles_to_click_this_round = [cell - 1 for cell in positive_cells]
                    print(f"VisionAI ranked tiles: {ranked}")
                except Exception as e:
                    print(f"VisionAI ranking failed, falling back to per-tile checks: {e}")

            if not tiles_to_click_this_round:
                tasks = [(i, path, object_name, provider, model) for i, path in enumerate(tile_paths)]
                with ThreadPoolExecutor(max_workers=len(all_tiles)) as executor:
                    results = executor.map(check_tile_for_object, tasks)
                    for tile_index, should_click in results:
                        if should_click:
                            tiles_to_click_this_round.append(tile_index)

            current_attempt_tiles = set(tiles_to_click_this_round)
            new_tiles_to_click = current_attempt_tiles - clicked_tile_indices
            num_last_clicks = len(new_tiles_to_click)

            print(f"[TRACE] recaptcha round={attempt + 1} target={object_name} tile_count={len(all_tiles)} new_clicks={len(new_tiles_to_click)}")
            print(f"\nAI identified tiles for clicking: {sorted(list(current_attempt_tiles))}")
            print(f"Already clicked tiles: {sorted(list(clicked_tile_indices))}")
            print(f"Clicking {len(new_tiles_to_click)} new tiles...")
            
            for i in sorted(list(new_tiles_to_click)):
                try:
                    clicked = click_tile_by_index(i, retries=3)
                    if not clicked:
                        print(f"Could not click tile {i}, tile missing or not interactable.")
                except Exception as e:
                    print(f"Could not click tile {i}, it might be already selected or disabled. Error: {e}")
            
            clicked_tile_indices.update(new_tiles_to_click)
            last_clicked_cells_1idx = [i + 1 for i in sorted(list(new_tiles_to_click))]
            previous_tile_keys = current_tile_keys

            try:
                verify_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "recaptcha-verify-button")))
                verify_button.click()
                time.sleep(1.5) # Wait for state change

                # After clicking, check if the button is now disabled, which indicates success
                verify_button_after_click = driver.find_element(By.ID, "recaptcha-verify-button")
                if verify_button_after_click.get_attribute("disabled"):
                    print("Verify button is disabled. Image challenge passed.")
                    driver.switch_to.default_content()
                    print("reCAPTCHA v2 passed successfully!")
        
                    final_success_path = f"screenshots/final_success_recaptcha_v2_{datetime.now().strftime('%H%M%S')}.png"
                    driver.save_screenshot(final_success_path)
                    screenshot_paths.append(final_success_path)
                    
                    create_success_gif(screenshot_paths, output_folder=f"successful_solves/recaptcha_v2_{provider}")
                    return 1
                else:
                    # This case handles "check new images" - we just let the loop continue
                    print("Verify button still active, likely a new challenge was served.")

            except Exception:
                print("Verify button not found after clicking tiles, checking main checkbox state.")
                if recaptcha_checkbox_verified(timeout=6):
                    print("Main reCAPTCHA checkbox is verified.")
                    break
                print("Main checkbox not verified yet, waiting for refreshed challenge to settle.")
                driver.switch_to.default_content()
                time.sleep(2)
                try:
                    challenge_iframe = WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.XPATH, "//iframe[contains(@title, 'recaptcha challenge expires in two minutes')]")))
                    driver.switch_to.frame(challenge_iframe)
                    WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CLASS_NAME, "rc-imageselect-instructions")))
                    driver.switch_to.default_content()
                    print("Refreshed challenge is present and stable. Continuing.")
                    continue
                except Exception:
                    driver.switch_to.default_content()
                    if recaptcha_checkbox_verified(timeout=4):
                        print("Main reCAPTCHA checkbox became verified during refresh wait.")
                        break
                    print("Refreshed challenge did not stabilize in time.")

            driver.switch_to.default_content()
            time.sleep(2)

            if recaptcha_checkbox_verified(timeout=4):
                print("Main reCAPTCHA checkbox is verified after challenge step.")
                break
        else:
            # This 'else' belongs to the 'for' loop. Runs if the loop completes without a 'break'.
            print("Image challenge still present after max attempts.")
            return 0

        # --- Submit main page form ---
        if not recaptcha_checkbox_verified(timeout=10):
            raise Exception('reCAPTCHA checkbox not verified in main frame')
        check_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-action='demo_action']"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", check_button)
        time.sleep(0.2)
        check_button.click()

        # Check for the success message using the correct class name
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "_successMessage_1ndnh_1"))
        )

        print("reCAPTCHA v2 passed successfully!")
        
        final_success_path = f"screenshots/final_success_recaptcha_v2_{datetime.now().strftime('%H%M%S')}.png"
        driver.save_screenshot(final_success_path)
        screenshot_paths.append(final_success_path)
        
        create_success_gif(screenshot_paths, output_folder=f"successful_solves/recaptcha_v2_{provider}")
        return 1
    
    except Exception as ex:
        print(f"An error occurred during reCAPTCHA v2 test: {ex}. Marking as failed.")
        traceback.print_exc()
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        return 0

def main():
    parser = argparse.ArgumentParser(description="Test various captcha types.")
    parser.add_argument('captcha_type', choices=['puzzle', 'text', 'complicated_text', 'recaptcha_v2', 'audio'],
                        help="Specify the type of captcha to test")
    parser.add_argument('--provider', choices=['openai', 'gemini', 'gemini-cli', 'codex', 'custom', 'visionai-local'], default='openai', help="Specify the AI provider to use")
    parser.add_argument('--file', type=str, default='files/audio.mp3', help="Path to the local audio file for the 'audio' test.")
    parser.add_argument('--model', type=str, default=None, help="Specify the AI model to use (e.g., 'gpt-4o', 'gemini-2.5-flash').")
    args = parser.parse_args()

    os.makedirs('screenshots', exist_ok=True)

    if args.captcha_type == 'audio':
        # Audio test is now provider-aware
        audio_test(args.file, args.provider, args.model)
        return

    chrome_profile_dir = tempfile.mkdtemp(prefix='private-captcha-solver-chrome-')
    driver = None
    try:
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-features=site-per-process,Translate,BackForwardCache,PaintHolding')
        chrome_options.add_argument('--js-flags=--max-old-space-size=256')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-background-networking')
        chrome_options.add_argument('--disable-sync')
        chrome_options.add_argument('--metrics-recording-only')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--no-zygote')
        chrome_options.add_argument('--remote-debugging-pipe')
        chrome_options.add_argument(f'--user-data-dir={chrome_profile_dir}')
        chrome_options.add_argument('--window-size=1366,768')
        chrome_options.binary_location = os.getenv('CHROME_BINARY', '/usr/bin/google-chrome')
        driver = webdriver.Chrome(options=chrome_options)

        if args.captcha_type == 'puzzle':
            solve_geetest_puzzle(driver, args.provider)
        elif args.captcha_type == 'text':
            text_test(driver, args.provider, args.model)
        elif args.captcha_type == 'complicated_text':
            complicated_text_test(driver, args.provider, args.model)
        elif args.captcha_type == 'recaptcha_v2':
            recaptcha_v2_test(driver, args.provider, args.model)
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        shutil.rmtree(chrome_profile_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
