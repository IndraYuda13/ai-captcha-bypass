# Token harvest lane

This module is separate from the visual solver.

## Purpose

Provide a browser-side token harvester for reCAPTCHA v3 style targets:
- input: `url`, `siteKey`, optional `action`
- output: token string

## Why separate

- reCAPTCHA v3 is not the same problem as reCAPTCHA v2 image challenges
- this lane uses browser-side `grecaptcha.execute(...)`
- the visual solver remains focused on OCR / image-based tasks

## Endpoint

`POST /recaptchav3`

Body:

```json
{
  "url": "https://target.example",
  "siteKey": "...",
  "action": "submit"
}
```

## Notes

- modeled after the older `rv3` reference lane
- intended as a private module first, not a public stable API yet
