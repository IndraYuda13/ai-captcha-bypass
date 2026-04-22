#!/usr/bin/env python3
import json
import sys
from recaptchav2_engine import solve_recaptcha_v2


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        sys.stdout.write(json.dumps({"status": "error", "message": f"invalid stdin json: {exc}"}))
        return 1

    result = solve_recaptcha_v2(**payload)
    sys.stdout.write(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
