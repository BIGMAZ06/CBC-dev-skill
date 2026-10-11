#!/usr/bin/env python3
"""CBC model inventory and opt-in, low-cost OpenCode connection probes.

No credentials, provider configuration, or OpenCode sessions are read or edited.
Probe success means connectivity only, not coding quality or free-tier entitlement.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CATALOG = ROOT / "models" / "cbc-model-pool.json"
STATE = ROOT / "task-state" / "model-pool" / "probes.json"
MARKER = "CBC_PROBE_OK"
PROMPT = "Connection test only. Reply with exactly CBC_PROBE_OK and nothing else."


def load_catalog(path=CATALOG):
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != 1 or not isinstance(data.get("candidates"), list):
        raise ValueError("Unsupported model catalog schema")
    ids = [entry["id"] for entry in data["candidates"]]
    if len(ids) != len(set(ids)) or any("/" not in x or x.startswith("/") for x in ids):
        raise ValueError("Invalid or duplicate model IDs")
    return data


def classify_error(s):
    text = s.lower()
    if re.search(r"\b(429|rate.limit|too many requests|quota exceeded|resource.exhausted)\b", text):
        return "rate_limited"
    if re.search(r"\b(401|403|unauthorized|invalid api key|permission denied|billing)\b", text):
        return "auth_or_billing"
    if re.search(r"\b(404|not found|model unavailable|unknown model)\b", text):
        return "model_unavailable"
    if re.search(r"\b(500|502|503|504|529|overloaded|service unavailable|timeout)\b", text):
        return "temporary_error"
    return "error_unknown"


def probe(model, timeout=45, runner=subprocess.run):
    try:
        result = runner(
            ["opencode", "run", "--model", model, PROMPT],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "model": model}
    except OSError:
        return {"status": "cli_unavailable", "model": model}
    if result.returncode != 0:
        return {"status": classify_error((result.stderr or "") + "\n" + (result.stdout or "")), "model": model}
    # A reply to the probe is connectivity evidence only; no code quality inferred.
    ok = any(line.strip() == MARKER for line in result.stdout.splitlines())
    return {"status": "responded" if ok else "unexpected_response", "model": model}


def record(result, path=STATE):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    history = []
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Unexpected local probe state")
        history = data[-99:]
    entry = dict(result)
    entry["timestamp_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    history.append(entry)
    # This file is ignored by Git; never store requests, replies, or credentials.
    path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="CBC OpenCode model inventory and connection probe")
    parser.add_argument("--catalog", type=pathlib.Path, default=CATALOG)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list", help="Display candidates; does NOT call any provider")
    p = sub.add_parser("probe", help="Send one small request to a specifically selected model")
    p.add_argument("model")
    p.add_argument("--timeout", type=int, default=45)
    p.add_argument("--no-save", action="store_true")
    args = parser.parse_args(argv)
    data = load_catalog(args.catalog)
    candidates = {c["id"]: c for c in data["candidates"]}
    if args.action == "list":
        for item in data["candidates"]:
            print(f'{item["id"]}\t{item["tier"]}\t{item["role"]}\tUNVERIFIED')
        return 0
    if args.model not in candidates:
        parser.error("Model not in CBC candidate catalog; add after explicit review")
    if not 5 <= args.timeout <= 180:
        parser.error("timeout must be 5–180 seconds")
    result = probe(args.model, timeout=args.timeout)
    if not args.no_save:
        record(result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "responded" else 1


if __name__ == "__main__":
    sys.exit(main())
