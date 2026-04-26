from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx


def _stable(obj: Any) -> Any:
    """
    Make JSON-like structures deterministic for diffing:
    - dict: sort keys
    - list: keep order (API order may matter)
    """
    if isinstance(obj, dict):
        return {k: _stable(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [_stable(x) for x in obj]
    return obj


def _pretty(obj: Any) -> str:
    return json.dumps(_stable(obj), ensure_ascii=False, indent=2, sort_keys=True)


def _strip_fields(obj: Any, fields: Iterable[str]) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in fields:
                continue
            out[k] = _strip_fields(v, fields)
        return out
    if isinstance(obj, list):
        return [_strip_fields(x, fields) for x in obj]
    return obj


@dataclass(frozen=True)
class Call:
    method: str
    path: str
    json_body: Optional[Dict[str, Any]] = None
    x_time: Optional[str] = None


def _register(client: httpx.Client) -> Tuple[str, Dict[str, Any]]:
    r = client.post("/register")
    return r.headers.get("content-type", ""), _read_json(r)


def _read_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"__non_json__": resp.text}


def _auth_headers(token: str, x_time: Optional[str]) -> Dict[str, str]:
    h = {"Authorization": f"Bearer {token}"}
    if x_time is not None:
        h["X-Time"] = x_time
    return h


def _do(client: httpx.Client, token: str, call: Call) -> Tuple[int, Any]:
    headers = _auth_headers(token, call.x_time)
    r = client.request(call.method, call.path, headers=headers, json=call.json_body)
    return r.status_code, _read_json(r)


def _diff(label: str, a: Any, b: Any) -> List[str]:
    if a == b:
        return []
    return [label, "--- reference", _pretty(a), "--- local", _pretty(b)]


def _diff_ignoring(label: str, a: Any, b: Any, *, ignore_fields: Iterable[str]) -> List[str]:
    aa = _strip_fields(a, ignore_fields)
    bb = _strip_fields(b, ignore_fields)
    return _diff(label, aa, bb)


def _scenario(drinks_from_menu: List[Dict[str, Any]]) -> List[Call]:

    calls: List[Call] = []
    calls.append(Call("GET", "/menu", x_time="14:30"))
    calls.append(Call("GET", "/balance"))
    calls.append(Call("GET", "/profile"))

    if drinks_from_menu:
        d0 = drinks_from_menu[0]["name"]
        calls.append(Call("POST", "/order", {"name": d0}, x_time="14:30"))
        calls.append(Call("POST", "/order", {"name": d0}, x_time="14:31"))

    calls.append(Call("POST", "/mix", {"ingredients": ["водка", "лёд"]}, x_time="14:30"))
    calls.append(Call("POST", "/mix", {"ingredients": ["водка", "сок"]}, x_time="23:59"))

    calls.append(Call("POST", "/tip", {"amount": 5}))
    calls.append(Call("POST", "/tip", {"amount": 10_000}))

    calls.append(Call("GET", "/history"))
    calls.append(Call("GET", "/profile"))

    calls.append(Call("POST", "/reset"))
    calls.append(Call("GET", "/history"))
    calls.append(Call("GET", "/balance"))
    calls.append(Call("GET", "/profile"))
    return calls


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="https://bar.antihype.lol", help="Reference base URL")
    ap.add_argument("--local", default="http://127.0.0.1:8000", help="Local base URL")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--insecure", action="store_true", help="Disable TLS verification for reference")
    args = ap.parse_args(argv)

    ref = httpx.Client(base_url=args.ref, timeout=args.timeout, verify=not args.insecure)
    loc = httpx.Client(base_url=args.local, timeout=args.timeout)

    try:
        _, ref_reg = _register(ref)
        _, loc_reg = _register(loc)
        ref_token = ref_reg.get("token")
        loc_token = loc_reg.get("token")
        if not isinstance(ref_token, str) or not isinstance(loc_token, str):
            print("Failed to register on one of APIs.")
            print("ref:", _pretty(ref_reg))
            print("local:", _pretty(loc_reg))
            return 2

        ref_menu_status, ref_menu = _do(ref, ref_token, Call("GET", "/menu", x_time="14:30"))
        loc_menu_status, loc_menu = _do(loc, loc_token, Call("GET", "/menu", x_time="14:30"))

        problems: List[str] = []
        if ref_menu_status != loc_menu_status:
            problems += [
                "MENU status_code differs",
                f"--- reference: {ref_menu_status}",
                f"--- local: {loc_menu_status}",
            ]
        problems += _diff("MENU body differs", ref_menu, loc_menu)

        drinks = []
        if isinstance(ref_menu, dict) and isinstance(ref_menu.get("drinks"), list):
            drinks = ref_menu["drinks"]

        for i, call in enumerate(_scenario(drinks), start=1):
            rs, rj = _do(ref, ref_token, call)
            ls, lj = _do(loc, loc_token, call)

            if rs != ls:
                problems += [
                    f"[{i}] {call.method} {call.path} status_code differs",
                    f"--- reference: {rs}",
                    f"--- local: {ls}",
                ]
            if rj != lj:
                ignore = []
                if call.path == "/profile":
                    ignore = ["id"]
                problems += _diff_ignoring(
                    f"[{i}] {call.method} {call.path} body differs",
                    rj,
                    lj,
                    ignore_fields=ignore,
                )

        if problems:
            print("\n".join(problems))
            return 1

        print("OK: local matches reference for this probe scenario.")
        return 0
    finally:
        ref.close()
        loc.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

