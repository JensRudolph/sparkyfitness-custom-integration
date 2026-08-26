"""Config and options flows for SparkyFitness."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import SparkyFitnessMcpClient, normalize_mcp_endpoint
from .const import (
    CONF_API_KEY,
    CONF_ENABLE_CHECKIN,
    CONF_ENABLE_ENGAGEMENT,
    CONF_ENABLE_EXERCISE,
    CONF_ENABLE_GOALS,
    CONF_ENABLE_NUTRITION,
    CONF_ENABLE_TRENDS,
    CONF_UPDATE_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
)
from .exceptions import (
    SparkyFitnessAuthenticationError,
    SparkyFitnessConnectionError,
    SparkyFitnessMcpError,
    SparkyFitnessSslError,
    SparkyFitnessTimeoutError,
)

_LOGGER = logging.getLogger(__name__)


class SparkyFitnessConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a SparkyFitness config flow."""

    VERSION = 1
    options_flow_reloads = True

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Collect the endpoint and API key and verify MCP."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                endpoint = normalize_mcp_endpoint(user_input[CONF_URL])
            except ValueError:
                errors["base"] = "invalid_url"
            else:
                normalized = {
                    CONF_URL: endpoint,
                    CONF_API_KEY: user_input[CONF_API_KEY],
                    CONF_VERIFY_SSL: user_input.get(
                        CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL
                    ),
                }
                error = await self._async_validate(normalized)
                if error is None:
                    for entry in self._async_current_entries():
                        if (
                            entry.data.get(CONF_URL) == endpoint
                            and entry.data.get(CONF_API_KEY) == normalized[CONF_API_KEY]
                        ):
                            return self.async_abort(reason="already_configured")
                    host = urlsplit(endpoint).hostname or endpoint
                    return self.async_create_entry(title=host, data=normalized)
                errors["base"] = error

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_URL,
                    default=(user_input or {}).get(CONF_URL, ""),
                ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
                vol.Required(CONF_API_KEY): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(
                    CONF_VERIFY_SSL,
                    default=(user_input or {}).get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                ): BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Start reauthentication after a rejected API key."""

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Validate and store a replacement API key."""

        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, CONF_API_KEY: user_input[CONF_API_KEY]}
            if (error := await self._async_validate(data)) is None:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
        )

    async def _async_validate(self, data: dict[str, Any]) -> str | None:
        """Return a localized error key, or None when validation succeeds."""

        client = SparkyFitnessMcpClient(
            async_get_clientsession(
                self.hass, verify_ssl=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
            ),
            data[CONF_URL],
            data[CONF_API_KEY],
            verify_ssl=data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        )
        try:
            await client.async_test_connection()
        except SparkyFitnessAuthenticationError:
            return "invalid_auth"
        except SparkyFitnessSslError:
            return "ssl_error"
        except SparkyFitnessTimeoutError:
            return "timeout"
        except SparkyFitnessMcpError:
            return "invalid_mcp_server"
        except SparkyFitnessConnectionError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error while validating SparkyFitness MCP")
            return "unknown"
        finally:
            await client.async_disconnect()
        return None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SparkyFitnessOptionsFlow:
        """Return the options flow handler."""

        return SparkyFitnessOptionsFlow()


class SparkyFitnessOptionsFlow(config_entries.OptionsFlow):
    """Configure polling, TLS, and feature groups."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show all supported options in one step."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        data = self.config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=options.get(
                            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_UPDATE_INTERVAL,
                            max=MAX_UPDATE_INTERVAL,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                            unit_of_measurement="min",
                        )
                    ),
                    vol.Required(
                        CONF_VERIFY_SSL,
                        default=options.get(
                            CONF_VERIFY_SSL,
                            data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                        ),
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_ENABLE_NUTRITION,
                        default=options.get(CONF_ENABLE_NUTRITION, True),
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_ENABLE_EXERCISE,
                        default=options.get(CONF_ENABLE_EXERCISE, True),
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_ENABLE_CHECKIN,
                        default=options.get(CONF_ENABLE_CHECKIN, True),
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_ENABLE_ENGAGEMENT,
                        default=options.get(CONF_ENABLE_ENGAGEMENT, True),
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_ENABLE_GOALS,
                        default=options.get(CONF_ENABLE_GOALS, True),
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_ENABLE_TRENDS,
                        default=options.get(CONF_ENABLE_TRENDS, True),
                    ): BooleanSelector(),
                }
            ),
        )
