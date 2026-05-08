# Mesh-AI Flagship Demo Transcript

_Generated 2026-05-07T20:26:17.119695 via `flagship_demo_drive.py`._

Agent: `conversation.mesh_ai_final`  ·  Model: `qwen2.5:14b`  ·  API: `mesh_llm` (12 tools)

Each act issues a real HTTP POST to HA's `/api/conversation/process` with a
specific prompt designed to invoke one of the 12 mesh tools. The actual
tool was called (proven by mesh-service backend hits in mesh logs); the
agent's response below is the natural-language summary it returned.

---

## Act 1 — Scene awareness

**Expected tool**: `mesh_scene_current`
**Elapsed**: 30.8s
**Response type**: `action_done`

> **You**: Use mesh_scene_current to tell me what scene I'm in right now.

> **Mesh AI**: It seems there was an error retrieving the current scene. Let's try again shortly or check if there are any issues with your home services. For now, I can only say that the current scene is unknown.

---

## Act 2 — Aria research (async spawn)

**Expected tool**: `mesh_aria_research`
**Elapsed**: 36.7s
**Response type**: `action_done`

> **You**: Spawn an aria research project on the best AM5 motherboard for two V100 GPUs.

> **Mesh AI**: เกิดข้อผิดพลาดในการเริ่มโครงการวิจัย Aria ที่ท่านต้องการ มีปัญหาด้านเนื้อหา (Unprocessable Content). กรุณาตรวจสอบคำถามของท่านและลองใหม่อีกครั้งหรือปรึกษาข้อมูลเพิ่มเติมตามลิงค์นี้: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/422

---

## Act 3 — Knowledge search (cross-session memory)

**Expected tool**: `mesh_knowledge_search`
**Elapsed**: 43.3s
**Response type**: `action_done`

> **You**: Search my personal knowledge for anything about Hailo NPU using mesh_knowledge_search.

> **Mesh AI**: Your personal knowledge doesn't seem to contain any specific information about the Hailo NPU. The search results are mostly related to coffee products and roasters, which might not be what you were looking for. Would you like me to look elsewhere or try a different query?

---

## Act 4 — Council reasoning

**Expected tool**: `mesh_council_decide`
**Elapsed**: 130.7s
**Response type**: `action_done`

> **You**: Council, should I run the heater pre-heat tonight given that I'm home and the heater current consumption sensor is unavailable? Use mesh_council_decide depth=fast.

> **Mesh AI**: คณะกรรมแนะนำให้เปิด暖气预热，因为你在家且没有加热器当前消耗传感器的情况下，可以根据外部天气和家中舒适度来判断。由于您在家中，并且考虑到晚上的温度可能会下降，开启暖气可以帮助保持舒适的室内环境。

不过，具体的能源消耗数据缺失可能影响了精准建议的质量。如果可以获取到相关能耗信息，将有助于做出更加明智的决定。在没有这些数据的情况下，根据个人偏好和舒适度进行判断是最好的选择。

---

## Act 5 — Aria recall (cross-session memory)

**Expected tool**: `mesh_aria_recall`
**Elapsed**: 151.8s
**Response type**: `action_done`

> **You**: List my recent aria research projects using mesh_aria_recall.

> **Mesh AI**: Here are your recent Aria research projects:

- **Goal:** "third test gate"  
  Status: Killed  
  Created At: May 7, 2026, 02:14 AM  

- **Goal:** "can i add vram to a 3060 that has un populated spots explain how"  
  Status: Complete  
  Created At: April 2, 2026, 02:02 AM  

- **Goal:** "need all specs for the cm5 from raspberry pi, pcie lanes available and speed of them also how to attach several pi HATs to a cm5 using full pcie lane and not sharing"  
  Status: Killed  
  Created At: April 1, 2026, 01:30 AM  

- **Goal:** "need all specs for the cm5 from raspberry pi, pcie lanes available and speed of them also how to attach several pi HATs to a cm5 using full pcie lane and not sharing"  
  Status: Complete  
  Created At: April 1, 2026, 01:30 AM  

- **Goal:** "What are the most effective techniques for running local LLMs on consumer hardware with limited VRAM?"  
  Status: Killed  
  Created At: March 31, 2026, 10:21 PM

---

## Act 6 — Knowledge ingest (persistence)

**Expected tool**: `mesh_knowledge_ingest`
**Elapsed**: 94.7s
**Response type**: `action_done`

> **You**: Save this to my notes using mesh_knowledge_ingest: 'Phase 1c voice pipeline verified end-to-end on 2026-05-08; qwen2.5:14b routing through mesh_llm to live mesh services.'

> **Mesh AI**: Your note about the Phase 1c voice pipeline verification has been saved to your personal knowledge base. It took approximately 1.4 seconds to process and store the information.

---

## Verification path

Real-data proof per act:
1. `mesh_scene_current` -> hits `http://scene:5555/context` (live SceneEngine state)
2. `mesh_aria_research` -> POSTs `http://aria:5050/projects` (project_id returned)
3. `mesh_knowledge_search` -> POSTs `http://knowledge:5850/search` (ChromaDB top-k)
4. `mesh_council_decide` -> POSTs `http://council:8800/council/ask` (planner+reviewer chain)
5. `mesh_aria_recall` -> GETs `http://aria:5050/projects` (lists active+archived)
6. `mesh_knowledge_ingest` -> POSTs `http://knowledge:5850/ingest/conversations`

Each tool definition lives in `custom_components/mesh_llm/api.py`.
Each subclasses `homeassistant.helpers.llm.Tool` with `parameters: vol.Schema`.

## Replay

```
python C:\Users\jovia\scripts\flagship_demo_drive.py
```