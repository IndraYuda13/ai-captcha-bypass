# Solver reference lessons

## 2026-04-22 - `aplesner/Breaking-reCAPTCHAv2`

Key takeaways:
- reCAPTCHA v2 solve rate is not just a classifier problem; browser history, cookies, and IP/user context matter heavily.
- image challenge automation can be pushed far with detection/segmentation models, but success should be measured together with browser/session realism.
- data collection, labeling, and log visualization are first-class parts of the system, not side utilities.

Reusable lessons for our solver:
- keep solving metrics and traces per round
- treat browser realism and session state as a real boundary, not noise
- keep segmentation/cropping quality high because downstream classification quality depends on it

Notable mismatch vs our current lane:
- their emphasis is more ML-heavy (YOLO / segmentation models), while our current private solver uses multimodal LLM reasoning plus browser automation.
- however, the browser-state lesson is directly applicable to our unstable v2 lane.

## 2026-04-22 - `lursz/reCAPTCHA-Solver`

Key takeaways:
- solving should be treated as a full pipeline: screenshot capture -> segmentation -> instruction extraction -> tile prediction -> mouse action -> submission.
- a monorepo split between runtime app and model training is a good long-term structure.
- mouse movement realism is its own subsystem and can affect solver credibility/stability.

Reusable lessons for our solver:
- preserve clear separation between runtime solver logic and any future training/data tooling
- keep the segmentation/cropping layer explicit and inspectable
- model output alone is insufficient; action execution strategy matters

Notable mismatch vs our current lane:
- their project leans on dedicated trained models and deterministic/ML mouse engines.
- our current system leans on Gemini CLI for reasoning and visual interpretation, so we can borrow the architecture more than the exact model stack.

## 2026-04-23 - VisionAI local alignment to DannyLuna reference

Key takeaways:
- the reference repo does not rely on OCR of a screenshot banner as the primary source of the target object.
- the correct primary lane is DOM-first keyword extraction from the challenge itself, then YOLO classification for 3x3 and YOLO detection for 4x4.
- our previous screenshot-banner instruction path was the main architectural mismatch.
- after switching to DOM-first extraction, the solver started reading real targets like `crosswalks` and `traffic lights` correctly from the live challenge.
- for 3x3 selection/dynamic, the reference behavior is ranking based: top 3 cells plus optional 4th if threshold passes, with a minimum-confidence gate.

Reusable lessons for our solver:
- keep `visionai-local` focused on what the reference model is actually good at: target mapping and tile/grid analysis.
- treat banner screenshot OCR only as a fallback, not as the primary truth source.
- when matching a third-party solver architecture, copy the data boundaries first, then tune thresholds.

## 2026-04-23 - dynamic handler mimic pass

Key takeaways:
- the engine now mirrors the reference dynamic architecture more closely: keep base grid, track per-cell image URLs, composite only changed clicked cells, and re-analyze only those changed cells while honoring a non-match cache.
- live smoke after this patch confirmed the multi-round loop itself is active and stable enough to continue across refreshed challenges.
- however, the captured smoke sequence happened to be 4x4-heavy, so the true dynamic 3x3 fidelity is not fully proven yet by downstream evidence.
- the same smoke also showed that 4x4 detection can overselect too many cells on some prompts, which is a separate tuning lane from the 3x3 dynamic architecture.

Reusable lessons for our solver:
- separate architecture-fidelity claims from quality/tuning claims. The loop can be structurally correct even when thresholds still need work.
- do not call dynamic 3x3 verified until a real 3x3 refresh sequence is observed with changed-cell-only re-analysis and sensible downstream clicks.

## 2026-04-23 - proof of real 3x3 dynamic refresh

Key takeaways:
- real 3x3 dynamic runs were finally observed over multiple rounds with stable 3x3 tile counts and changing selected cells across rounds.
- this is downstream proof that the refresh-aware loop is not just structurally present, but actively reacting to changed challenge state.
- concrete evidence from live runs:
  - `hunt3x3b-3` target `bus`: selected cells changed across rounds ` [1,2,8] -> [1,7,8] -> [3,5,8] `.
  - `hunt3x3b-4` target `bicycles`: selected cells changed across rounds ` [1,4,5] -> [1,4,7] -> [1,3,5] `.
- a small 4x4 guard was also added in the wrapper: raise effective detection threshold a bit and trim extreme over-selection cases when the detected cell set becomes too wide.

Reusable lessons for our solver:
- for dynamic 3x3 proof, repeated 3x3 rounds with changing selected tiles are a meaningful downstream oracle.
- 4x4 tuning should stay minimal and wrapper-level first, so the architecture remains close to the reference while runtime-specific over-selection is softened.

## 2026-04-23 - narrowed blocker after 3x3 completion patch

Key takeaways:
- the recent completion patch fixed a real comparison bug, but live runs still did not reach verified/token.
- the remaining blocker is narrower than before: the engine still cannot reliably tell when a dynamic 3x3 refresh wave is actually finished.
- URL-diff alone is not a sufficient refresh completion oracle in this lane. The board can remain open and dynamic without our current checks concluding that it is ready for final verify.
- the next likely useful oracle should come from richer post-click state evidence, such as tile DOM state changes, verify-button transitions, or short-window screenshot/hash comparisons on the clicked cells.

Reusable lessons for our solver:
- separate `reference snapshot for refresh comparison` from `current round snapshot`; overwriting the reference too early silently kills post-click logic.
- when URL-level evidence keeps failing, escalate to a stronger visual or DOM settle oracle instead of stretching the same weak signal further.

## 2026-04-23 - reference-aligned verify-settle oracle validated live

Key takeaways:
- after tracing the DannyLuna reference deeper, the real completion oracle was confirmed: always click verify, then wait on verify-button disabled/enabled processing state before judging solved vs unsolved.
- this oracle was ported into our Selenium engine and then validated live after clearing a separate browser-start blocker.
- the live trace changed accordingly, proving the new path is active, for example: `challenge still open after verify settle wait, continue next round`.
- a separate ops blocker also surfaced and was fixed: Chrome startup instability after restart came from reusing a fixed `--user-data-dir`. Switching to a fresh temporary Chrome profile per request restored stable startup.
- after these fixes, the remaining failures are no longer architecture confusion. The current misses are in live board interaction quality and occasional Selenium instability, not in the completion-oracle design itself.

Reusable lessons for our solver:
- when validating a new code path, trace-message changes are useful proof that the live server is actually executing the patched branch.
- for long-lived local automation services, shared Chrome profiles are fragile after hard restarts; per-request temp profiles are safer.

## 2026-04-23 - recaptchav2 Python HTTP lane

Key takeaways:
- the Python `POST /recaptchav2` server is now live and can execute the extracted Selenium engine end-to-end against the 2captcha demo.
- the current first hard blocker is instruction-provider correctness and availability in service context, not endpoint wiring.
- `visionai-local` is usable for tile classification/ranking but should not be trusted for instruction-banner OCR.
- `gemini-cli` currently fails here due to quota exhaustion, and the local custom relay returned HTTP 500 in the tested service context.

Reusable lessons for our solver:
- keep instruction extraction decoupled from tile classification so hybrid lanes can swap providers independently.
- when a provider fails, distinguish between logic bugs and provider-runtime failures like quota, missing binary, or relay 500.
- preserve debug artifacts per request id because they let us verify whether the target object or tile picks were wrong.

## Combined conclusion

For our private solver roadmap, the references suggest three permanent architecture rules:
1. Separate token-harvest lanes (e.g. reCAPTCHA v3) from visual challenge lanes (e.g. reCAPTCHA v2 image grid).
2. Treat session realism, cookie state, and browser stability as equal in importance to classifier quality.
3. Keep detailed per-round trace and artifact capture so failures are diagnosable instead of opaque.
