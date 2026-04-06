#!/usr/bin/env python3
"""
Check Bybit mainnet and testnet connectivity with response latency (ms).

Features:
- Public health check on both environments (no keys needed)
- Optional authenticated check per environment (if keys are provided)
- Prints per-attempt latency and summary stats

Usage:
  python3 test/check_bybit_network.py
  python3 test/check_bybit_network.py --attempts 5 --timeout 8

Environment variables (optional):
  BYBIT_MAINNET_API_KEY
  BYBIT_MAINNET_API_SECRET
  BYBIT_TESTNET_API_KEY
  BYBIT_TESTNET_API_SECRET

Fallback env vars for mainnet:
  BYBIT_API_KEY
  BYBIT_API_SECRET
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests


MAINNET_URL = "https://api.bybit.com"
TESTNET_URL = "https://api-testnet.bybit.com"


@dataclass
class CheckResult:
    name: str
    ok: bool
    status_code: Optional[int]
    latency_ms: float
    detail: str


def sign_payload(api_key: str, api_secret: str, timestamp: int, recv_window: int, payload: str) -> str:
    raw = f"{timestamp}{api_key}{recv_window}{payload}"
    return hmac.new(api_secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()


def timed_get(session: requests.Session, url: str, *, headers: Optional[Dict[str, str]] = None,
              timeout: int = 6) -> Tuple[float, Optional[requests.Response], Optional[str]]:
    start = time.perf_counter()
    try:
        resp = session.get(url, headers=headers, timeout=timeout)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return elapsed_ms, resp, None
    except requests.RequestException as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return elapsed_ms, None, str(exc)


def check_public(session: requests.Session, base_url: str, timeout: int) -> CheckResult:
    url = f"{base_url}/v5/market/time"
    latency_ms, resp, err = timed_get(session, url, timeout=timeout)

    if err:
        return CheckResult("public", False, None, latency_ms, err)

    ok = False
    detail = ""
    status = resp.status_code
    try:
        data = resp.json()
        ok = (status == 200 and data.get("retCode") == 0)
        detail = f"retCode={data.get('retCode')} retMsg={data.get('retMsg', '')}"
    except json.JSONDecodeError:
        detail = "Non-JSON response"

    return CheckResult("public", ok, status, latency_ms, detail)


def check_private(session: requests.Session, base_url: str, api_key: str, api_secret: str,
                  timeout: int) -> CheckResult:
    endpoint = "/v5/account/wallet-balance"
    params = "accountType=UNIFIED"
    url = f"{base_url}{endpoint}?{params}"
    ts = int(time.time() * 1000)
    recv_window = 5000
    signature = sign_payload(api_key, api_secret, ts, recv_window, params)
    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-SIGN": signature,
        "X-BAPI-SIGN-TYPE": "2",
        "X-BAPI-TIMESTAMP": str(ts),
        "X-BAPI-RECV-WINDOW": str(recv_window),
    }

    latency_ms, resp, err = timed_get(session, url, headers=headers, timeout=timeout)
    if err:
        return CheckResult("private", False, None, latency_ms, err)

    ok = False
    detail = ""
    status = resp.status_code
    try:
        data = resp.json()
        ok = (status == 200 and data.get("retCode") == 0)
        detail = f"retCode={data.get('retCode')} retMsg={data.get('retMsg', '')}"
    except json.JSONDecodeError:
        detail = "Non-JSON response"

    return CheckResult("private", ok, status, latency_ms, detail)


def summarize(values: List[float]) -> str:
    if not values:
        return "n/a"
    avg = sum(values) / len(values)
    return f"min={min(values):.1f}ms avg={avg:.1f}ms max={max(values):.1f}ms"


def run_env_checks(name: str, base_url: str, api_key: str, api_secret: str,
                   attempts: int, timeout: int) -> int:
    print(f"\n=== {name.upper()} ({base_url}) ===")
    session = requests.Session()
    failures = 0

    public_latencies: List[float] = []
    private_latencies: List[float] = []

    for i in range(1, attempts + 1):
        public_result = check_public(session, base_url, timeout)
        public_latencies.append(public_result.latency_ms)
        p_status = public_result.status_code if public_result.status_code is not None else "ERR"
        p_ok = "OK" if public_result.ok else "FAIL"
        print(
            f"[{i}/{attempts}] public  status={p_status}  latency={public_result.latency_ms:.1f}ms  {p_ok}  {public_result.detail}"
        )
        if not public_result.ok:
            failures += 1

        if api_key and api_secret:
            private_result = check_private(session, base_url, api_key, api_secret, timeout)
            private_latencies.append(private_result.latency_ms)
            pr_status = private_result.status_code if private_result.status_code is not None else "ERR"
            pr_ok = "OK" if private_result.ok else "FAIL"
            print(
                f"[{i}/{attempts}] private status={pr_status}  latency={private_result.latency_ms:.1f}ms  {pr_ok}  {private_result.detail}"
            )
            if not private_result.ok:
                failures += 1
        elif i == 1:
            print("[info] private check skipped (no API key/secret for this environment)")

    print(f"summary public : {summarize(public_latencies)}")
    if private_latencies:
        print(f"summary private: {summarize(private_latencies)}")

    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Bybit mainnet/testnet API + latency")
    parser.add_argument("--attempts", type=int, default=3, help="Attempts per environment (default: 3)")
    parser.add_argument("--timeout", type=int, default=6, help="HTTP timeout in seconds (default: 6)")

    parser.add_argument("--main-key", default=os.getenv("BYBIT_MAINNET_API_KEY") or os.getenv("BYBIT_API_KEY", ""))
    parser.add_argument("--main-secret", default=os.getenv("BYBIT_MAINNET_API_SECRET") or os.getenv("BYBIT_API_SECRET", ""))
    parser.add_argument("--test-key", default=os.getenv("BYBIT_TESTNET_API_KEY", ""))
    parser.add_argument("--test-secret", default=os.getenv("BYBIT_TESTNET_API_SECRET", ""))

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    attempts = max(1, args.attempts)
    timeout = max(1, args.timeout)

    print("Bybit connectivity and latency check")
    print(f"attempts={attempts} timeout={timeout}s")

    total_failures = 0
    total_failures += run_env_checks(
        "mainnet", MAINNET_URL, args.main_key.strip(), args.main_secret.strip(), attempts, timeout
    )
    total_failures += run_env_checks(
        "testnet", TESTNET_URL, args.test_key.strip(), args.test_secret.strip(), attempts, timeout
    )

    print("\n=== RESULT ===")
    if total_failures == 0:
        print("All checks passed.")
        return 0

    print(f"Completed with {total_failures} failed check(s).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())