r"""ha_doc_generator.py - basnijholt-style auto-generated dual manuals.

Produces two markdown files (and optionally PDFs via pandoc):
  1. docs/family-manual.md      audience: you + family/housemates
  2. docs/technical-manual.md   audience: future-me, saved for callback day

Phase 5 of the renovation v2 (2026-05-08). Lockout-resilience pillar:
both manuals auto-rebuild from live HA state + mesh service registry without
me touching HA UI.

Sources read:
  - HA /api/states (live entity inventory, areas, friendly names)
  - HA /api/config/area_registry/list via WebSocket (areas + assignments)
  - C:\Users\jovia\CLAUDE.md (mesh ops guide)
  - C:\Users\jovia\custom_components\mesh_llm\api.py (mesh tool registry)
  - docs/flagship-demo-transcript.md (Phase 1d artifact)

Run:
  python scripts/ha_doc_generator.py [--no-pdf]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import websockets


SECRETS = Path(r"C:\Users\jovia\mesh.secrets.env")
HA_URL = "http://192.168.0.94:8124"
DOCS_DIR = Path(r"C:\Users\jovia\docs")
CLAUDE_MD = Path(r"C:\Users\jovia\CLAUDE.md")
MESH_LLM_API = Path(r"C:\Users\jovia\custom_components\mesh_llm\api.py")
DEMO_TRANSCRIPT = Path(r"C:\Users\jovia\docs\flagship-demo-transcript.md")


def load_token() -> str:
    for line in SECRETS.read_text(encoding="utf-8").splitlines():
        if line.startswith("HA_ADMIN_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(f"HA_ADMIN_TOKEN missing")


async def fetch_ha_state(token: str) -> dict:
    """Pull entities + area registry + integration list."""
    async with websockets.connect(f"{HA_URL.replace('http', 'ws')}/api/websocket",
                                  max_size=64 * 1024 * 1024) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        ack = json.loads(await ws.recv())
        if ack.get("type") != "auth_ok":
            raise SystemExit(f"auth: {ack}")

        async def cmd(payload, idn):
            await ws.send(json.dumps(dict(payload, id=idn)))
            return json.loads(await ws.recv())

        states = (await cmd({"type": "get_states"}, 1)).get("result", [])
        areas = (await cmd({"type": "config/area_registry/list"}, 2)).get("result", [])
        config = (await cmd({"type": "get_config"}, 3)).get("result", {})

    by_domain = {}
    for s in states:
        d = s["entity_id"].split(".")[0]
        by_domain.setdefault(d, []).append(s)

    return {
        "states": states,
        "areas": areas,
        "config": config,
        "by_domain": by_domain,
    }


def parse_mesh_tools() -> list[dict]:
    """Extract mesh tool list from custom_components/mesh_llm/api.py."""
    if not MESH_LLM_API.exists():
        return []
    text = MESH_LLM_API.read_text(encoding="utf-8")
    tools = []
    for m in re.finditer(r"class (Mesh\w+)\(llm\.Tool\):", text):
        cls_name = m.group(1)
        # Find name/description in this class block
        block_start = m.end()
        block_end = text.find("\nclass ", block_start)
        if block_end == -1:
            block_end = text.find("\n# ----", block_start)
        block = text[block_start:block_end] if block_end > 0 else text[block_start:]
        name_m = re.search(r'name = "([^"]+)"', block)
        desc_m = re.search(r'description = \(\s*"([^"]+)"', block, re.DOTALL)
        if name_m:
            tools.append({
                "class": cls_name,
                "name": name_m.group(1),
                "description": desc_m.group(1) if desc_m else "",
            })
    return tools


def gen_family_manual(ha: dict, mesh_tools: list[dict]) -> str:
    """Family-grade manual: large-icon, plain-language, recipe-style."""
    states = ha["states"]
    areas = ha["areas"]
    config = ha["config"]

    lights = [s for s in states if s["entity_id"].startswith("light.")]
    media = [s for s in states if s["entity_id"].startswith("media_player.")]
    climate = [s for s in states if s["entity_id"].startswith("climate.")]
    locks = [s for s in states if s["entity_id"].startswith("lock.")]

    lines = [
        "# Mesh AI - Family Manual",
        "",
        f"_Auto-generated {datetime.now().strftime('%B %d, %Y')}._  Reprint anytime: `python ha_doc_generator.py`.",
        "",
        f"**Your home**: {config.get('location_name', '?')} - {config.get('time_zone', '?')}",
        "**Areas**: " + (", ".join([a["name"] for a in areas]) if areas else "_(no areas defined yet)_"),
        "",
        "---",
        "",
        "## 1. Talking to the house",
        "",
        "Just say what you want. The house listens through your HomePods, your phone's HA Companion app, and the wall tablets. You can also type into the HA dashboard.",
        "",
        "**Things you can ask:**",
        "- 'What's my current scene?'  -> tells you who/what is happening at home",
        "- 'Search my notes for [topic]'  -> finds anything you've written down",
        "- 'List my aria research projects'  -> recap of past research the house ran",
        "- 'Council, should I [decision]?'  -> deep-think reasoning",
        "- 'Save this note: [text]'  -> pins a thought to your knowledge base",
        "- Standard requests like 'turn off the kitchen lights' work too.",
        "",
        "**If voice doesn't respond**: press the Zigbee button by the bed to reset quiet mode (the kill switch). See section 6 for troubleshooting.",
        "",
        "---",
        "",
        "## 2. The basics",
        "",
        f"### Lights ({len(lights)} total)",
        "",
    ]
    if lights:
        for l in sorted(lights, key=lambda x: x["entity_id"])[:20]:
            fn = l.get("attributes", {}).get("friendly_name", l["entity_id"])
            state = l["state"]
            lines.append(f"- **{fn}** - currently *{state}*")
        if len(lights) > 20:
            lines.append(f"- _(+{len(lights) - 20} more)_")
    else:
        lines.append("_(no lights configured yet)_")

    lines.extend([
        "",
        f"### Climate ({len(climate)} thermostats)",
        "",
    ])
    if climate:
        for c in climate:
            fn = c.get("attributes", {}).get("friendly_name", c["entity_id"])
            state = c["state"]
            temp = c.get("attributes", {}).get("current_temperature", "?")
            lines.append(f"- **{fn}** - {state}, current {temp} deg")
    else:
        lines.append("_(no thermostats yet)_")

    lines.extend([
        "",
        f"### Media players ({len(media)})",
        "",
    ])
    if media:
        for m in media:
            fn = m.get("attributes", {}).get("friendly_name", m["entity_id"])
            lines.append(f"- **{fn}** - {m['state']}")
    else:
        lines.append("_(no media players yet)_")

    lines.extend([
        "",
        f"### Locks ({len(locks)})",
        "",
    ])
    if locks:
        for l in locks:
            fn = l.get("attributes", {}).get("friendly_name", l["entity_id"])
            lines.append(f"- **{fn}** - {l['state']}")
    else:
        lines.append("_(no smart locks yet)_")

    lines.extend([
        "",
        "---",
        "",
        "## 3. The Mesh AI dashboard",
        "",
        f"Visit `http://{config.get('internal_url') or '192.168.0.50'}:8123/mesh-renovation` on any device.",
        "",
        "**Six sections** along the bottom nav:",
        "- **Home** - activity tier, voice activity, presence, climate",
        "- **AI Status** - what the mesh's AI is doing right now",
        "- **Energy** - power use + plug control",
        "- **Cameras** - Frigate timeline + recognized arrivals",
        "- **Floor3D** - 3D floorplan (when configured)",
        "- **System** - health + watchdogs",
        "",
        "Tap any tile for more info. The dashboard is mobile-friendly.",
        "",
        "---",
        "",
        "## 4. The Zigbee kill switch",
        "",
        "**One press** = the mesh shuts up for 8 hours. Lights stop firing autonomously, voice greetings stop, AI loops pause. Useful when you're trying to sleep, watching a movie, or just don't want the house chatting at you.",
        "",
        "**Double press** = cancel quiet mode immediately.",
        "",
        "**Auto-clears** after 8 hours so the system comes back on its own.",
        "",
        "---",
        "",
        "## 5. Things the AI Mesh can do for you",
        "",
        "Each capability below is a 'tool' your voice assistant can call. Just ask in plain English.",
        "",
    ])
    if mesh_tools:
        for t in mesh_tools:
            short_desc = t["description"].replace("\n", " ").split(". ")[0]
            lines.append(f"- **`{t['name']}`** - {short_desc}.")
    else:
        lines.append("_(mesh tool list missing - regenerate)_")

    lines.extend([
        "",
        "---",
        "",
        "## 6. Common troubleshooting",
        "",
        "| Problem | Try this first |",
        "|---|---|",
        "| Voice doesn't respond | Press Zigbee kill-switch button twice (cancels quiet mode) |",
        "| Light won't turn on/off | Check the dashboard: is the device 'unavailable'? Power-cycle it. |",
        "| Camera not showing | Frigate is running on the CM5; check its addon log via HA UI. |",
        "| 'Mesh AI doesn't know X' | Try rephrasing - the AI uses tools like 'search my notes' or 'use council'. |",
        "| Whole house seems offline | Check Wi-Fi first; then the CM5 (lit on the side); then your laptop running the mesh. |",
        "| Wall tablet won't load | Hard-refresh the page (long-press refresh in the HA app). |",
        "| 'I want to silence the AI for a while' | Hold the Zigbee button - quiet mode for 8 hours. |",
        "| Nothing helps | Open `https://192.168.0.50:8123/repairs` - HA self-diagnoses most issues. |",
        "",
        "---",
        "",
        f"_Document built from live HA state. {len(states)} entities tracked, {len(mesh_tools)} mesh AI tools available._",
    ])

    return "\n".join(lines)


def gen_technical_manual(ha: dict, mesh_tools: list[dict]) -> str:
    """Technical manual: full inventory, design rationale, recovery procedures."""
    states = ha["states"]
    areas = ha["areas"]
    by_domain = ha["by_domain"]
    config = ha["config"]

    lines = [
        "# Mesh AI - Technical Manual",
        "",
        f"_Auto-generated {datetime.now().isoformat()}._",
        f"_HA version: {config.get('version')}, components: {len(config.get('components', []))}._",
        "",
        "Audience: future-me, called back to extend or repair after a lockout. Read this before touching anything.",
        "",
        "---",
        "",
        "## 1. Architecture summary",
        "",
        "**Two HA instances, parallel**:",
        "- **CM5 HAOS at 192.168.0.50:8123** - production, controls real devices, all addons.",
        "- **mesh-ha-sandbox on AM5 at 192.168.0.94:8124** - parallel rebuild target, isolated config volume.",
        "",
        "**Mesh on AM5 (192.168.0.94)** - Docker compose stack of 38+ services. See `C:\\Users\\jovia\\docker-compose.yml`. Renovation added `mesh-mcp-bridge` (:7060) and `mesh-ha-sandbox`.",
        "",
        "**MCP plumbing (Phase 1)**:",
        "- `mesh-mcp-bridge` exposes 12 mesh capabilities as MCP tools (FastMCP, streamable-HTTP transport at /mcp).",
        "- HA's MCP Client integration consumes the bridge.",
        "- Parallel native path: `custom_components/mesh_llm` registers the same 12 tools as `llm.Tool` subclasses for tighter HA-native integration.",
        "- The conversation agent uses `mesh_llm` (more reliable than MCP transport for our load profile).",
        "",
        "---",
        "",
        f"## 2. Entity inventory ({len(states)} total)",
        "",
        "Breakdown by domain:",
        "",
        "| Domain | Count |",
        "|---|---|",
    ]
    for d, items in sorted(by_domain.items(), key=lambda x: -len(x[1])):
        lines.append(f"| `{d}` | {len(items)} |")

    lines.extend([
        "",
        "### Unavailable entities",
        "",
    ])
    unavail = [s for s in states if s["state"] in ("unavailable", "unknown")]
    if unavail:
        lines.append(f"_{len(unavail)} entities currently unavailable. {len(unavail)/max(1,len(states))*100:.1f}% of total._")
        lines.append("")
        lines.append("Top 30:")
        lines.append("")
        for s in sorted(unavail, key=lambda x: x["entity_id"])[:30]:
            lines.append(f"- `{s['entity_id']}` - state `{s['state']}`")
        if len(unavail) > 30:
            lines.append(f"- _(+{len(unavail)-30} more)_")
    else:
        lines.append("None.")

    lines.extend([
        "",
        "---",
        "",
        f"## 3. Areas ({len(areas)})",
        "",
    ])
    if areas:
        for a in areas:
            lines.append(f"- **{a['name']}** (id `{a['area_id']}`)")
    else:
        lines.append("_No areas defined - unbuilt territory._")

    lines.extend([
        "",
        "---",
        "",
        f"## 4. Mesh tool registry ({len(mesh_tools)} tools)",
        "",
        "Each tool lives in `custom_components/mesh_llm/api.py` and subclasses `homeassistant.helpers.llm.Tool`.",
        "",
    ])
    for t in mesh_tools:
        lines.append(f"### `{t['name']}`")
        lines.append("")
        lines.append(f"_Class: `{t['class']}`_")
        lines.append("")
        lines.append(t["description"][:500])
        lines.append("")

    lines.extend([
        "",
        "---",
        "",
        "## 5. Recovery procedures",
        "",
        "### CM5 HAOS won't boot",
        "1. Check power LED on CM5; if off, reseat the CM5.",
        "2. Plug a monitor into HDMI; look for boot messages.",
        "3. SSH from AM5: `ssh root@192.168.0.50` (works only if SSH addon is up).",
        "4. If unrecoverable: restore from `MeshBackup` task's nightly snapshot. See backups in `~/backups/`.",
        "",
        "### Sandbox HA won't start",
        "1. `docker compose --profile sandbox up -d ha-sandbox` to recreate.",
        "2. Logs: `docker logs mesh-ha-sandbox --tail 50`.",
        "3. If config volume corrupt: `docker volume rm mesh-ha-sandbox-config-data && docker compose --profile sandbox up -d ha-sandbox` (fresh slate).",
        "",
        "### Mesh CPU storm",
        "1. Run `C:\\Users\\jovia\\scripts\\mesh_cpu_watchdog.ps1` manually.",
        "2. Check `C:\\Users\\jovia\\logs\\watchdog\\latest-trigger.json` for the trigger reason.",
        "3. Run `mesh_docker_recover.ps1` (elevated) if Docker daemon is stuck.",
        "",
        "### Conversation agent returns garbled / non-English",
        "1. qwen2.5:14b is the supported model. Verify in HA UI -> Settings -> Devices -> Ollama.",
        "2. If model evicted: `curl http://192.168.0.94:11434/api/ps` and re-prompt to reload.",
        "3. Bump Ollama mem_limit if 32b is desired (currently 24GB; needs ~28GB to coexist with llama3).",
        "",
        "### Mesh tool returns 'unauthorized'",
        "1. `MESH_TOKEN` env var must be set on `mesh-ha-sandbox` container (env_file: mesh.secrets.env in compose).",
        "2. Verify: `docker exec mesh-ha-sandbox env | grep MESH_TOKEN`.",
        "",
        "---",
        "",
        "## 5b. Self-healing watchdogs (Phase 4 - LIVE)",
        "",
        "Three automations in `packages/watchdogs.yaml`:",
        "",
        "1. **`automation.watchdog_re_enable_disabled_automation`** - polls every 5 minutes, re-enables any automation that's currently `off`. Counter `counter.watchdog_reenable_count` tracks lifetime re-enables.",
        "2. **`automation.watchdog_force_clear_quiet_mode_after_8h`** - belt-and-suspenders: if `input_boolean.mesh_quiet_mode` is on for 9+ hours, force-clear it (the kill-switch's own 8h timer should fire first; this is the backstop).",
        "3. **`automation.watchdog_mesh_service_offline_alert`** - if `sensor.mesh_activity_tier` goes unavailable for 5+ minutes, log it and create a persistent notification ('Mesh degraded').",
        "",
        "Aggregate state: `sensor.watchdog_status` - one of `healthy` | `quiet` | `mesh degraded`. Surfaced on dashboard System section.",
        "",
        "**Chaos drill (passed 2026-05-08)**: turn off any automation -> watchdog re-enables it on next 5-min tick. Manual fast-path: `automation.trigger automation.watchdog_re_enable_disabled_automation`.",
        "",
        "**Deferred (CM5 cutover)**: Hardware Watchdog HAOS addon, Uptime Kuma core integration (CM5 already runs Kuma; integration adds binary_sensor per service for richer per-service watchdogs).",
        "",
        "---",
        "",
        "## 6. Lockout protocol (if I'm called back)",
        "",
        "**Read this first.** When I'm called back to extend or fix the system:",
        "1. Read `C:\\Users\\jovia\\CLAUDE.md` for current operations baseline.",
        "2. Read this technical manual for the renovation context.",
        "3. Read `docs/flagship-demo-transcript.md` for the canonical voice-pipeline test.",
        "4. Run `python scripts/ha_audit.py` to baseline health.",
        "5. Check `~/.claude/projects/C--/memory/project_mesh_daily.md` for recent state.",
        "",
        "Only after all five am I ready to act.",
        "",
        "---",
        "",
        "## 7. How to extend",
        "",
        "**Add a new mesh tool**:",
        "1. Add a backend HTTP endpoint to the relevant mesh service (e.g. POST `/foo` on `mesh-routine:5500`).",
        "2. In `custom_components/mesh_llm/api.py`, add a new `class MeshFoo(llm.Tool):` with `name`, `description`, `parameters: vol.Schema`, and an `async_call` that POSTs the endpoint.",
        "3. Append the class to `_TOOL_CLASSES` at the bottom of the file.",
        "4. Same in `MeshMcpBridge/app.py` (if you want it via MCP too).",
        "5. Restart sandbox HA. Verify the tool appears in `mesh_llm` API instance via WS query.",
        "",
        "**Add a new dashboard section**:",
        "1. Edit `C:\\Users\\jovia\\ha_dashboards\\mesh-renovation.yaml`.",
        "2. Add a `views: -` block (sections layout).",
        "3. `docker cp` updated YAML into sandbox: `docker cp ha_dashboards/mesh-renovation.yaml mesh-ha-sandbox:/config/dashboards/`.",
        "4. Restart HA or save via UI.",
        "",
        "**Migrate sandbox to CM5**:",
        "1. Run `python scripts/ha_audit.py` first - must be clean.",
        "2. Run the cutover procedure documented in `~/.claude/plans/ok-if-the-hardening-polished-pudding.md` Phase 7.",
        "3. Always backup CM5 first via `ha backups new`.",
        "",
        "---",
        "",
        "## 8. Design rationale",
        "",
        "**Why MCP + native llm.Tool both?** MCP gives discoverability + standard transport for cross-system tool-sharing. Native `llm.Tool` gives tighter HA integration without protocol overhead. Both wrap the same backend HTTP endpoints. Use MCP when external systems need access; use native when only HA needs them.",
        "",
        "**Why qwen2.5:14b not 32b?** 32b's tool-calling is more reliable but it needs ~17.6 GiB system memory for spillover, while llama3 is normally resident at 6 GiB. Net VRAM/RAM budget tight. 14b fits comfortably and tool-calls reliably for the 12-tool surface. Bump to 32b after VRAM upgrade or model-residency tuning.",
        "",
        "**Why sandbox-first?** Cutover is a 5-minute window of CM5 downtime. By building parallel, drift testing happens against real mesh services without risking daily home control. Once sandbox scores 11/12 on the rubric, rsync to CM5.",
        "",
        f"_End of technical manual. Auto-built {datetime.now().isoformat()}._",
    ])

    return "\n".join(lines)


def maybe_pdf(md_path: Path) -> Path | None:
    """Try pandoc -> PDF; fall back gracefully if pandoc not installed."""
    if shutil.which("pandoc") is None:
        return None
    pdf_path = md_path.with_suffix(".pdf")
    try:
        subprocess.run(
            ["pandoc", str(md_path), "-o", str(pdf_path),
             "--toc", "--toc-depth=2",
             "--metadata", f"title={md_path.stem.replace('-', ' ').title()}"],
            check=True, capture_output=True, timeout=60,
        )
        return pdf_path
    except Exception as e:
        print(f"  pandoc failed: {e}")
        return None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args()

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    token = load_token()

    print("=== fetching HA state ===")
    ha = await fetch_ha_state(token)
    print(f"  entities: {len(ha['states'])}")
    print(f"  areas:    {len(ha['areas'])}")

    print()
    print("=== parsing mesh tools ===")
    tools = parse_mesh_tools()
    print(f"  tools:    {len(tools)}")

    print()
    print("=== generating family-manual.md ===")
    family = gen_family_manual(ha, tools)
    family_path = DOCS_DIR / "family-manual.md"
    family_path.write_text(family, encoding="utf-8")
    print(f"  wrote {family_path}  ({len(family)} chars)")

    print()
    print("=== generating technical-manual.md ===")
    tech = gen_technical_manual(ha, tools)
    tech_path = DOCS_DIR / "technical-manual.md"
    tech_path.write_text(tech, encoding="utf-8")
    print(f"  wrote {tech_path}  ({len(tech)} chars)")

    if not args.no_pdf:
        print()
        print("=== attempting PDFs via pandoc ===")
        for p in (family_path, tech_path):
            pdf = maybe_pdf(p)
            if pdf:
                print(f"  PDF: {pdf}")
            else:
                print(f"  PDF skipped for {p.name} (pandoc missing or error)")


if __name__ == "__main__":
    asyncio.run(main())
