from __future__ import annotations

from typing import Callable, Dict, Mapping


OFF_SCHEDULE_VALUES = frozenset(("off", "pause", "paused", "disabled", "disable"))


def is_schedule_paused(value: object) -> bool:
    return str(value or "").strip().lower() in OFF_SCHEDULE_VALUES


def build_initial_auto_check_map(services: Mapping[str, object], overrides: Mapping[str, str]) -> Dict[str, bool]:
    initial: Dict[str, bool] = {}
    for sid, svc in services.items():
        cfg = getattr(svc, "config", None)
        if not isinstance(cfg, dict):
            initial[str(sid)] = False
            continue
        if is_schedule_paused(overrides.get(str(sid))):
            initial[str(sid)] = False
        else:
            initial[str(sid)] = bool(cfg.get("auto_check", False))
    return initial


def build_initial_ops_map(services: Mapping[str, object]) -> Dict[str, bool]:
    initial: Dict[str, bool] = {}
    for sid, svc in services.items():
        cfg = getattr(svc, "config", None)
        initial[str(sid)] = bool(cfg.get("ops_default_enabled", False)) if isinstance(cfg, dict) else False
    return initial


def backfill_bool_store(
    current_map: Mapping[str, bool],
    initial_map: Mapping[str, bool],
    setter: Callable[[str, bool], None],
) -> Dict[str, bool]:
    merged = {str(k): bool(v) for k, v in current_map.items()}
    for sid, enabled in initial_map.items():
        key = str(sid)
        if key in merged:
            continue
        setter(key, bool(enabled))
        merged[key] = bool(enabled)
    return merged


def apply_runtime_service_flags(
    services: Mapping[str, object],
    *,
    overrides: Mapping[str, str],
    disabled_map: Mapping[str, bool],
    ops_enabled_map: Mapping[str, bool],
    auto_check_enabled_map: Mapping[str, bool],
    failure_policies: Mapping[str, str],
) -> None:
    for sid, svc in services.items():
        cfg = getattr(svc, "config", None)
        if not isinstance(cfg, dict):
            continue

        sid = str(sid)
        if "_base_check_schedule" not in cfg:
            cfg["_base_check_schedule"] = str(cfg.get("check_schedule") or "").strip()

        cfg["_disabled"] = bool(disabled_map.get(sid, False))
        cfg["_ops_enabled"] = bool(ops_enabled_map.get(sid, bool(cfg.get("ops_default_enabled", False))))

        policy = str(failure_policies.get(sid) or "").strip().lower()
        if policy == "alert":
            cfg["on_failure"] = "alert"
            cfg["auto_fix"] = False
        elif policy == "restart":
            cfg["on_failure"] = "restart"
            cfg["auto_fix"] = True

        if is_schedule_paused(overrides.get(sid)):
            cfg["_auto_check_enabled"] = False
            cfg["auto_check"] = False
        else:
            enabled = bool(auto_check_enabled_map.get(sid, bool(cfg.get("auto_check", False))))
            cfg["_auto_check_enabled"] = enabled
            cfg["auto_check"] = enabled
