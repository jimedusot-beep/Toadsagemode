"""Trusted HTTPS-only OpenAI Responses request transport.
Executed as a separate bounded helper. Never accepts an arbitrary URL.
Keys come only from the host's secret environment, never model prompt data.
"""
from __future__ import annotations
import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://api.openai.com/v1/responses"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main():
    raw = sys.stdin.buffer.read(160001)
    if len(raw) > 160000:
        raise ValueError("Request exceeds maximum size")
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != {"payload", "timeout", "max_bytes"}:
        raise ValueError("Invalid transport request")
    timeout = data["timeout"]
    limit = data["max_bytes"]
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0.1 <= timeout <= 60:
        raise ValueError("Invalid transport timeout")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1000 <= limit <= 1000000:
        raise ValueError("Invalid transport body limit")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or "\r" in api_key or "\n" in api_key or len(api_key) > 512:
        raise ValueError("Missing or invalid server-side API key")
    payload = json.dumps(data["payload"], ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(payload) > 150000:
        raise ValueError("Request payload exceeds maximum size")
    request = urllib.request.Request(
        ENDPOINT, data=payload, method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer " + api_key,
        },
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirect(),
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise ValueError("Model returned non-success HTTP status")
            body = response.read(limit + 1)
    except urllib.error.HTTPError:
        # Never emit server response bodies or transport headers; they could
        # contain tenant information, prompt text or sensitive error details.
        raise ValueError("Model provider returned an unsuccessful HTTP status") from None
    except urllib.error.URLError:
        raise ValueError("Model provider transport unavailable") from None
    if len(body) > limit:
        raise ValueError("Model response exceeds maximum size")
    sys.stdout.buffer.write(body)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, TypeError, UnicodeError):
        print("Cloud model request failed or exceeded a bound", file=sys.stderr)
        raise SystemExit(1)
