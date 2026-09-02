"""Read-only FSW front-end settings captured before acquisition.

The acquisition product must preserve the operator's FSW setup. These helpers
therefore query preamp and RF attenuation only; they never write either value.
A snapshot is cached on the adapter instance so a long Batch reusing one VISA
session performs the queries once before its first logical sample instead of on
every sample.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


_CACHE_ATTRIBUTE = "_capture_frontend_snapshot"


def read_fsw_frontend_snapshot(adapter: Any) -> dict[str, object]:
    """Return one frozen preamp/attenuation snapshot for an FSW adapter session."""

    cached = getattr(adapter, _CACHE_ATTRIBUTE, None)
    if isinstance(cached, dict):
        return deepcopy(cached)

    driver = getattr(adapter, "_driver", None)
    if driver is None:
        raise AttributeError("FSW adapter does not expose its guarded driver")

    # Prefer the reusable instrument-automation-platform driver API. Raw SCPI is
    # retained only as a compatibility fallback for older local baseline copies.
    if _supports(driver, "get_preamp_enabled"):
        preamp_enabled = bool(driver.get_preamp_enabled())
    else:
        preamp_enabled = _query_bool(driver, "INPut:GAIN:STATe?")

    if preamp_enabled:
        if _supports(driver, "get_preamp_gain_db"):
            preamp_gain_db = int(driver.get_preamp_gain_db())
        else:
            preamp_gain_db = int(round(_query_float(driver, "INPut:GAIN:VALue?")))
    else:
        preamp_gain_db = 0

    if _supports(driver, "get_rf_attenuation_auto"):
        attenuation_auto = bool(driver.get_rf_attenuation_auto())
    else:
        attenuation_auto = _query_bool(driver, "INPut:ATTenuation:AUTO?")

    if _supports(driver, "get_rf_attenuation_db"):
        attenuation_db = float(driver.get_rf_attenuation_db())
    else:
        attenuation_db = _query_float(driver, "INPut:ATTenuation?")

    snapshot: dict[str, object] = {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "preamp_enabled": preamp_enabled,
        "preamp_db": preamp_gain_db,
        "rf_attenuation_auto": attenuation_auto,
        "rf_attenuation_db": attenuation_db,
        "commands": {
            "preamp_state": "INPut:GAIN:STATe?",
            "preamp_gain": "INPut:GAIN:VALue?" if preamp_enabled else None,
            "rf_attenuation_auto": "INPut:ATTenuation:AUTO?",
            "rf_attenuation": "INPut:ATTenuation?",
        },
    }
    setattr(adapter, _CACHE_ATTRIBUTE, deepcopy(snapshot))
    return snapshot


def _supports(driver: Any, name: str) -> bool:
    checker = getattr(driver, "supports", None)
    if callable(checker):
        return bool(checker(name))
    return hasattr(driver, name)


def _query_bool(driver: Any, command: str) -> bool:
    raw = str(driver.query(command)).strip().upper()
    return raw in {"1", "ON", "TRUE"}


def _query_float(driver: Any, command: str) -> float:
    return float(str(driver.query(command)).strip())
