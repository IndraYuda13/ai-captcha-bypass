# Coinadster reCAPTCHA v2 Cloudflare bridge

Date: 2026-05-05

## Proven

- `token_harvest/recaptchav2_server.py` opens `pageUrl` in a fresh Selenium Chrome profile.
- Current fresh solver browser can be stopped by Coinadster Cloudflare before the reCAPTCHA widget loads.
- Coinadster artefacts show a valid FlareSolverr-cleared bundle contains a browser user-agent plus `cf_clearance` and `PHPSESSID` cookies.
- `src/vision_ai_recaptcha_solver/browser/factory.py:create_replicator_session` already has `cookies`, `user_agent`, and `proxy` parameters, but the active HTTP endpoint currently uses Selenium `make_driver`, not this replicator entrypoint.

## Not proven

- Raw Python `requests` with imported Cloudflare cookies is not a proven transport for Coinadster. Prior Coinadster notes say it still returns `403 cf-mitigated`.
- Attaching directly to a FlareSolverr browser/CDP session is not available from the current project code. No CDP endpoint is exposed by the local FlareSolverr wrapper.

## Minimal patch direction

- Add `userAgent` and `cookies` inputs to `POST /recaptchav2`.
- Start Selenium with `--user-agent=<userAgent>`.
- Preseed cookies via Chrome DevTools `Network.setCookie` before `solve_recaptcha_v2` calls `driver.get(pageUrl)`.
- Keep proxy binding unchanged and pass the same Surfshark/local proxy used by FlareSolverr.
- Caller should pass only cookie name/value/domain/path/secure/httpOnly fields. Do not log cookie values.

## Do not repeat

- Do not try only `proxy` again. The previous failure page was Cloudflare, not the Google reCAPTCHA challenge.
- Do not assume FlareSolverr cookie import into `requests` solves this target.

## Next best action

- Apply the minimal cookie/user-agent preseed patch, extend the Coinadster solver caller to forward the cleared bundle, then live-test oracle: debug HTML must show Coinadster page/reCAPTCHA iframe, not Cloudflare `Just a moment...`.


## Follow-up findings

- Coinadster renders the login reCAPTCHA inside hidden modal `#slogi22Mo2dal`; open the modal before clicking the checkbox.
- For `gemini-cli-grid`, full-grid ranking was more reliable than the secondary per-tile confirmation pass on dynamic grids. Trusting ranked top-level selections produced a real verified token in the Coinadster flow.
- A valid reCAPTCHA token alone is not enough: Coinadster can still reject login with `Session expired` if the hidden page token/PHP session state no longer matches.

## DannyLuna migration lesson

- The custom Selenium/Gemini-grid solver was not reliable enough for Coinadster.
- DannyLuna official `VisionAIRecaptchaSolver` with `recaptcha-domain-replicator`, DrissionPage, Ultralytics/YOLO, and model `yolo12x.pt` solved Coinadster reCAPTCHA and produced valid tokens.
- Heavy dependencies should live in `/mnt/visionai-ref-runtime` on this VPS; root disk is too small for repeated YOLO/OpenCV installs.
- Do not pass Coinadster PHP/Cloudflare cookies into the official solver by default. For Coinadster the robust login lane is to solve in the replica, then create a fresh target session and submit with a fresh hidden token.
