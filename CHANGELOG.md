# CHANGELOG

## 2026-04-23

### VisionAI parity refactor bootstrap
- Added new package skeleton under `src/vision_ai_recaptcha_solver/` to move local repo away from the old script-first layout and toward the reference repo architecture.
- Added first extracted modules:
  - `__init__.py`
  - `config.py`
  - `types.py`
  - `exceptions.py`
  - `browser/navigation.py`
  - `captcha/base_handler.py`
  - `captcha/selection_handler.py`
  - `captcha/dynamic_handler.py`
  - `captcha/square_handler.py`
  - `solver.py`
- Why this exists:
  - Boskuu explicitly asked that this project become as similar as possible to `DannyLuna17/VisionAIRecaptchaSolver`, not just loosely inspired by it.
  - The live blocker was architectural mismatch, not just solve heuristics. The local repo was still hybrid and script-centric.
- Current design truth:
  - This is a **transitional skeleton**, not full parity yet.
  - `solver.py` currently wraps the legacy implementation through a `LegacyEngineAdapter`, so the new package shape exists before the old logic is fully migrated.
- What must not be casually removed later:
  - the new `src/vision_ai_recaptcha_solver/` package path
  - the split between config/types/browser/handlers/solver layers
  - the note that current solver dispatch is intentionally transitional until the old logic is extracted into real handler implementations

### Step 4 migration start: real round logic moved into handlers
- Replaced the earlier pure-placeholder handler wrappers with first real logic extraction:
  - `captcha/selection_handler.py` now owns round-level 3x3 selection extraction and tile decision building
  - `captcha/dynamic_handler.py` now owns round-level dynamic 3x3 extraction, changed-cell recomposite path, and fallback selection policy
  - `captcha/square_handler.py` now owns round-level 4x4 selection extraction
- `solver.py` was upgraded from adapter-only dispatch into a real orchestrator shell with captcha-type routing plus shared tile click execution.
- Why this exists:
  - step 4 target was to stop treating the new package as empty scaffolding and start moving real solve behavior out of `token_harvest/recaptchav2_engine.py`.
- Current truth:
  - this is still **partial migration**, not a full engine cutover.
  - bootstrap, verification loop, token extraction, and end-to-end round orchestration are still primarily anchored in the old engine.
  - handler code now contains meaningful solve logic, so the architectural migration is real, but the old engine still remains the active top boundary.
- What future edits must not casually remove:
  - the migrated round-level logic inside the three new handler files
  - the rule that new parity work should continue extracting behavior into the package instead of adding fresh complexity only to `token_harvest/recaptchav2_engine.py`

### Step 5 migration: solver became main orchestration boundary
- Moved the main bootstrap and orchestration flow into `src/vision_ai_recaptcha_solver/solver.py`:
  - result object construction
  - trace appending
  - checkbox bootstrap
  - challenge readiness
  - DOM target extraction
  - reload / verify / token helpers
  - round loop orchestration
  - handler dispatch
  - selected-tile click execution
  - final verify and exception artifact handling
- Reduced `token_harvest/recaptchav2_engine.py` to a thin wrapper that now delegates directly into `RecaptchaSolver.solve(...)`.
- Why this exists:
  - Boskuu approved the next step to make `solver.py` the real brain and leave the old engine as a transition boundary only.
- Current truth:
  - this is the first real boundary flip. The package solver is now the main owner of the end-to-end v2 visual flow.
  - parity is still incomplete because browser boundary is still Selenium/demo-page oriented, not yet replicator-first like the reference repo.
- What must not be casually removed later:
  - the thin-wrapper role of `token_harvest/recaptchav2_engine.py`
  - the fact that `solver.py` is now the intended canonical orchestration boundary for future parity work

### Step 6 browser-boundary prep + first test
- Installed missing parity-side dependencies into the project venv:
  - `recaptcha-domain-replicator`
  - `DrissionPage`
- Added browser boundary abstraction files:
  - `browser/session.py`
  - `browser/factory.py`
- New boundary capability:
  - can create a Selenium-backed `BrowserSession` for the existing flow
  - can create a replicator-backed `BrowserSession` for the future reference-style flow
  - session cleanup is centralized instead of being scattered in entry scripts
- Verification already run:
  - import check confirmed both `recaptcha_domain_replicator` and `DrissionPage` are now available in the venv
  - smoke test confirmed `create_selenium_session()` works and cleans up correctly
- Current truth:
  - browser boundary parity prep is now real, but solver flow has not yet been fully switched to a replicator session object
  - this was the smallest meaningful live test after the boundary prep, and it passed
- What must not be casually removed later:
  - the new browser factory/session abstraction
  - the fact that replicator dependencies are now present and ready for the next integration step

### Step 7 transition test through BrowserSession abstraction
- Updated `solver.py` so it can accept either a raw driver or a `BrowserSession` wrapper.
- Added `solve_with_selenium_session()` as a transition entry so the new solver can own session creation + cleanup through the new boundary layer.
- Ran a real transition smoke test through the new path:
  - `RecaptchaSolver().solve_with_selenium_session(...)`
  - targeted `https://2captcha.com/demo/recaptcha-v2`
  - completed without crashing the new session-boundary flow
  - returned a structured result (`status=error`, `stage=incomplete`, `verified=False`, `trace-len=2`)
- Meaning of the test:
  - the boundary refactor path itself works end-to-end
  - failure is currently solve incompleteness, not a broken session abstraction or wrapper path
- What must not be casually removed later:
  - support for passing `BrowserSession` into `solve()`
  - `solve_with_selenium_session()` as the first real session-boundary transition entry

### Step 8 replicator lane scaffold + smoke result
- Added `solve_with_replicator_session()` into `solver.py` as the first reference-style session entrypoint.
- Confirmed the minimal replicator API actually available in this environment:
  - constructor accepts `download_dir`, `server_port`, `persist_html`, `proxy`, `browser_path`
  - `replicate_captcha(...)` accepts `website_key`, `website_url`, invis/enterprise flags, cookies, user_agent, and headless mode
- Ran a minimal replicator smoke test against Google's public demo site.
- Actual outcome in this VPS/runtime:
  - `session.mode = replicator`
  - but `browser = None`
  - `token_handle = None`
  - cleanup succeeded
- Meaning of this result:
  - the new replicator session entrypoint and cleanup path work
  - but the live browser bootstrap inside `recaptcha-domain-replicator` is still failing in this environment before a usable browser/token handle is returned
  - so the current blocker is now a concrete environment/bootstrap issue inside the replicator lane, not a missing abstraction in our repo
- What must not be casually removed later:
  - `solve_with_replicator_session()` as the dedicated parity lane entry
  - the finding that current replicator smoke returns `None` browser/token in this VPS runtime and therefore needs focused bootstrap debugging

### Step 9 replicator bootstrap fix verified
- Read the real hidden bootstrap error from `recaptcha-domain-replicator` logs.
- Root cause confirmed:
  - `DrissionPage` Chromium bootstrap failed with `BrowserConnectError`
  - its own hint explicitly pointed to missing Linux headless flags like `--headless=new` and `--no-sandbox`
- Applied a minimal local environment-specific patch in the installed package:
  - expanded `recaptcha_domain_replicator/constants.py` `CHROMIUM_ARGUMENTS` with the same hardened Chromium flags already proven stable in the Selenium lane on this VPS
- Re-ran replicator bootstrap smoke test.
- Verified new outcome:
  - `FINAL_BROWSER Chromium`
  - `FINAL_TOKEN True`
  - logs confirmed browser creation succeeded and reCAPTCHA iframe was detected
- Meaning of this result:
  - the replicator lane now boots successfully in this environment
  - the previous blocker was specifically the package's default Chromium flags, not a deeper architecture failure
- What must not be casually removed later:
  - the local hardened Chromium-argument patch for `recaptcha-domain-replicator`
  - the lesson that this VPS needs the same strict headless Linux flags for both Selenium and DrissionPage-based Chromium bootstrap

### Step 10 first live solve attempt via replicator exposed API mismatch
- Ran the first real `solve_with_replicator_session()` attempt against Google's demo reCAPTCHA.
- Result did not crash the process, but failed immediately with a structured exception trace:
  - `exception: 'Chromium' object has no attribute 'get'`
- Meaning of the failure:
  - replicator bootstrap now works
  - but the local solver flow still assumes Selenium-style driver methods (`driver.get`, `find_elements`, `switch_to.frame`, etc.)
  - the replicator lane returns a DrissionPage `Chromium` object with a different browser/tab API
- New concrete blocker:
  - the next required step is not bootstrap anymore; it is **API adaptation** between Selenium driver assumptions and DrissionPage browser/tab behavior
- What must not be casually removed later:
  - the evidence that the next parity gap is browser API mismatch, not replicator startup
  - the requirement to build a browser adapter layer instead of forcing Selenium calls directly onto DrissionPage objects

### Step 11 adapter phase 1 and 2
- Added `browser/adapter.py` with first `SeleniumAdapter` and `DrissionAdapter` abstraction.
- First adapter phase covered:
  - `open()`
  - `get_challenge_title()`
  - `get_checkbox_checked()`
- Second adapter phase covered:
  - `click_checkbox()`
  - `has_challenge_open()`
- Retests showed live progress through successive blockers:
  - removed `'Chromium' object has no attribute 'get'`
  - removed `'Chromium' object has no attribute 'find_element'`
  - advanced to native challenge detection state instead of immediate adapter failure
- Critical live finding:
  - direct JS access to `frame.contentWindow.document` in the replicator page failed with cross-origin `SecurityError`
  - but native DrissionPage frame access via `tab.get_frame(iframe)` worked
- Native frame proof gathered live:
  - `ChromiumFrame` objects could be created from iframes
  - checkbox could be clicked from the frame object
  - challenge iframe and instruction text were readable natively
  - example native instruction read succeeded, e.g. `Select all images with a fire hydrant ...`
- Meaning:
  - replicator lane is viable, but requires **native frame API usage**, not top-page JS cross-frame scraping

### Step 12 native frame adapter integration
- Extended adapter with native challenge helpers for DrissionPage:
  - `get_challenge_frame()`
  - `get_challenge_elements()`
  - `get_target_keyword()`
- Refactored solver paths to use adapter-driven challenge frame and keyword extraction.
- Verified native keyword extraction live from challenge frame, including `tag:strong` and payload selectors.
- Retests advanced through these blockers:
  - removed `keyword_missing`
  - removed `ChromiumElement.find_elements` mismatch for some table/tile paths
  - removed `ChromiumElement.screenshot` mismatch by proving and then using `get_screenshot()`/`save()` on DrissionPage elements
- Confirmed native capture API:
  - `ChromiumElement.get_screenshot(path=...)` works for table and instruction elements
- Added adapter helper `capture_element()` and wired handlers to use it.

### Step 13 native image/tile extraction and table traversal
- Probed the live native challenge DOM directly and found the image-source root cause:
  - old selectors like `#rc-imageselect-target img` and `.rc-image-tile-wrapper img` returned `0`
  - generic `tag:img` returned the real challenge images and valid payload URLs
- Patched Drission image URL extraction helper to prioritize `tag:img`.
- Retest confirmed image feed now works:
  - `round analyzed urls=16` on live 4x4 challenge instead of `0`
- Probed native table traversal and verified:
  - `table.eles('tag:td')` returns 9 tiles for 3x3
  - `ChromiumElement` tile objects are usable
- Added adapter helper `get_table_tiles()` and refactored handlers/solver to use adapter tile enumeration instead of raw `find_elements()`.
- Retests then reached genuine selection-phase problems instead of plumbing failures.

### Step 14 reference-policy comparison and raw ranking probes
- Audited reference behavior from DannyLuna repo:
  - 3x3 uses ranking-based selection (top 3 plus optional 4th)
  - 4x4 uses detection-to-cell mapping directly
- Identified that local helper had drifted from reference in the 4x4 path due to extra dense/edge heuristics.
- Simplified local 4x4 helper closer to reference by removing extra custom post-processing and using detection-to-cell output directly.
- Built isolated live probes to capture real challenge grids and compare raw model output.
- Successful reference-model raw ranking probe on a live 3x3 `cars` grid showed the reference model itself is healthy:
  - sample ranked output included strong scores like
    - cell 6 ≈ `0.9966`
    - cell 4 ≈ `0.9880`
    - cell 1 ≈ `0.9063`
  - proving that empty selections were not caused by the core reference model being unable to score the grid
- This shifted suspicion away from model quality and toward live-path control flow / import / policy wiring.

### Step 15 root cause: live VisionAI function was not actually available
- Added traces inside live handlers and solver import path.
- Live evidence showed `visionai_fn=False` inside square handler for 4x4 challenges.
- Added import tracing in `solver.py` and confirmed the actual root cause:
  - `visionai import failed: No module named 'vision_ai_recaptcha_solver.detector.yolo_detector'`
- Meaning:
  - live solver was not actually calling the reference VisionAI detector at all
  - empty selections were explained by the ranking function failing to import before execution
- This exposed the real blocker as **namespace collision / import failure**, not model weakness.

### Step 16 subprocess isolation for VisionAI reference
- Created subprocess-based ranking runner:
  - `tmp_visionai_rank_runner.py`
- Added thin subprocess wrapper module:
  - `src/vision_ai_recaptcha_solver/visionai_subprocess.py`
- Initial goal:
  - bypass in-process namespace collision by calling the reference detector in an isolated process using the reference venv python
- Verified the dedicated runner can succeed manually when invoked with the right environment and grid artifact.
- Initial live subprocess helper still failed because the subprocess environment did not inherit the correct reference `PYTHONPATH`.
- Fixed subprocess environment by explicitly setting:
  - `PYTHONPATH=<VisionAI src>:<VisionAI site-packages>`
- This was the turning point.

### Step 17 major milestone: live VisionAI ranking finally executed
- After the explicit subprocess env fix, the live solver finally invoked the real reference ranking path successfully.
- Verified live trace output from the actual solve path showed reference-model confidence values, for example on a 3x3 `bus` challenge:
  - tile 8 conf ≈ `0.9999`
  - tile 6 conf ≈ `0.9907`
  - tile 7 conf ≈ `0.9835`
  - lower-confidence trailing tiles also logged
- Most important live milestone:
  - `selected_tiles = [6, 7, 8]`
  - `new_clicks = 3`
- This proved conclusively that:
  - the live path now really uses VisionAI reference scoring
  - the earlier `selected_tiles=[]` issue was not because the AI model could not choose
  - the true root cause had been import / env wiring into the live solve path

### Current live blocker after the big fix
- After live VisionAI selection finally worked, the solve path advanced and exposed the next blocker:
  - `exception: 'Chromium' object has no attribute 'switch_to'`
- Meaning:
  - post-selection flow still contains remaining Selenium-only cleanup / verification code paths
  - the current active work after this checkpoint should focus on removing or adapting the remaining `switch_to` usage for native DrissionPage/replicator flow
- Current honest state at this commit moment:
  - replicator bootstrap works
  - native frame access works
  - image source works
  - keyword extraction works
  - tile enumeration works
  - native capture works
  - reference VisionAI scoring works live
  - selected tiles finally become non-empty in the real live path
  - the next blocker is now only the leftover Selenium `switch_to` path after tile selection
