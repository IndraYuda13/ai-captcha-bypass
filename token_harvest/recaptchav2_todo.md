# recaptchav2 engine refactor TODO

- [ ] extract `recaptcha_v2_test()` core loop from `main.py` into reusable callable
- [ ] return structured trace object instead of only prints
- [ ] surface `verified` and any available `g-recaptcha-response` token
- [ ] add `POST /recaptchav2` endpoint in token_harvest server
- [ ] preserve `gemini-cli` provider path for tile reasoning
- [ ] keep debug artifacts per request id
- [ ] re-run 2captcha demo through HTTP endpoint, not only CLI wrapper
