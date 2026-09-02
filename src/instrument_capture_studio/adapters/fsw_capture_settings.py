"""Read-only FSW front-end settings captured before acquisition.

The acquisition product must preserve the operator's FSW setup.  These helpers
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

    preamp_enabled = _query_bool(driver, "INPut:GAIN:STATe?")
    preamp_gain_db = (
        int(round(_query_float(driver, "INPut:GAIN:VALue?")))
        if preamp_enabled
        else 0
    )
    attenuation_auto = _query_bool(driver, "INPut:ATTenuation:AUTO?")
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
            "preamp_gain": (
                "INPut:GAIN:VALue?" if preamp_enabled else None
            ),
            "rf_attenuation_auto": "INPut:ATTenuation:AUTO?",
            "rf_attenuation": "INPut:ATTenuation?",
        },
    }
    setattr(adapter, _CACHE_ATTRIBUTE, deepcopy(snapshot))
    return snapshot


def _query_bool(driver: Any, command: str) -> bool:
    raw = str(driver.query(command)).strip().upper()
    return raw in {"1", "ON", "TRUE"}


def _query_float(driver: Any, command: str) -> float:
    return float(str(driver.query(command)).strip())
