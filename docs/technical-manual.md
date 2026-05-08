# Mesh AI - Technical Manual

_Auto-generated 2026-05-07T20:50:07.219308._
_HA version: 2026.5.0, components: 156._

Audience: future-me, called back to extend or repair after a lockout. Read this before touching anything.

---

## 1. Architecture summary

**Two HA instances, parallel**:
- **CM5 HAOS at 192.168.0.50:8123** - production, controls real devices, all addons.
- **mesh-ha-sandbox on AM5 at 192.168.0.94:8124** - parallel rebuild target, isolated config volume.

**Mesh on AM5 (192.168.0.94)** - Docker compose stack of 38+ services. See `C:\Users\jovia\docker-compose.yml`. Renovation added `mesh-mcp-bridge` (:7060) and `mesh-ha-sandbox`.

**MCP plumbing (Phase 1)**:
- `mesh-mcp-bridge` exposes 12 mesh capabilities as MCP tools (FastMCP, streamable-HTTP transport at /mcp).
- HA's MCP Client integration consumes the bridge.
- Parallel native path: `custom_components/mesh_llm` registers the same 12 tools as `llm.Tool` subclasses for tighter HA-native integration.
- The conversation agent uses `mesh_llm` (more reliable than MCP transport for our load profile).

---

## 2. Entity inventory (80 total)

Breakdown by domain:

| Domain | Count |
|---|---|
| `sensor` | 33 |
| `update` | 14 |
| `conversation` | 7 |
| `binary_sensor` | 5 |
| `automation` | 4 |
| `select` | 4 |
| `switch` | 2 |
| `event` | 1 |
| `zone` | 1 |
| `person` | 1 |
| `counter` | 1 |
| `input_boolean` | 1 |
| `sun` | 1 |
| `todo` | 1 |
| `tts` | 1 |
| `weather` | 1 |
| `button` | 1 |
| `number` | 1 |

### Unavailable entities

_14 entities currently unavailable. 17.5% of total._

Top 30:

- `binary_sensor.edge_brain_hailo_edge_cpu_throttled_now` - state `unknown`
- `binary_sensor.edge_brain_hailo_edge_cpu_under_voltage_now` - state `unknown`
- `button.zigbee2mqtt_bridge_restart` - state `unknown`
- `conversation.home_assistant` - state `unknown`
- `event.backup_automatic_backup` - state `unknown`
- `person.claude` - state `unknown`
- `select.kitchen_drawer_report_interval` - state `unknown`
- `select.kitchen_drawer_sensitivity_adjustment` - state `unknown`
- `sensor.backup_last_attempted_automatic_backup` - state `unknown`
- `sensor.backup_last_successful_automatic_backup` - state `unknown`
- `sensor.backup_next_scheduled_automatic_backup` - state `unknown`
- `sensor.edge_brain_hailo_edge_fan_rpm` - state `unknown`
- `sensor.edge_brain_hailo_edge_npu_power` - state `unknown`
- `tts.google_translate_en_com` - state `unknown`

---

## 3. Areas (3)

- **Living Room** (id `living_room`)
- **Kitchen** (id `kitchen`)
- **Bedroom** (id `bedroom`)

---

## 4. Mesh tool registry (12 tools)

Each tool lives in `custom_components/mesh_llm/api.py` and subclasses `homeassistant.helpers.llm.Tool`.

### `mesh_council_decide`

_Class: `MeshCouncilDecide`_

Use the mesh's Council deep-reasoning chain for multi-step thinking, 

### `mesh_knowledge_search`

_Class: `MeshKnowledgeSearch`_

Search 16,749 chunks of personal knowledge (notes, conversations, 

### `mesh_scene_current`

_Class: `MeshSceneCurrent`_

Get the current home scene narrative -- what's happening in the house 

### `mesh_vision_describe`

_Class: `MeshVisionDescribe`_

Get the latest scene description for one camera. Available: 

### `mesh_aria_research`

_Class: `MeshAriaResearch`_

Spawn an aria research project for a question that needs deep web 

### `mesh_aria_recall`

_Class: `MeshAriaRecall`_

List recent aria research projects, optionally filtered by topic substring. 

### `mesh_knowledge_ingest`

_Class: `MeshKnowledgeIngest`_

Save a text snippet (note, summary, observation) to personal knowledge 

### `mesh_sentiment_analyze`

_Class: `MeshSentimentAnalyze`_

Classify sentiment of a text (positive/neutral/negative + emotion tags). 

### `mesh_routine_predict`

_Class: `MeshRoutinePredict`_

Predict the user's likely current/upcoming routine based on time, 

### `mesh_memory_recall`

_Class: `MeshMemoryRecall`_

Search episodic memory (events, conversations, observations) for matches. 

### `mesh_vision_list_recent`

_Class: `MeshVisionListRecent`_

Get most-recent retained scene/detected payloads for one or all cameras. 

### `mesh_genesis_spawn`

_Class: `MeshGenesisSpawn`_

[DANGEROUS] Auto-code a new mesh capability. Genesis runs aria research, 


---

## 5. Recovery procedures

### CM5 HAOS won't boot
1. Check power LED on CM5; if off, reseat the CM5.
2. Plug a monitor into HDMI; look for boot messages.
3. SSH from AM5: `ssh root@192.168.0.50` (works only if SSH addon is up).
4. If unrecoverable: restore from `MeshBackup` task's nightly snapshot. See backups in `~/backups/`.

### Sandbox HA won't start
1. `docker compose --profile sandbox up -d ha-sandbox` to recreate.
2. Logs: `docker logs mesh-ha-sandbox --tail 50`.
3. If config volume corrupt: `docker volume rm mesh-ha-sandbox-config-data && docker compose --profile sandbox up -d ha-sandbox` (fresh slate).

### Mesh CPU storm
1. Run `C:\Users\jovia\scripts\mesh_cpu_watchdog.ps1` manually.
2. Check `C:\Users\jovia\logs\watchdog\latest-trigger.json` for the trigger reason.
3. Run `mesh_docker_recover.ps1` (elevated) if Docker daemon is stuck.

### Conversation agent returns garbled / non-English
1. qwen2.5:14b is the supported model. Verify in HA UI -> Settings -> Devices -> Ollama.
2. If model evicted: `curl http://192.168.0.94:11434/api/ps` and re-prompt to reload.
3. Bump Ollama mem_limit if 32b is desired (currently 24GB; needs ~28GB to coexist with llama3).

### Mesh tool returns 'unauthorized'
1. `MESH_TOKEN` env var must be set on `mesh-ha-sandbox` container (env_file: mesh.secrets.env in compose).
2. Verify: `docker exec mesh-ha-sandbox env | grep MESH_TOKEN`.

---

## 5b. Self-healing watchdogs (Phase 4 - LIVE)

Three automations in `packages/watchdogs.yaml`:

1. **`automation.watchdog_re_enable_disabled_automation`** - polls every 5 minutes, re-enables any automation that's currently `off`. Counter `counter.watchdog_reenable_count` tracks lifetime re-enables.
2. **`automation.watchdog_force_clear_quiet_mode_after_8h`** - belt-and-suspenders: if `input_boolean.mesh_quiet_mode` is on for 9+ hours, force-clear it (the kill-switch's own 8h timer should fire first; this is the backstop).
3. **`automation.watchdog_mesh_service_offline_alert`** - if `sensor.mesh_activity_tier` goes unavailable for 5+ minutes, log it and create a persistent notification ('Mesh degraded').

Aggregate state: `sensor.watchdog_status` - one of `healthy` | `quiet` | `mesh degraded`. Surfaced on dashboard System section.

**Chaos drill (passed 2026-05-08)**: turn off any automation -> watchdog re-enables it on next 5-min tick. Manual fast-path: `automation.trigger automation.watchdog_re_enable_disabled_automation`.

**Deferred (CM5 cutover)**: Hardware Watchdog HAOS addon, Uptime Kuma core integration (CM5 already runs Kuma; integration adds binary_sensor per service for richer per-service watchdogs).

---

## 6. Lockout protocol (if I'm called back)

**Read this first.** When I'm called back to extend or fix the system:
1. Read `C:\Users\jovia\CLAUDE.md` for current operations baseline.
2. Read this technical manual for the renovation context.
3. Read `docs/flagship-demo-transcript.md` for the canonical voice-pipeline test.
4. Run `python scripts/ha_audit.py` to baseline health.
5. Check `~/.claude/projects/C--/memory/project_mesh_daily.md` for recent state.

Only after all five am I ready to act.

---

## 7. How to extend

**Add a new mesh tool**:
1. Add a backend HTTP endpoint to the relevant mesh service (e.g. POST `/foo` on `mesh-routine:5500`).
2. In `custom_components/mesh_llm/api.py`, add a new `class MeshFoo(llm.Tool):` with `name`, `description`, `parameters: vol.Schema`, and an `async_call` that POSTs the endpoint.
3. Append the class to `_TOOL_CLASSES` at the bottom of the file.
4. Same in `MeshMcpBridge/app.py` (if you want it via MCP too).
5. Restart sandbox HA. Verify the tool appears in `mesh_llm` API instance via WS query.

**Add a new dashboard section**:
1. Edit `C:\Users\jovia\ha_dashboards\mesh-renovation.yaml`.
2. Add a `views: -` block (sections layout).
3. `docker cp` updated YAML into sandbox: `docker cp ha_dashboards/mesh-renovation.yaml mesh-ha-sandbox:/config/dashboards/`.
4. Restart HA or save via UI.

**Migrate sandbox to CM5**:
1. Run `python scripts/ha_audit.py` first - must be clean.
2. Run the cutover procedure documented in `~/.claude/plans/ok-if-the-hardening-polished-pudding.md` Phase 7.
3. Always backup CM5 first via `ha backups new`.

---

## 8. Design rationale

**Why MCP + native llm.Tool both?** MCP gives discoverability + standard transport for cross-system tool-sharing. Native `llm.Tool` gives tighter HA integration without protocol overhead. Both wrap the same backend HTTP endpoints. Use MCP when external systems need access; use native when only HA needs them.

**Why qwen2.5:14b not 32b?** 32b's tool-calling is more reliable but it needs ~17.6 GiB system memory for spillover, while llama3 is normally resident at 6 GiB. Net VRAM/RAM budget tight. 14b fits comfortably and tool-calls reliably for the 12-tool surface. Bump to 32b after VRAM upgrade or model-residency tuning.

**Why sandbox-first?** Cutover is a 5-minute window of CM5 downtime. By building parallel, drift testing happens against real mesh services without risking daily home control. Once sandbox scores 11/12 on the rubric, rsync to CM5.

_End of technical manual. Auto-built 2026-05-07T20:50:07.219357._