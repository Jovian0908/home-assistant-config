"""Minimal config flow for mesh_llm -- single 'add' step, no settings."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from . import DOMAIN


class MeshLLMConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for mesh_llm."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step. No options -- just confirm."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Mesh LLM Tools", data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
            description_placeholders={
                "info": "This adds mesh-llm tools (council, knowledge, scene, vision, sentiment, routine, memory, aria, genesis) to HA's LLM API registry. Conversation agents can include `mesh_llm` in llm_hass_api to use these tools.",
            },
        )
