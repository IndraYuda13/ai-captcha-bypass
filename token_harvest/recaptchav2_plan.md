# recaptchav2 refactor plan

## immediate target

Turn the existing `recaptcha_v2_test()` Selenium flow into an engine callable from HTTP.

## minimum output contract

- `status`
- `verified`
- `token` (if any)
- `stage`
- `message`
- `trace[]`
- `artifacts[]` optional

## extraction steps

1. move browser creation to token_harvest server side
2. port `recaptcha_v2_test()` into a callable module with parameters:
   - `pageUrl`
   - `siteKey` optional hint
   - `provider`
   - `model`
   - `maxRounds`
3. replace prints with `trace.push(...)`
4. return structured object instead of integer pass/fail
5. wire endpoint `POST /recaptchav2`

## known hard boundary

- multi-round refreshed iframe DOM churn after verify
- checkbox verified oracle is necessary but not sufficient yet
- token may remain unavailable even when challenge progressed
