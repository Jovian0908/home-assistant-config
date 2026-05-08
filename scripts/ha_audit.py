"""ha_audit.py — basnijholt-style self-audit for the HA renovation.

Combines three audits in one CLI:
  1. find-unused-sensors  -- sensors defined in YAML but never referenced anywhere
  2. find-dangling-refs   -- automations referencing entity_ids that don't exist
  3. check-repairs        -- HA's `repairs/list_issues` WebSocket query (active issues)

Run:
  python scripts/ha_audit.py [--ha-url URL] [--config-dir DIR] [--exit-on-findings]

Phase 5 of the renovation v2 (2026-05-08). The lockout-resilience pillar:
this script answers "is the config still healthy?" without me touching HA UI.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

import websockets
import yaml


def load_token(secrets_path: Path, prefer: str = "HA_ADMIN_TOKEN") -> str:
    """Load token from secrets file. Tries prefer first, then HA_TOKEN as fallback."""
    text = secrets_path.read_text(encoding="utf-8")
    for key in (prefer, "HA_TOKEN", "HA_ADMIN_TOKEN"):
        for line in text.splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    raise SystemExit(f"No HA token found in {secrets_path}")


def gather_yaml_files(config_dir: Path) -> list[Path]:
    """Walk config_dir collecting all YAML files (skip .storage, deps, www)."""
    skip = {".storage", "deps", "www", "tts", ".cloud", "blueprints"}
    out: list[Path] = []
    for p in config_dir.rglob("*.yaml"):
        if any(part in skip for part in p.parts):
            continue
        out.append(p)
    return out


# ---- find-dangling-refs ---------------------------------------------------

ENTITY_RE = re.compile(r"\b([a-z_]+)\.([a-z0-9_]+)\b")
DOMAINS = {
    "alarm_control_panel", "automation", "binary_sensor", "button", "calendar",
    "camera", "climate", "conversation", "cover", "device_tracker", "event",
    "fan", "humidifier", "input_boolean", "input_button", "input_datetime",
    "input_number", "input_select", "input_text", "light", "lock", "media_player",
    "number", "person", "remote", "scene", "script", "select", "sensor", "siren",
    "stt", "sun", "switch", "text", "timer", "todo", "tts", "update", "vacuum",
    "valve", "weather", "zone",
}


async def find_dangling_refs(ha_url: str, token: str, yaml_files: list[Path]) -> list[dict]:
    """Scan YAML for entity_id refs that don't exist in HA's state machine."""
    # Pull live entity ids
    async with websockets.connect(f"{ha_url.replace('http', 'ws')}/api/websocket",
                                  max_size=64 * 1024 * 1024) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        ack = json.loads(await ws.recv())
        if ack.get("type") != "auth_ok":
            raise SystemExit(f"auth: {ack}")
        await ws.send(json.dumps({"id": 1, "type": "get_states"}))
        r = json.loads(await ws.recv())
        live_ids: set[str] = {s["entity_id"] for s in r.get("result", [])}

    # Scan YAML files for entity-id-shaped strings
    findings = []
    for f in yaml_files:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        for ln_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            # Skip lines that are obviously service-call or method-name shaped
            # (e.g. "service: automation.turn_on", "input_boolean.turn_off:")
            # Real entity_id refs sit on entity_id:/target: or in singletons in lists.
            if any(stripped.startswith(p) for p in ("#", "//", "/*")):
                continue
            for m in ENTITY_RE.finditer(line):
                domain, obj_id = m.group(1), m.group(2)
                if domain not in DOMAINS:
                    continue
                eid = f"{domain}.{obj_id}"
                # Filter: pseudo-services like automation.turn_on, automation.reload
                if obj_id in ("turn_on", "turn_off", "toggle", "reload", "trigger",
                              "set_value", "increment", "decrement", "select_option",
                              "press", "send_command", "lock", "unlock", "open_cover",
                              "close_cover", "stop_cover", "set_temperature"):
                    continue
                # Filter: glob/wildcard placeholders in markdown/comments
                if obj_id.endswith(("_", "_x", "_*")):
                    continue
                if eid in live_ids:
                    continue
                # Heuristic: a real reference sits on a yaml-key line that's specifically
                # entity_id / target / friendly mention. Service calls and prose are out.
                if any(k in line for k in ("entity_id:", "target:", "  - sensor.",
                                            "  - binary_sensor.", "  - automation.",
                                            "  - input_", "device_id:", "area_id:")):
                    findings.append({
                        "entity_id": eid, "file": str(f.relative_to(f.parents[len(f.parents) - 1])),
                        "line": ln_no, "context": stripped[:120],
                    })
    # Dedup by (entity_id, file)
    seen = set()
    unique = []
    for x in findings:
        key = (x["entity_id"], x["file"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(x)
    return unique


# ---- check-repairs --------------------------------------------------------

async def check_repairs(ha_url: str, token: str) -> list[dict]:
    """Pull active repairs/issues from HA."""
    async with websockets.connect(f"{ha_url.replace('http', 'ws')}/api/websocket",
                                  max_size=64 * 1024 * 1024) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        await ws.recv()
        await ws.send(json.dumps({"id": 1, "type": "repairs/list_issues"}))
        r = json.loads(await ws.recv())
        if not r.get("success"):
            return [{"error": r.get("error", {}).get("message", "?")}]
        return r["result"].get("issues", [])


# ---- find-unused-sensors --------------------------------------------------

def find_unused_sensors(yaml_files: list[Path]) -> list[dict]:
    """Find template sensors / customize entries defined but never referenced.

    Only scans files that look like sensor-definition packages (skips dashboards
    where `name:` is a UI label, not a sensor name).
    """
    defined: dict[str, Path] = {}
    referenced: set[str] = set()
    for f in yaml_files:
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        # Skip dashboard files - their `name:` lines are UI labels, not sensors
        if "dashboards" in f.parts:
            # Still harvest references from them
            for m in ENTITY_RE.finditer(text):
                referenced.add(m.group(2))
            continue
        # Skip automation files - `alias:` is the automation name, not a sensor
        if f.name == "automations.yaml":
            for m in ENTITY_RE.finditer(text):
                referenced.add(m.group(2))
            continue
        # Defined: lines like "  - name: foo" or "  foo:" inside a sensor: block
        for m in re.finditer(r"^\s+-?\s*(?:name|alias):\s*['\"]?([a-zA-Z0-9_ -]+)", text, re.MULTILINE):
            name = m.group(1).strip()
            slug = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")
            if slug and slug not in defined:
                defined[slug] = f
        # Referenced: any token matching an entity_id pattern
        for m in ENTITY_RE.finditer(text):
            referenced.add(m.group(2))

    findings = []
    for slug, f in defined.items():
        if slug not in referenced:
            findings.append({"slug": slug, "file": str(f.name)})
    return findings


# ---- main -----------------------------------------------------------------

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ha-url", default="http://192.168.0.94:8124")
    ap.add_argument("--config-dir", default=r"C:\Users\jovia\ha_dashboards")
    ap.add_argument("--secrets", default=r"C:\Users\jovia\mesh.secrets.env")
    ap.add_argument("--exit-on-findings", action="store_true")
    args = ap.parse_args()

    # CM5 uses HA_TOKEN; sandbox uses HA_ADMIN_TOKEN
    prefer = "HA_TOKEN" if "192.168.0.50" in args.ha_url else "HA_ADMIN_TOKEN"
    token = load_token(Path(args.secrets), prefer=prefer)
    config_dir = Path(args.config_dir)
    yaml_files = gather_yaml_files(config_dir) if config_dir.exists() else []

    print(f"=== ha_audit ({args.ha_url}) ===")
    print(f"  config dir: {config_dir}  ({len(yaml_files)} yaml files)")
    print()

    # 1. dangling refs
    print("[1/3] find-dangling-refs")
    dangling = await find_dangling_refs(args.ha_url, token, yaml_files)
    if dangling:
        for x in dangling[:20]:
            print(f"  X {x['entity_id']:50s} {x['file']}:{x['line']}")
        print(f"  ({len(dangling)} dangling refs total)")
    else:
        print("  OK no dangling references")
    print()

    # 2. unused sensors
    print("[2/3] find-unused-sensors")
    unused = find_unused_sensors(yaml_files) if yaml_files else []
    if unused:
        for x in unused[:20]:
            print(f"  ? {x['slug']:50s} {x['file']}")
        print(f"  ({len(unused)} potentially unused)")
    else:
        print("  OK none flagged")
    print()

    # 3. repairs
    print("[3/3] check-repairs (HA active issues)")
    issues = await check_repairs(args.ha_url, token)
    if issues:
        for x in issues[:20]:
            domain = x.get("domain", "?")
            issue_id = x.get("issue_id", "?")
            severity = x.get("severity", "?")
            print(f"  X {severity:8s} {domain:20s} {issue_id}")
        print(f"  ({len(issues)} active issues)")
    else:
        print("  OK no active issues")

    total_findings = len(dangling) + len(unused) + len(issues)
    print()
    print(f"=== summary: {total_findings} findings ===")

    if args.exit_on_findings and total_findings > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
