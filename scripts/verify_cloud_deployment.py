#!/usr/bin/env python3
"""Verify public DINKLY cloud dependencies without printing credentials."""

from __future__ import annotations

import argparse
import os
from urllib.parse import urlsplit

import httpx

PATHS = (
    "/health",
    "/health/database",
    "/health/storage",
    "/health/slack",
    "/health/gemini",
    "/health/agent",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default=os.getenv("API_URL"))
    args = parser.parse_args()
    parsed = urlsplit(args.api_url or "")
    if parsed.scheme != "https" or not parsed.hostname or parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("API_URL must be a public HTTPS URL")
    base = str(args.api_url).rstrip("/")
    failures = []
    with httpx.Client(timeout=20) as client:
        for path in PATHS:
            try:
                response = client.get(f"{base}{path}")
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                failures.append(f"{path}: {type(exc).__name__}")
                continue
            status = str(payload.get("status") or "unknown")
            print(f"{path}: {status}")
            if path == "/health" and payload.get("mode") != "cloud":
                failures.append("/health: APP_MODE is not cloud")
            expected = {"/health/gemini": {"configured", "healthy"}}
            allowed = expected.get(path, {"healthy"})
            if status not in allowed:
                failures.append(f"{path}: {status}")
    if failures:
        print("Cloud verification failed:")
        print("\n".join(f"- {failure}" for failure in failures))
        return 1
    print("Public cloud dependencies are healthy. Continue the human Slack/generation acceptance runbook.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
