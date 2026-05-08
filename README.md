# home-assistant-config

[![ha-version](https://img.shields.io/badge/HA-2026.5.0-41bdf5?logo=home-assistant)](https://home-assistant.io)
[![python](https://img.shields.io/badge/python-3.14-3776AB?logo=python)](https://python.org)
[![license](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![ci](https://github.com/Jovian0908/home-assistant-config/actions/workflows/ci.yml/badge.svg)](https://github.com/Jovian0908/home-assistant-config/actions/workflows/ci.yml)

> Home Assistant config + a custom 12-tool LLM API + a self-healing watchdog package + a self-documenting audit toolchain. Sandbox-first, lockout-ready.

This is the public extraction of a private mesh-AI build. The mesh services themselves (Council, ARIA, Knowledge, Vision, Genesis, ...) are not in this repo - what's here is the **HA-side surface**: the integration that exposes those services to the conversation agent, the dashboard that surfaces their state, and the operations toolchain that keeps the install honest.

## Highlights

- **`custom_components/mesh_llm/`** - registers a custom HA `llm.API` with **12 `llm.Tool` subclasses** (`mesh_council_decide`, `mesh_aria_research`, `mesh_knowledge_search`, `mesh_vision_describe`, ...). Each wraps a backend HTTP endpoint with `voluptuous` parameter validation. Drop into any HA, point it at your services, and the conversation agent gains 12 new abilities.
- **`packages/watchdogs.yaml`** - 3 self-healing automations + helpers + status template sensor. Automation Watchdog re-enables disabled automations every 5 min. Quiet-mode 9h backstop. Mesh-degraded alert. **Chaos drill passes**: disable any automation, watchdog re-enables it on the next tick.
- **`dashboards/mesh-renovation.yaml`** - 6-section Lovelace (Sections layout), uses Bubble Card / Mushroom / advanced-camera-card / floor3d-pro-card.
- **`scripts/ha_audit.py`** - basnijholt-pattern combined audit: find-dangling-refs + find-unused-sensors + check-repairs (HA WebSocket `repairs/list_issues`).
- **`scripts/ha_doc_generator.py`** - auto-rebuilds **`docs/family-manual.md`** + **`docs/technical-manual.md`** from live HA state + mesh tool registry. Optional pandoc -> PDF.
- **`scripts/flagship_demo_drive.py`** - drives the 6-act voice demo via HA conversation API and captures the transcript.

## The 12 mesh tools

| Tool | Purpose |
|---|---|
| `mesh_council_decide` | Multi-model deep-reasoning chain (planner + reviewer + judge) |
| `mesh_knowledge_search` | Vector search across personal knowledge corpus |
| `mesh_knowledge_ingest` | Persist a note/observation to the knowledge base |
| `mesh_scene_current` | Current home scene narrative (presence + objects + activity) |
| `mesh_vision_describe` | Latest VLM scene description for one camera |
| `mesh_vision_list_recent` | Recent retained scene/detected payloads |
| `mesh_aria_research` | Spawn an async research project (returns `task_id`) |
| `mesh_aria_recall` | List recent research projects, filterable |
| `mesh_sentiment_analyze` | Classify text sentiment + emotion tags |
| `mesh_routine_predict` | Predict likely routine from time + presence |
| `mesh_memory_recall` | Search episodic memory |
| `mesh_genesis_spawn` | (DANGEROUS) Auto-code a new mesh capability |

Each tool definition lives in `custom_components/mesh_llm/api.py` and subclasses `homeassistant.helpers.llm.Tool`.

## Flagship demo

`docs/flagship-demo-transcript.md` is the captured 6-act voice demo. Real HTTP POSTs to HA's `/api/conversation/process`; tool-call routing proven by mesh-side service hits. Replay:

```bash
python scripts/flagship_demo_drive.py
```

## Architecture

```
   You speak                  HA Voice Pipeline                 Ollama (qwen2.5:14b)
       v                                                                v
[ HomePod / phone / tablet ] -> Whisper -> conversation.mesh_ai_final -> LLM
                                                |                        |
                                                |   tool-call decision   |
                                                |<-----------------------|
                                                v
                                  custom_components/mesh_llm
                                                |
                              12 llm.Tool subclasses (this repo)
                                                |
                          +---------------------+----------------------+
                          v        v        v        v        v        v
                    Council    ARIA   Knowledge  Vision  Sentiment  Memory ...
                    (mesh services - separate private codebase)
```

The mesh services themselves are not public; this repo is the surface that any HA install needs to consume them.

## Self-healing

`packages/watchdogs.yaml` defines:

1. **`watchdog_re_enable_disabled_automation`** - polls every 5 min, re-enables anything `off`. Counter `counter.watchdog_reenable_count` tracks lifetime re-enables.
2. **`watchdog_force_clear_quiet_mode_after_8h`** - if the kill-switch input_boolean stays on for 9+ hours, force-clear it.
3. **`watchdog_mesh_service_offline_alert`** - persistent notification when `sensor.mesh_activity_tier` goes unavailable for 5+ min.

Aggregate: `sensor.watchdog_status` -> `healthy | quiet | mesh degraded`.

## Self-documenting

`scripts/ha_doc_generator.py` rebuilds two manuals from live HA state:

- **`docs/family-manual.md`** - plain-language, sized for printing and putting on the fridge
- **`docs/technical-manual.md`** - full inventory + mesh tool registry + recovery procedures + lockout protocol

Run nightly via cron / Task Scheduler. Optional pandoc step generates PDFs.

## Auditing

`scripts/ha_audit.py` runs three checks in one shot against your live HA:

```
[1/3] find-dangling-refs       (entity refs in YAML that don't exist in /api/states)
[2/3] find-unused-sensors      (sensors defined but never referenced)
[3/3] check-repairs            (HA WebSocket repairs/list_issues)
```

Run via cron; gate CI on `--exit-on-findings`.

## Repo layout (Frenck-pattern)

```
configuration.yaml          - top-level (packages directive, lovelace yaml mode)
automations.yaml            - root automations (watchdogs live in packages/)
packages/                   - one file per concern
  watchdogs.yaml            - self-healing layer
custom_components/
  mesh_llm/                 - the 12-tool API
dashboards/
  mesh-renovation.yaml      - 6-section Lovelace
scripts/
  ha_audit.py               - combined audit
  ha_doc_generator.py       - dual-manual generator
  flagship_demo_drive.py    - 6-act demo runner
  hacs_install_phase2_plugins.py  - bulk HACS plugin installer
docs/
  family-manual.md          - generated
  technical-manual.md       - generated
  flagship-demo-transcript.md  - captured 2026-05-07
.github/workflows/
  ci.yml                    - matrix CI vs HA stable/beta/dev
secrets.fake.yaml           - committed fake secrets for CI
```

## CI

`.github/workflows/ci.yml` runs `ha core check` against a matrix of HA versions on every push. `secrets.fake.yaml` provides values for any `!secret` references so the check works without leaking real secrets. `actionlint` validates the workflows. `zizmor` security-scans them.

## Setup (your HA)

1. Drop `configuration.yaml`, `packages/`, `automations.yaml`, `dashboards/` into `/config/`.
2. Drop `custom_components/mesh_llm/` into `/config/custom_components/`.
3. Set `MESH_TOKEN`, `MESH_BRIDGE_URL`, `MESH_KNOWLEDGE_URL`, etc. on the HA container (via `env_file:` in your compose, or `homeassistant.os.options.env`).
4. Restart HA.
5. Add the integration: **Settings -> Devices & Services -> Add Integration -> Mesh LLM**.
6. Wire it to your conversation agent: **Settings -> Voice assistants -> [your assistant] -> Conversation agent: Ollama** -> **Control Home Assistant: yes** -> **API: Mesh LLM**.
7. Voice prompt: *"Use mesh_scene_current to tell me the scene"* - if the conversation agent calls back with a scene narrative, you're wired.

## Credits

Patterns studied / adapted from:

- **[frenck/home-assistant-config](https://github.com/frenck/home-assistant-config)** - packages-per-concern, CI matrix, secrets.fake.yaml
- **[basnijholt/home-assistant-config](https://github.com/basnijholt/home-assistant-config)** - self-audit + self-doc + GitHub-permalinked README pattern
- **[CCOSTAN/Home-AssistantConfig](https://github.com/CCOSTAN/Home-AssistantConfig)** - docs-as-product
- **[Madelena/hass-config-public](https://github.com/Madelena/hass-config-public)** - lovelace-resources + dashboard masterclass
- **[aradlein/hass-agent-llm](https://github.com/aradlein/hass-agent-llm)** - the `llm.API` + `llm.Tool` reference implementation

## License

MIT - see [LICENSE](LICENSE).
