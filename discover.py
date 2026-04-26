from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import httpx


def _pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)


def _read_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        text = resp.text
        if len(text) > 300:
            text = text[:300] + "…"
        return {"__non_json__": text}


def _is_default_404(resp: httpx.Response, body: Any) -> bool:
    if resp.status_code != 404:
        return False
    # FastAPI/Starlette typical 404 shape
    if isinstance(body, dict) and body.get("detail") == "Not Found":
        return True
    # Some APIs return empty JSON / message; treat any 404 as "not interesting"
    return True


def _is_rate_limit(resp: httpx.Response, body: Any) -> Optional[int]:
    if resp.status_code != 429:
        return None
    if isinstance(body, dict) and body.get("error") == "rate_limit":
        ra = body.get("retry_after")
        if isinstance(ra, int) and ra >= 0:
            return ra
    return 1


@dataclass(frozen=True)
class Probe:
    method: str
    path: str
    auth: bool
    json_body: Optional[Dict[str, Any]] = None


def _auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client: httpx.Client) -> str:
    r = client.post("/register")
    j = _read_json(r)
    token = j.get("token") if isinstance(j, dict) else None
    if not isinstance(token, str) or not token:
        raise RuntimeError(f"register failed: status={r.status_code} body={_pretty(j)}")
    return token


def _make_probes(paths: Sequence[str]) -> List[Probe]:
    probes: List[Probe] = []
    for p in paths:
        # Keep request volume low to avoid tripping rate limits.
        probes.append(Probe("GET", p, auth=False))
        probes.append(Probe("GET", p, auth=True))

    return probes


def _candidate_paths() -> List[str]:
    # Keep this list reasonable to avoid hammering the reference.
    return [
        "/",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/health",
        "/healthz",
        "/ping",
        "/status",
        "/version",
        "/whoami",
        "/me",
        "/account",
        "/user",
        "/users",
        "/admin",
        "/debug",
        "/metrics",
        "/stats",
        "/score",
        "/rating",
        "/leaderboard",
        "/ingredients",
        "/recipes",
        "/recipe",
        "/drinks",
        "/drink",
        "/secret",
        "/secrets",
        "/easter",
        "/easter-egg",
        "/easter_egg",
        "/hint",
        "/hints",
        "/help",
        "/about",
        "/close",
        "/open",
        "/bar",
        "/barmen",
    ]


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="https://bar.antihype.lol", help="Reference base URL")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--sleep-ms", type=int, default=350, help="Sleep between requests (politeness)")
    ap.add_argument("--max-requests", type=int, default=80, help="Hard cap to avoid hammering")
    ap.add_argument("--insecure", action="store_true", help="Disable TLS verification")
    args = ap.parse_args(argv)

    client = httpx.Client(base_url=args.ref, timeout=args.timeout, verify=not args.insecure)
    try:
        token = _register(client)

        paths = _candidate_paths()
        probes = _make_probes(paths)

        hits: List[str] = []
        seen: set[Tuple[str, str, bool]] = set()
        rate_limited = 0

        for pr in probes[: max(0, args.max_requests)]:
            key = (pr.method, pr.path, pr.auth)
            if key in seen:
                continue
            seen.add(key)

            headers = _auth_headers(token) if pr.auth else None
            resp = client.request(pr.method, pr.path, headers=headers, json=pr.json_body)
            body = _read_json(resp)

            ra = _is_rate_limit(resp, body)
            if ra is not None:
                rate_limited += 1
                time.sleep(float(ra) + 0.25)
                continue

            if _is_default_404(resp, body):
                pass
            else:
                hits.append(
                    "\n".join(
                        [
                            f"{pr.method} {pr.path} auth={pr.auth} -> {resp.status_code}",
                            _pretty(body),
                        ]
                    )
                )

            time.sleep(max(0, args.sleep_ms) / 1000.0)

        if rate_limited:
            print(f"Rate limited {rate_limited} times (429). Slowed down automatically.")

        if not hits:
            print("No non-404 candidates found in current wordlist.")
            print("Tip: extend _candidate_paths() in discover.py with more guesses.")
            return 0

        print("\n\n".join(hits))
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

