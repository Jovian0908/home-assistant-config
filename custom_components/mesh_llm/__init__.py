"""mesh_llm -- HA-native LLM API exposing mesh capabilities as llm.Tool subclasses.

Phase 1b of the renovation v2 (2026-05-07). Bypasses HA's MCP Client transport
(which had session-stability issues) and registers tools directly with HA's
llm registry. Conversation agents add `mesh_llm` to their llm_hass_api list to
get the 12 mesh tools alongside HA's assist tools.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from .api import MeshLLMAPI, warm_http

_LOGGER = logging.getLogger(__name__)
DOMAIN = "mesh_llm"


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up via YAML (we use config flow instead, but HA needs this stub)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Register the mesh-llm API on integration load."""
    # Pre-build httpx client off the event loop (avoids blocking-call warning)
    await warm_http()
    api = MeshLLMAPI(hass=hass, id=DOMAIN, name="Mesh AI Tools")
    unsub = llm.async_register_api(hass, api)
    entry.async_on_unload(unsub)
    _LOGGER.info("mesh_llm: registered API with id=%s", DOMAIN)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Cleanup on unload."""
    return True
