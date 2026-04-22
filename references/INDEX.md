# Solver Reference Index

Purpose:
- durable list of external references, patterns, and lessons for building the private captcha solver
- avoid re-learning the same ideas after session resets

## Active references

- `aplesner/Breaking-reCAPTCHAv2`
  - status: audited
  - focus: reCAPTCHA v2 analysis, segmentation/YOLO solve methodology, and the importance of browser/session realism
  - local repo: `/root/.openclaw/workspace/tmp-gh/Breaking-reCAPTCHAv2`
  - notes: `references/LESSONS.md`

- `lursz/reCAPTCHA-Solver`
  - status: audited
  - focus: full solver pipeline architecture, segmentation, OCR header extraction, prediction, and mouse engine design
  - local repo: `/root/.openclaw/workspace/tmp-gh/reCAPTCHA-Solver`
  - notes: `references/LESSONS.md`

- `IndraYuda/rv3`
  - status: audited
  - focus: browser-side reCAPTCHA v3 token harvest via `grecaptcha.execute(siteKey, {action})`
  - local repo: `/root/.openclaw/workspace/tmp-hf-rv3`
  - local notes: `token_harvest/README.md`
  - notes: `references/LESSONS.md`

## Internal findings already proven

- visual OCR lane:
  - `text` demo passed with `gemini-cli`
  - `complicated_text` demo passed with `gemini-cli`
- visual reCAPTCHA v2 lane:
  - reasoning and tile classification work partially
  - main blocker remains multi-round iframe refresh / DOM churn
- token harvest lane:
  - `recaptchav3` API-like service successfully returned a token on a public v3 demo

## Next references to classify

- challenge refresh synchronization patterns
- token extraction / `g-recaptcha-response` harvesting patterns
- browser-side anti-detection / browser realism patterns
- iframe lifecycle handling patterns
