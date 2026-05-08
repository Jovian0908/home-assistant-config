"""HACS bulk-install for Phase 2 dashboard plugins (2026-05-07).

Connects to sandbox HA WebSocket API and drives HACS to:
  1. Add 12 frontend plugin repositories
  2. Install the latest release of each
  3. Register lovelace resources (auto via HACS)

Run: python scripts/hacs_install_phase2_plugins.py
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import websockets

# --- Config -----------------------------------------------------------------
HA_URL = "ws://192.168.0.94:8124/api/websocket"
SECRETS = Path(r"C:\Users\jovia\mesh.secrets.env")

PLUGINS = [
    # (full_name, category, description)
    ("piitaya/lovelace-mushroom",                "plugin", "Mushroom cards"),
    ("Clooos/Bubble-Card",                       "plugin", "Bubble Card 3.1.5+"),
    ("thomasloven/lovelace-card-mod",            "plugin", "card-mod 4.x"),
    ("custom-cards/button-card",                 "plugin", "button-card"),
    ("RomRider/apexcharts-card",                 "plugin", "ApexCharts card"),
    ("thomasloven/lovelace-auto-entities",       "plugin", "auto-entities"),
    ("custom-cards/decluttering-card",           "plugin", "decluttering-card"),
    ("thomasloven/lovelace-layout-card",         "plugin", "layout-card"),
    ("bramkragten/swipe-card",                   "plugin", "swipe-card"),
    ("dermotduffy/advanced-camera-card",         "plugin", "advanced-camera-card v3"),
    ("kalkih/mini-media-player",                 "plugin", "mini-media-player"),
    # Note: floor3d-pro-card uses a different repo pattern; will install separately
]


def load_token() -> str:
    for line in SECRETS.read_text(encoding="utf-8").splitlines():
        if line.startswith("HA_ADMIN_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("HA_ADMIN_TOKEN missing in mesh.secrets.env")


async def cmd(ws, msg_id: int, payload: dict, timeout: float = 30.0) -> dict:
    """Send a WS command, await the matching response."""
    payload = dict(payload, id=msg_id)
    await ws.send(json.dumps(payload))
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            return {"success": False, "error": {"message": "timeout"}, "id": msg_id}
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        except asyncio.TimeoutError:
            return {"success": False, "error": {"message": "timeout"}, "id": msg_id}
        msg = json.loads(raw)
        if msg.get("id") == msg_id and msg.get("type") == "result":
            return msg


async def main():
    token = load_token()
    print(f"connecting {HA_URL}")
    async with websockets.connect(HA_URL, max_size=64 * 1024 * 1024) as ws:
        # Auth handshake
        hello = json.loads(await ws.recv())
        assert hello["type"] == "auth_required", hello
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        ok = json.loads(await ws.recv())
        if ok["type"] != "auth_ok":
            raise SystemExit(f"auth failed: {ok}")
        print(f"auth ok (HA {ok.get('ha_version','?')})")

        # Wait for HACS to be ready (poll repositories list)
        print("\nwaiting for HACS to initialize repositories...")
        msg_id = 1
        for attempt in range(20):
            r = await cmd(ws, msg_id, {"type": "hacs/repositories/list"}, timeout=60)
            msg_id += 1
            if r.get("success"):
                count = len(r.get("result") or [])
                print(f"  attempt {attempt+1}: HACS knows {count} repos")
                if count > 0:
                    break
            else:
                err = r.get("error", {}).get("message", "?")
                print(f"  attempt {attempt+1}: hacs/repositories/list not ready ({err})")
            await asyncio.sleep(6)
        else:
            raise SystemExit("HACS never became ready")

        # Add + install each plugin
        print(f"\ninstalling {len(PLUGINS)} plugins")
        results = []
        for full_name, category, desc in PLUGINS:
            print(f"\n--- {full_name} ({desc}) ---")

            # 1. Add repository
            r = await cmd(ws, msg_id, {
                "type": "hacs/repositories/add",
                "repository": full_name,
                "category": category,
            }, timeout=45)
            msg_id += 1
            if not r.get("success"):
                err = r.get("error", {}).get("message", "?")
                if "already" in err.lower():
                    print(f"  add: already added (continuing)")
                else:
                    print(f"  add FAILED: {err}")
                    results.append((full_name, "add-fail", err))
                    continue
            else:
                print(f"  add ok")

            # 2. Look up repository id (HACS list is huge so this is slow)
            rlist = await cmd(ws, msg_id, {"type": "hacs/repositories/list"}, timeout=60)
            msg_id += 1
            repo_id = None
            for repo in rlist.get("result") or []:
                if repo.get("full_name", "").lower() == full_name.lower():
                    repo_id = repo.get("id")
                    break
            if not repo_id:
                print(f"  lookup FAILED -- repo not in list")
                results.append((full_name, "lookup-fail", ""))
                continue
            print(f"  repo_id={repo_id}")

            # 3. Install latest version (HACS calls it "download")
            r = await cmd(ws, msg_id, {
                "type": "hacs/repository/download",
                "repository": str(repo_id),
            }, timeout=180)
            msg_id += 1
            if not r.get("success"):
                err = r.get("error", {}).get("message", "?")
                print(f"  install FAILED: {err}")
                results.append((full_name, "install-fail", err))
                continue
            print(f"  install ok")
            results.append((full_name, "ok", ""))

        # Summary
        print(f"\n=== summary ===")
        ok_count = sum(1 for r in results if r[1] == "ok")
        print(f"installed {ok_count} / {len(PLUGINS)}")
        for full_name, status, msg in results:
            tag = "OK" if status == "ok" else f"FAIL ({status})"
            extra = f" -- {msg}" if msg else ""
            print(f"  [{tag:18s}] {full_name}{extra}")


if __name__ == "__main__":
    asyncio.run(main())
