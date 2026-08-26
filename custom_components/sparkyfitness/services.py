"""Home Assistant actions backed by explicit SparkyFitness MCP calls."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CONFIG_ENTRY_ID,
    DOMAIN,
    MEAL_TYPES,
    SERVICE_CREATE_EXERCISE,
    SERVICE_CREATE_WORKOUT_PRESET,
    SERVICE_DELETE_EXERCISE_ENTRY,
    SERVICE_DELETE_FOOD_ENTRY,
    SERVICE_LOG_BIOMETRICS,
    SERVICE_LOG_CUSTOM_METRIC,
    SERVICE_LOG_EXERCISE,
    SERVICE_LOG_FASTING_WINDOW,
    SERVICE_LOG_FOOD,
    SERVICE_LOG_HABIT,
    SERVICE_LOG_MOOD,
    SERVICE_LOG_SLEEP,
    SERVICE_LOG_WATER,
    SERVICE_LOG_WEIGHT,
    SERVICE_LOG_WORKOUT_PRESET,
    SERVICE_REFRESH,
    SERVICE_SET_GOALS,
    SERVICE_START_FASTING,
    SERVICE_UPDATE_EXERCISE_ENTRY,
    SERVICE_UPDATE_FOOD_ENTRY,
    SET_TYPES,
)
from .exceptions import (
    SparkyFitnessAuthenticationError,
    SparkyFitnessError,
    SparkyFitnessUnsupportedFeatureError,
)

ENTRY_FIELD = {vol.Optional(CONF_CONFIG_ENTRY_ID): cv.string}
DATE_FIELD = {vol.Optional("entry_date"): cv.date}
UUID_VALUE = vol.All(
    cv.string,
    vol.Match(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    ),
)

LOG_WEIGHT_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        **DATE_FIELD,
        vol.Required("weight"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("unit", default="kg"): vol.In(("kg", "lbs")),
    }
)
LOG_BIOMETRICS_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        **DATE_FIELD,
        vol.Optional("weight"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("weight_unit", default="kg"): vol.In(("kg", "lbs")),
        vol.Optional("steps"): cv.positive_int,
        vol.Optional("height"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("height_unit", default="cm"): vol.In(("cm", "in", "ft")),
        vol.Optional("neck"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("waist"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("hips"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("measurements_unit", default="cm"): vol.In(("cm", "in")),
        vol.Optional("body_fat"): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
        vol.Optional("muscle_mass"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("bone_mass"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("body_water"): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=100)
        ),
    }
)
LOG_WATER_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        **DATE_FIELD,
        vol.Required("amount"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("unit", default="ml"): vol.In(("ml", "l", "fl_oz")),
    }
)
LOG_MOOD_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        **DATE_FIELD,
        vol.Required("mood"): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
        vol.Optional("notes"): cv.string,
        vol.Optional("mood_tags"): vol.All(cv.ensure_list, [cv.string]),
    }
)
LOG_SLEEP_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        **DATE_FIELD,
        vol.Optional("duration_minutes"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("bedtime"): cv.string,
        vol.Optional("wake_time"): cv.string,
        vol.Optional("source"): cv.string,
    }
)
LOG_CUSTOM_METRIC_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        **DATE_FIELD,
        vol.Required("name"): cv.string,
        vol.Required("value"): vol.Any(vol.Coerce(float), cv.string),
        vol.Optional("unit"): cv.string,
        vol.Optional("notes"): cv.string,
    }
)
LOG_FOOD_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        **DATE_FIELD,
        vol.Required("food"): cv.string,
        vol.Required("quantity"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("unit"): cv.string,
        vol.Optional("meal_type", default="snacks"): vol.In(MEAL_TYPES),
        vol.Optional("meal_type_id"): cv.string,
    }
)
UPDATE_FOOD_ENTRY_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        vol.Required("entry_id"): UUID_VALUE,
        vol.Optional("entry_type", default="food_entry"): vol.In(
            ("food_entry", "food_entry_meal")
        ),
        vol.Optional("quantity"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("unit"): cv.string,
        vol.Optional("meal_type"): vol.In(MEAL_TYPES),
        vol.Optional("meal_type_id"): UUID_VALUE,
    }
)
DELETE_FOOD_ENTRY_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        vol.Required("entry_id"): UUID_VALUE,
        vol.Optional("entry_type", default="food_entry"): vol.In(
            ("food_entry", "food_entry_meal")
        ),
        vol.Required("confirm"): vol.Equal(True),
    }
)
EXERCISE_SET_SCHEMA = vol.Schema(
    {
        vol.Optional("reps"): cv.positive_int,
        vol.Optional("weight"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("duration"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("distance"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("rest_time"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("set_type", default="Working Set"): vol.In(SET_TYPES),
        vol.Optional("rpe"): vol.All(vol.Coerce(float), vol.Range(min=0, max=10)),
        vol.Optional("notes"): cv.string,
    }
)
LOG_EXERCISE_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        **DATE_FIELD,
        vol.Required("exercise"): cv.string,
        vol.Optional("entry_time"): cv.string,
        vol.Optional("notes"): cv.string,
        vol.Optional("duration_minutes"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("calories_burned"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("distance"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("avg_heart_rate"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=300)
        ),
        vol.Optional("steps"): cv.positive_int,
        vol.Optional("sets"): vol.All(cv.ensure_list, [EXERCISE_SET_SCHEMA]),
    }
)
UPDATE_EXERCISE_ENTRY_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        **DATE_FIELD,
        vol.Required("entry_id"): UUID_VALUE,
        vol.Optional("entry_time"): cv.string,
        vol.Optional("notes"): cv.string,
        vol.Optional("duration_minutes"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("calories_burned"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("distance"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("avg_heart_rate"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=300)
        ),
        vol.Optional("steps"): cv.positive_int,
        vol.Optional("sets"): vol.All(cv.ensure_list, [EXERCISE_SET_SCHEMA]),
    }
)
DELETE_EXERCISE_ENTRY_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        vol.Required("entry_id"): UUID_VALUE,
        vol.Required("confirm"): vol.Equal(True),
    }
)
CREATE_EXERCISE_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        vol.Required("name"): cv.string,
        vol.Optional("category"): cv.string,
        vol.Optional("description"): cv.string,
        vol.Optional("calories_per_hour"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("modality"): vol.In(
            ("weight_reps", "reps_only", "duration", "duration_distance")
        ),
    }
)
CREATE_WORKOUT_PRESET_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        vol.Required("name"): cv.string,
        vol.Required("exercises"): vol.All(cv.ensure_list, [cv.string]),
    }
)
LOG_WORKOUT_PRESET_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        **DATE_FIELD,
        vol.Exclusive("preset_id", "preset"): cv.string,
        vol.Exclusive("preset_name", "preset"): cv.string,
    }
)
SET_GOALS_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        vol.Optional("start_date"): cv.date,
        vol.Optional("calories"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("protein"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("carbs"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("fat"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("water_goal_ml"): vol.All(vol.Coerce(float), vol.Range(min=0)),
        vol.Optional("weight"): vol.All(vol.Coerce(float), vol.Range(min=0)),
    }
)
LOG_HABIT_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        **DATE_FIELD,
        vol.Required("habit_id"): cv.string,
        vol.Required("completed"): cv.boolean,
    }
)
START_FASTING_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        vol.Optional("start_time"): cv.datetime,
        vol.Optional("fasting_type"): cv.string,
    }
)
LOG_FASTING_WINDOW_SCHEMA = vol.Schema(
    {
        **ENTRY_FIELD,
        vol.Required("start_time"): cv.datetime,
        vol.Required("end_time"): cv.datetime,
        vol.Optional("fasting_status", default="COMPLETED"): vol.In(
            ("COMPLETED", "CANCELLED")
        ),
        vol.Optional("fasting_type"): cv.string,
    }
)


def async_register_services(hass: HomeAssistant) -> None:
    """Register explicit, typed actions once for all config entries."""

    if hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        return

    async def handle(call: ServiceCall) -> dict[str, Any]:
        entry = _resolve_entry(hass, call.data.get(CONF_CONFIG_ENTRY_ID))
        runtime = entry.runtime_data
        client = runtime.client
        service = call.service
        data = dict(call.data)
        data.pop(CONF_CONFIG_ENTRY_ID, None)

        try:
            if service == SERVICE_REFRESH:
                runtime.coordinator.invalidate_sections("goals", "trends")
                await runtime.coordinator.async_request_refresh()
                return {"result": "refreshed"}

            entry_date_value = data.pop("entry_date", None)
            entry_date = _date_string(entry_date_value)
            if service == SERVICE_LOG_WEIGHT:
                result = await client.async_log_weight(
                    data["weight"], data.get("unit", "kg"), entry_date
                )
            elif service == SERVICE_LOG_BIOMETRICS:
                if not any(
                    key in data
                    for key in (
                        "weight",
                        "steps",
                        "height",
                        "neck",
                        "waist",
                        "hips",
                        "body_fat",
                        "muscle_mass",
                        "bone_mass",
                        "body_water",
                    )
                ):
                    raise ServiceValidationError(
                        "At least one biometric measurement is required"
                    )
                result = await client.async_log_biometrics(
                    entry_date=entry_date, **data
                )
            elif service == SERVICE_LOG_WATER:
                amount_ml = _water_to_ml(data["amount"], data.get("unit", "ml"))
                result = await client.async_log_water(amount_ml, entry_date)
            elif service == SERVICE_LOG_MOOD:
                result = await client.async_log_mood(
                    data["mood"],
                    entry_date,
                    notes=data.get("notes"),
                    mood_tags=data.get("mood_tags"),
                )
            elif service == SERVICE_LOG_SLEEP:
                if not any(
                    key in data for key in ("duration_minutes", "bedtime", "wake_time")
                ):
                    raise ServiceValidationError(
                        "Provide duration_minutes, bedtime, or wake_time"
                    )
                duration = data.get("duration_minutes")
                result = await client.async_log_sleep(
                    entry_date,
                    duration_seconds=round(duration * 60)
                    if duration is not None
                    else None,
                    bedtime=data.get("bedtime"),
                    wake_time=data.get("wake_time"),
                    source=data.get("source"),
                )
            elif service == SERVICE_LOG_CUSTOM_METRIC:
                result = await client.async_log_custom_metric(
                    data["name"],
                    data["value"],
                    entry_date,
                    unit=data.get("unit"),
                    notes=data.get("notes"),
                )
            elif service == SERVICE_LOG_FOOD:
                arguments = {
                    "food_name": data["food"],
                    "quantity": data["quantity"],
                    "meal_type": data.get("meal_type", "snacks"),
                    "entry_date": entry_date,
                }
                if data.get("unit"):
                    arguments["unit"] = data["unit"]
                if data.get("meal_type_id"):
                    arguments["meal_type_id"] = data["meal_type_id"]
                result = await client.async_log_food(**arguments)
            elif service == SERVICE_UPDATE_FOOD_ENTRY:
                entry_id = data.pop("entry_id")
                if not any(
                    key in data
                    for key in ("quantity", "unit", "meal_type", "meal_type_id")
                ):
                    raise ServiceValidationError(
                        "Provide quantity, unit, meal_type, or meal_type_id"
                    )
                result = await client.async_update_food_entry(entry_id, **data)
            elif service == SERVICE_DELETE_FOOD_ENTRY:
                entry_id = data.pop("entry_id")
                data.pop("confirm")
                result = await client.async_delete_food_entry(
                    entry_id, data["entry_type"]
                )
            elif service == SERVICE_LOG_EXERCISE:
                exercise = data.pop("exercise")
                result = await client.async_log_exercise(
                    exercise_name=exercise, entry_date=entry_date, **data
                )
            elif service == SERVICE_UPDATE_EXERCISE_ENTRY:
                entry_id = data.pop("entry_id")
                if entry_date_value is not None:
                    data["entry_date"] = entry_date
                if not data:
                    raise ServiceValidationError(
                        "At least one exercise entry field is required"
                    )
                result = await client.async_update_exercise_entry(entry_id, **data)
            elif service == SERVICE_DELETE_EXERCISE_ENTRY:
                entry_id = data.pop("entry_id")
                data.pop("confirm")
                result = await client.async_delete_exercise_entry(entry_id)
            elif service == SERVICE_CREATE_EXERCISE:
                result = await client.async_create_exercise(**data)
            elif service == SERVICE_CREATE_WORKOUT_PRESET:
                result = await client.async_create_workout_preset(
                    data["name"], data["exercises"]
                )
            elif service == SERVICE_LOG_WORKOUT_PRESET:
                if not data.get("preset_id") and not data.get("preset_name"):
                    raise ServiceValidationError("Provide preset_id or preset_name")
                result = await client.async_log_workout_preset(
                    entry_date=entry_date, **data
                )
            elif service == SERVICE_SET_GOALS:
                start_date = _date_string(data.pop("start_date", None))
                if not data:
                    raise ServiceValidationError("At least one goal value is required")
                result = await client.async_set_goals(start_date=start_date, **data)
            elif service == SERVICE_LOG_HABIT:
                result = await client.async_log_habit(
                    data["habit_id"], entry_date, data["completed"]
                )
            elif service == SERVICE_START_FASTING:
                result = await client.async_log_fasting(
                    _timestamp_string(data.get("start_time")),
                    fasting_status="ACTIVE",
                    fasting_type=data.get("fasting_type"),
                )
            elif service == SERVICE_LOG_FASTING_WINDOW:
                start_time = data["start_time"]
                end_time = data["end_time"]
                if dt_util.as_utc(_as_aware(end_time)) <= dt_util.as_utc(
                    _as_aware(start_time)
                ):
                    raise ServiceValidationError("end_time must be after start_time")
                result = await client.async_log_fasting(
                    _timestamp_string(start_time),
                    end_time=_timestamp_string(end_time),
                    fasting_status=data["fasting_status"],
                    fasting_type=data.get("fasting_type"),
                )
            else:
                raise ServiceValidationError(f"Unknown SparkyFitness action: {service}")

            if service == SERVICE_SET_GOALS:
                runtime.coordinator.invalidate_sections("goals")
            elif service in {
                SERVICE_LOG_WEIGHT,
                SERVICE_LOG_BIOMETRICS,
                SERVICE_LOG_MOOD,
                SERVICE_LOG_SLEEP,
                SERVICE_LOG_FOOD,
                SERVICE_UPDATE_FOOD_ENTRY,
                SERVICE_DELETE_FOOD_ENTRY,
                SERVICE_LOG_EXERCISE,
                SERVICE_UPDATE_EXERCISE_ENTRY,
                SERVICE_DELETE_EXERCISE_ENTRY,
            }:
                runtime.coordinator.invalidate_sections("trends")
            await runtime.coordinator.async_request_refresh()
            return {"result": result}
        except SparkyFitnessAuthenticationError as err:
            entry.async_start_reauth(hass)
            raise HomeAssistantError("SparkyFitness authentication failed") from err
        except SparkyFitnessUnsupportedFeatureError as err:
            raise ServiceValidationError(str(err)) from err
        except SparkyFitnessError as err:
            raise HomeAssistantError(str(err)) from err

    registrations = {
        SERVICE_REFRESH: vol.Schema(ENTRY_FIELD),
        SERVICE_LOG_WEIGHT: LOG_WEIGHT_SCHEMA,
        SERVICE_LOG_BIOMETRICS: LOG_BIOMETRICS_SCHEMA,
        SERVICE_LOG_WATER: LOG_WATER_SCHEMA,
        SERVICE_LOG_MOOD: LOG_MOOD_SCHEMA,
        SERVICE_LOG_SLEEP: LOG_SLEEP_SCHEMA,
        SERVICE_LOG_CUSTOM_METRIC: LOG_CUSTOM_METRIC_SCHEMA,
        SERVICE_LOG_FOOD: LOG_FOOD_SCHEMA,
        SERVICE_UPDATE_FOOD_ENTRY: UPDATE_FOOD_ENTRY_SCHEMA,
        SERVICE_DELETE_FOOD_ENTRY: DELETE_FOOD_ENTRY_SCHEMA,
        SERVICE_LOG_EXERCISE: LOG_EXERCISE_SCHEMA,
        SERVICE_UPDATE_EXERCISE_ENTRY: UPDATE_EXERCISE_ENTRY_SCHEMA,
        SERVICE_DELETE_EXERCISE_ENTRY: DELETE_EXERCISE_ENTRY_SCHEMA,
        SERVICE_CREATE_EXERCISE: CREATE_EXERCISE_SCHEMA,
        SERVICE_CREATE_WORKOUT_PRESET: CREATE_WORKOUT_PRESET_SCHEMA,
        SERVICE_LOG_WORKOUT_PRESET: LOG_WORKOUT_PRESET_SCHEMA,
        SERVICE_SET_GOALS: SET_GOALS_SCHEMA,
        SERVICE_LOG_HABIT: LOG_HABIT_SCHEMA,
        SERVICE_START_FASTING: START_FASTING_SCHEMA,
        SERVICE_LOG_FASTING_WINDOW: LOG_FASTING_WINDOW_SCHEMA,
    }
    for service, schema in registrations.items():
        hass.services.async_register(
            DOMAIN,
            service,
            handle,
            schema=schema,
            supports_response=SupportsResponse.OPTIONAL,
        )


def _resolve_entry(hass: HomeAssistant, entry_id: str | None):
    """Resolve a loaded config entry, requiring a target when ambiguous."""

    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if entry_id:
        for entry in entries:
            if entry.entry_id == entry_id:
                return entry
        raise ServiceValidationError(
            f'SparkyFitness config entry "{entry_id}" is not loaded'
        )
    if not entries:
        raise ServiceValidationError("No loaded SparkyFitness config entry exists")
    if len(entries) > 1:
        raise ServiceValidationError(
            "Multiple SparkyFitness entries exist; provide config_entry_id"
        )
    return entries[0]


def _date_string(value: date | str | None) -> str:
    """Render a service date, defaulting to Home Assistant's local date."""

    if value is None:
        return dt_util.now().date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _water_to_ml(amount: float, unit: str) -> float:
    """Convert supported Home Assistant action units to MCP milliliters."""

    if unit == "l":
        amount *= 1000
    elif unit == "fl_oz":
        amount *= 29.5735295625
    return round(amount, 2)


def _timestamp_string(value: datetime | None) -> str:
    """Render an action timestamp, defaulting to Home Assistant's current time."""

    return _as_aware(value or dt_util.now()).isoformat()


def _as_aware(value: datetime) -> datetime:
    """Interpret selector timestamps without offsets in Home Assistant's time zone."""

    if value.tzinfo is None:
        return value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return value
