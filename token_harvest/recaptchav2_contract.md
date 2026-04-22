# reCAPTCHA v2 API contract draft

## Goal

Request-only interface for callers:
- input: `url + siteKey`
- output: token when possible, otherwise structured failure/debug payload

## Proposed endpoint

`POST /recaptchav2`

Body:

```json
{
  "url": "https://target.example/login",
  "siteKey": "...",
  "provider": "gemini-cli",
  "model": null,
  "maxRounds": 5,
  "debug": true
}
```

## Proposed success response

```json
{
  "status": "success",
  "requestId": "...",
  "durationMs": 12345,
  "verified": true,
  "token": "...",
  "stage": "verified"
}
```

## Proposed failure response

```json
{
  "status": "error",
  "requestId": "...",
  "durationMs": 12345,
  "verified": false,
  "stage": "challenge_refresh",
  "message": "...",
  "trace": [
    {"round": 1, "target": "buses", "clicks": [2,7,8], "checkboxVerified": false}
  ]
}
```

## Notes

- Token may be empty even when browser challenge progressed. In that case, `verified=false` and `stage` explains the boundary.
- This endpoint is experimental until the v2 engine stops flaking on multi-round challenge refresh.
