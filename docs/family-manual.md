# Mesh AI - Family Manual

_Auto-generated May 07, 2026._  Reprint anytime: `python ha_doc_generator.py`.

**Your home**: Home - America/Toronto
**Areas**: Living Room, Kitchen, Bedroom

---

## 1. Talking to the house

Just say what you want. The house listens through your HomePods, your phone's HA Companion app, and the wall tablets. You can also type into the HA dashboard.

**Things you can ask:**
- 'What's my current scene?'  -> tells you who/what is happening at home
- 'Search my notes for [topic]'  -> finds anything you've written down
- 'List my aria research projects'  -> recap of past research the house ran
- 'Council, should I [decision]?'  -> deep-think reasoning
- 'Save this note: [text]'  -> pins a thought to your knowledge base
- Standard requests like 'turn off the kitchen lights' work too.

**If voice doesn't respond**: press the Zigbee button by the bed to reset quiet mode (the kill switch). See section 6 for troubleshooting.

---

## 2. The basics

### Lights (0 total)

_(no lights configured yet)_

### Climate (0 thermostats)

_(no thermostats yet)_

### Media players (0)

_(no media players yet)_

### Locks (0)

_(no smart locks yet)_

---

## 3. The Mesh AI dashboard

Visit `http://192.168.0.50:8123/mesh-renovation` on any device.

**Six sections** along the bottom nav:
- **Home** - activity tier, voice activity, presence, climate
- **AI Status** - what the mesh's AI is doing right now
- **Energy** - power use + plug control
- **Cameras** - Frigate timeline + recognized arrivals
- **Floor3D** - 3D floorplan (when configured)
- **System** - health + watchdogs

Tap any tile for more info. The dashboard is mobile-friendly.

---

## 4. The Zigbee kill switch

**One press** = the mesh shuts up for 8 hours. Lights stop firing autonomously, voice greetings stop, AI loops pause. Useful when you're trying to sleep, watching a movie, or just don't want the house chatting at you.

**Double press** = cancel quiet mode immediately.

**Auto-clears** after 8 hours so the system comes back on its own.

---

## 5. Things the AI Mesh can do for you

Each capability below is a 'tool' your voice assistant can call. Just ask in plain English.

- **`mesh_council_decide`** - Use the mesh's Council deep-reasoning chain for multi-step thinking, .
- **`mesh_knowledge_search`** - Search 16,749 chunks of personal knowledge (notes, conversations, .
- **`mesh_scene_current`** - Get the current home scene narrative -- what's happening in the house .
- **`mesh_vision_describe`** - Get the latest scene description for one camera.
- **`mesh_aria_research`** - Spawn an aria research project for a question that needs deep web .
- **`mesh_aria_recall`** - List recent aria research projects, optionally filtered by topic substring.
- **`mesh_knowledge_ingest`** - Save a text snippet (note, summary, observation) to personal knowledge .
- **`mesh_sentiment_analyze`** - Classify sentiment of a text (positive/neutral/negative + emotion tags).
- **`mesh_routine_predict`** - Predict the user's likely current/upcoming routine based on time, .
- **`mesh_memory_recall`** - Search episodic memory (events, conversations, observations) for matches.
- **`mesh_vision_list_recent`** - Get most-recent retained scene/detected payloads for one or all cameras.
- **`mesh_genesis_spawn`** - [DANGEROUS] Auto-code a new mesh capability.

---

## 6. Common troubleshooting

| Problem | Try this first |
|---|---|
| Voice doesn't respond | Press Zigbee kill-switch button twice (cancels quiet mode) |
| Light won't turn on/off | Check the dashboard: is the device 'unavailable'? Power-cycle it. |
| Camera not showing | Frigate is running on the CM5; check its addon log via HA UI. |
| 'Mesh AI doesn't know X' | Try rephrasing - the AI uses tools like 'search my notes' or 'use council'. |
| Whole house seems offline | Check Wi-Fi first; then the CM5 (lit on the side); then your laptop running the mesh. |
| Wall tablet won't load | Hard-refresh the page (long-press refresh in the HA app). |
| 'I want to silence the AI for a while' | Hold the Zigbee button - quiet mode for 8 hours. |
| Nothing helps | Open `https://192.168.0.50:8123/repairs` - HA self-diagnoses most issues. |

---

_Document built from live HA state. 80 entities tracked, 12 mesh AI tools available._