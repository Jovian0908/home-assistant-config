"""Mesh LLM API -- registers 12 mesh capabilities as llm.Tool subclasses.

Each tool wraps an HTTP call to a mesh service running on the Docker network.
Tools are exposed to HA's Conversation Agent (when llm_hass_api includes "mesh_llm").
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

_LOGGER = logging.getLogger(__name__)

# ---- Mesh service URLs (Docker network) ----------------------------------
# When sandbox HA runs in mesh-ha-sandbox container, hostnames resolve via
# Docker DNS. For deployment to CM5 HAOS, point at LAN IPs (192.168.0.94:<port>).
COUNCIL_URL    = "http://council:8800"
ARIA_URL       = "http://aria:5050"
KNOWLEDGE_URL  = "http://knowledge:5850"
VISION_URL     = "http://vision:6600"
SCENE_URL      = "http://scene:5555"
SENTIMENT_URL  = "http://sentiment:5800"
ROUTINE_URL    = "http://routine:5500"
MEMORY_URL     = "http://memory:5950"
GENESIS_URL    = "http://genesis:6400"

# Mesh token for service-to-service auth (loaded from HA secrets if available)
import os
MESH_TOKEN = os.environ.get("MESH_TOKEN", "")
HEADERS = {"X-Mesh-Token": MESH_TOKEN, "Content-Type": "application/json"}


# ---- Persistent HTTP client (avoids per-call TLS setup) ------------------
# Pre-warmed at integration setup (see __init__.py async_setup_entry) to avoid
# httpx.AsyncClient() doing blocking SSL cert load inside the event loop.
_client: httpx.AsyncClient | None = None


async def warm_http() -> None:
    """Called from __init__.async_setup_entry to pre-build the client off-loop."""
    global _client
    if _client is None:
        import asyncio
        loop = asyncio.get_running_loop()
        _client = await loop.run_in_executor(
            None,
            lambda: httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0))
        )


def _http() -> httpx.AsyncClient:
    """Sync accessor; warm_http() must have run during integration setup."""
    if _client is None:
        # Late path: build sync (will trigger blocking warning but won't crash)
        return httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0))
    return _client


# ---- Tool implementations ------------------------------------------------

class MeshCouncilDecide(llm.Tool):
    """Multi-step reasoning via the Council planner -> reviewer -> manager chain."""
    name = "mesh_council_decide"
    description = (
        "Use the mesh's Council deep-reasoning chain for multi-step thinking, "
        "tradeoff analysis, or review of a recommendation. Local LLMs only "
        "(qwen2.5:32b planner + 7B/14B reviewers). Latency 30-300s. Best for "
        "questions like 'should I do X given Y' or 'compare these options'."
    )
    parameters = vol.Schema({
        vol.Required("query", description="The user's question (full natural language)."): str,
        vol.Optional("depth", default="normal",
            description="fast = single planner only; normal = full chain; deep = debate triplet."): vol.In(["fast", "normal", "deep"]),
    })

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput,
                         llm_context: llm.LLMContext) -> dict[str, Any]:
        try:
            r = await _http().post(f"{COUNCIL_URL}/council/ask",
                json={"query": tool_input.tool_args["query"],
                      "depth": tool_input.tool_args.get("depth", "normal")},
                headers=HEADERS)
            r.raise_for_status()
            data = r.json()
            return {"final_answer": data.get("final_answer", ""),
                    "iterations": data.get("iterations", 0),
                    "elapsed_ms": data.get("elapsed_ms", 0)}
        except Exception as e:
            _LOGGER.warning("mesh_council_decide failed: %s", e)
            return {"error": str(e), "final_answer": ""}


class MeshKnowledgeSearch(llm.Tool):
    """Search the mesh's personal-knowledge ChromaDB index."""
    name = "mesh_knowledge_search"
    description = (
        "Search 16,749 chunks of personal knowledge (notes, conversations, "
        "documents) by semantic similarity. Returns top-k matching excerpts. "
        "Use for 'what did I write about X' or 'find my notes on Y'. Latency <500ms."
    )
    parameters = vol.Schema({
        vol.Required("query", description="Search text (natural language)."): str,
        vol.Optional("k", default=5, description="Number of results (1-20)."): vol.All(int, vol.Range(min=1, max=20)),
    })

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput,
                         llm_context: llm.LLMContext) -> dict[str, Any]:
        try:
            r = await _http().post(f"{KNOWLEDGE_URL}/search",
                json={"query": tool_input.tool_args["query"],
                      "n_results": tool_input.tool_args.get("k", 5)},
                headers=HEADERS)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            _LOGGER.warning("mesh_knowledge_search failed: %s", e)
            return {"error": str(e), "results": []}


class MeshSceneCurrent(llm.Tool):
    """Current home scene narrative + presence + recent activity."""
    name = "mesh_scene_current"
    description = (
        "Get the current home scene narrative -- what's happening in the house "
        "right now. Returns llava-generated text + presence + recent activity. "
        "Use for 'what scene am I in' or 'what's happening'. Latency <100ms."
    )
    parameters = vol.Schema({})

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput,
                         llm_context: llm.LLMContext) -> dict[str, Any]:
        try:
            r = await _http().get(f"{SCENE_URL}/context", headers=HEADERS)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            _LOGGER.warning("mesh_scene_current failed: %s", e)
            return {"error": str(e), "scene": "unknown"}


class MeshVisionDescribe(llm.Tool):
    """Latest llava scene description for a specific camera."""
    name = "mesh_vision_describe"
    description = (
        "Get the latest scene description for one camera. Available: "
        "aqara_g3 (hallway), tapo_c260 (living room), g410_front (front door). "
        "Returns scene text + detected objects + flags. Latency <100ms."
    )
    parameters = vol.Schema({
        vol.Required("camera", description="Camera ID."): vol.In(["aqara_g3", "tapo_c260", "g410_front"]),
    })

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput,
                         llm_context: llm.LLMContext) -> dict[str, Any]:
        try:
            cam = tool_input.tool_args["camera"]
            r = await _http().get(f"{VISION_URL}/snapshot/{cam}", headers=HEADERS)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            _LOGGER.warning("mesh_vision_describe failed: %s", e)
            return {"error": str(e)}


class MeshAriaResearch(llm.Tool):
    """Spawn an aria research project (async, returns task_id immediately)."""
    name = "mesh_aria_research"
    description = (
        "Spawn an aria research project for a question that needs deep web "
        "+ local-knowledge research. Returns task_id IMMEDIATELY -- aria runs "
        "for minutes async. Result will be announced via TTS on completion. "
        "Use for open research questions like 'find me the best X for Y'."
    )
    parameters = vol.Schema({
        vol.Required("question", description="Research question."): str,
        vol.Optional("budget_tokens", default=100000): int,
        vol.Optional("budget_api_calls", default=50): int,
        vol.Optional("budget_wall_seconds", default=300): int,
    })

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput,
                         llm_context: llm.LLMContext) -> dict[str, Any]:
        args = tool_input.tool_args
        try:
            r = await _http().post(f"{ARIA_URL}/projects",
                json={"question": args["question"],
                      "budget_tokens": args.get("budget_tokens", 100000),
                      "budget_api_calls": args.get("budget_api_calls", 50),
                      "budget_wall_seconds": args.get("budget_wall_seconds", 300)},
                headers=HEADERS)
            r.raise_for_status()
            data = r.json()
            return {"status": "started", "task_id": data.get("project_id"),
                    "goal": data.get("goal"),
                    "msg": "aria running async; result announced on completion"}
        except Exception as e:
            _LOGGER.warning("mesh_aria_research failed: %s", e)
            return {"error": str(e)}


class MeshAriaRecall(llm.Tool):
    """List recent aria research projects (filtered by topic)."""
    name = "mesh_aria_recall"
    description = (
        "List recent aria research projects, optionally filtered by topic substring. "
        "Returns project goals + statuses + findings preview. Use to answer "
        "'what have I researched about X' before starting a new project."
    )
    parameters = vol.Schema({
        vol.Optional("topic", default="", description="Substring filter on goal."): str,
        vol.Optional("n", default=5): int,
    })

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput,
                         llm_context: llm.LLMContext) -> dict[str, Any]:
        try:
            r = await _http().get(f"{ARIA_URL}/projects", headers=HEADERS)
            r.raise_for_status()
            data = r.json()
            all_p = (data.get("projects") or []) + (data.get("archived") or [])
            topic = tool_input.tool_args.get("topic", "").lower()
            if topic:
                all_p = [p for p in all_p if topic in str(p.get("goal", "")).lower()]
            n = tool_input.tool_args.get("n", 5)
            return {"projects": all_p[:n], "total_matched": len(all_p)}
        except Exception as e:
            _LOGGER.warning("mesh_aria_recall failed: %s", e)
            return {"error": str(e), "projects": []}


class MeshKnowledgeIngest(llm.Tool):
    """Save text to personal knowledge ChromaDB."""
    name = "mesh_knowledge_ingest"
    description = (
        "Save a text snippet (note, summary, observation) to personal knowledge "
        "for later semantic recall. Use when user says 'remember this' or 'save to my notes'."
    )
    parameters = vol.Schema({
        vol.Required("text", description="Content to save."): str,
        vol.Optional("source", default="mesh_llm_user_save"): str,
    })

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput,
                         llm_context: llm.LLMContext) -> dict[str, Any]:
        try:
            payload = {"conversations": [{
                "role": "user",
                "content": tool_input.tool_args["text"],
                "source": tool_input.tool_args.get("source", "mesh_llm_user_save"),
                "ts": time.time(),
            }]}
            r = await _http().post(f"{KNOWLEDGE_URL}/ingest/conversations",
                                   json=payload, headers=HEADERS)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            _LOGGER.warning("mesh_knowledge_ingest failed: %s", e)
            return {"error": str(e)}


class MeshSentimentAnalyze(llm.Tool):
    """Sentiment / mood classification."""
    name = "mesh_sentiment_analyze"
    description = (
        "Classify sentiment of a text (positive/neutral/negative + emotion tags). "
        "Use for tone-aware responses or 'how does this read?' questions."
    )
    parameters = vol.Schema({
        vol.Required("text"): str,
    })

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput,
                         llm_context: llm.LLMContext) -> dict[str, Any]:
        try:
            r = await _http().post(f"{SENTIMENT_URL}/analyze",
                                   json={"text": tool_input.tool_args["text"]},
                                   headers=HEADERS)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            _LOGGER.warning("mesh_sentiment_analyze failed: %s", e)
            return {"error": str(e)}


class MeshRoutinePredict(llm.Tool):
    """Predict current/upcoming routine from learned patterns."""
    name = "mesh_routine_predict"
    description = (
        "Predict the user's likely current/upcoming routine based on time, "
        "presence, and learned daily patterns. Returns predictions with confidence."
    )
    parameters = vol.Schema({})

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput,
                         llm_context: llm.LLMContext) -> dict[str, Any]:
        try:
            r = await _http().get(f"{ROUTINE_URL}/predict", headers=HEADERS)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            _LOGGER.warning("mesh_routine_predict failed: %s", e)
            return {"error": str(e)}


class MeshMemoryRecall(llm.Tool):
    """Episodic-memory search."""
    name = "mesh_memory_recall"
    description = (
        "Search episodic memory (events, conversations, observations) for matches. "
        "Use for 'remember when X' or 'what happened around Y' questions."
    )
    parameters = vol.Schema({
        vol.Required("query"): str,
        vol.Optional("n", default=5): int,
    })

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput,
                         llm_context: llm.LLMContext) -> dict[str, Any]:
        try:
            r = await _http().get(f"{MEMORY_URL}/memory/search",
                                  params={"q": tool_input.tool_args["query"],
                                          "n": tool_input.tool_args.get("n", 5)},
                                  headers=HEADERS)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            _LOGGER.warning("mesh_memory_recall failed: %s", e)
            return {"error": str(e)}


class MeshVisionListRecent(llm.Tool):
    """Recent vision events across cameras."""
    name = "mesh_vision_list_recent"
    description = (
        "Get most-recent retained scene/detected payloads for one or all cameras. "
        "Use for quick 'what was just at the door' questions."
    )
    parameters = vol.Schema({
        vol.Optional("camera", description="Filter to one camera or omit for all."): vol.In(["aqara_g3", "tapo_c260", "g410_front"]),
    })

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput,
                         llm_context: llm.LLMContext) -> dict[str, Any]:
        cams = [tool_input.tool_args["camera"]] if "camera" in tool_input.tool_args else ["aqara_g3", "tapo_c260", "g410_front"]
        out = {}
        for cam in cams:
            try:
                r = await _http().get(f"{VISION_URL}/snapshot/{cam}", headers=HEADERS)
                r.raise_for_status()
                out[cam] = r.json()
            except Exception as e:
                out[cam] = {"error": str(e)}
        return {"cameras": out}


class MeshGenesisSpawn(llm.Tool):
    """[DANGEROUS] Auto-code a new mesh capability via Genesis."""
    name = "mesh_genesis_spawn"
    description = (
        "[DANGEROUS] Auto-code a new mesh capability. Genesis runs aria research, "
        "generates code, gates review, sandbox-tests. confirm_dangerous=true REQUIRED "
        "to actually spawn -- otherwise dry-run preview only."
    )
    parameters = vol.Schema({
        vol.Required("capability_spec"): str,
        vol.Optional("confirm_dangerous", default=False): bool,
    })

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput,
                         llm_context: llm.LLMContext) -> dict[str, Any]:
        args = tool_input.tool_args
        if not args.get("confirm_dangerous", False):
            return {"status": "dry_run",
                    "would_create": args["capability_spec"],
                    "msg": "Set confirm_dangerous=true to actually spawn."}
        try:
            r = await _http().post(f"{GENESIS_URL}/genesis/propose",
                                   json={"capability_spec": args["capability_spec"]},
                                   headers=HEADERS)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            _LOGGER.warning("mesh_genesis_spawn failed: %s", e)
            return {"error": str(e)}


# ---- Tool registry + API class -------------------------------------------

_TOOL_CLASSES = [
    MeshCouncilDecide,
    MeshKnowledgeSearch,
    MeshSceneCurrent,
    MeshVisionDescribe,
    MeshAriaResearch,
    MeshAriaRecall,
    MeshKnowledgeIngest,
    MeshSentimentAnalyze,
    MeshRoutinePredict,
    MeshMemoryRecall,
    MeshVisionListRecent,
    MeshGenesisSpawn,
]


@dataclass(kw_only=True, slots=True)
class MeshLLMAPI(llm.API):
    """Mesh-LLM API: returns the 12 mesh tools to whichever conversation
    agent has `mesh_llm` in its llm_hass_api list."""

    async def async_get_api_instance(self, llm_context: llm.LLMContext) -> llm.APIInstance:
        api_prompt = (
            "You have access to 12 Mesh AI tools that wrap a local-LLM home-AI mesh. "
            "Use them aggressively when the user asks for reasoning, scenes, knowledge, "
            "vision, sentiment, routines, memory, or research. Tools are local-only "
            "(no cloud) and return real data from the user's home services. Prefer "
            "tool calls over speculation -- the tools are the authoritative source."
        )
        tools = [cls() for cls in _TOOL_CLASSES]
        return llm.APIInstance(api=self, api_prompt=api_prompt, llm_context=llm_context, tools=tools)
