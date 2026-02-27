from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class ScheduleSpec:
    trigger: str
    kwargs: Dict[str, Any]


def job_id_for_service(service_id: str) -> str:
    sid = str(service_id or "")
    safe = "".join((c if c.isalnum() or c in ("_", "-") else "_") for c in sid)
    return "check_" + safe


def parse_check_schedule(value: Any, default_minutes: int = 30, strict: bool = False) -> ScheduleSpec:
    """
    解析服务检查频率，转换为 APScheduler 触发器配置。

    支持格式：
    - "<n>s" / "<n>m" / "<n>h"
    - "daily@HH:MM"
    - "weekly@mon HH:MM"（星期字段遵循 APScheduler day_of_week）

    strict=False：非法值回退为默认分钟间隔。
    strict=True：非法值直接抛出 ValueError，便于接口层返回 400。
    """
    if value is None:
        return ScheduleSpec("interval", {"minutes": int(default_minutes)})
    if isinstance(value, (int, float)):
        secs = int(value)
        secs = max(secs, 1)
        return ScheduleSpec("interval", {"seconds": secs})
    s = str(value or "").strip()
    if not s:
        return ScheduleSpec("interval", {"minutes": int(default_minutes)})
    s = s.lower()

    if s.endswith("s") and s[:-1].isdigit():
        return ScheduleSpec("interval", {"seconds": max(int(s[:-1]), 1)})
    if s.endswith("m") and s[:-1].isdigit():
        return ScheduleSpec("interval", {"minutes": max(int(s[:-1]), 1)})
    if s.endswith("h") and s[:-1].isdigit():
        return ScheduleSpec("interval", {"hours": max(int(s[:-1]), 1)})

    if s.startswith("daily@"):
        hhmm = s[len("daily@") :].strip()
        h, m = _parse_hhmm(hhmm)
        return ScheduleSpec("cron", {"hour": h, "minute": m})

    if s.startswith("weekly@"):
        rest = s[len("weekly@") :].strip()
        parts = [p for p in rest.split() if p.strip()]
        if len(parts) >= 2:
            dow = parts[0].strip().lower()
            h, m = _parse_hhmm(parts[1])
            return ScheduleSpec("cron", {"day_of_week": dow, "hour": h, "minute": m})

    if strict:
        raise ValueError(f"invalid_check_schedule: {value!r}")
    return ScheduleSpec("interval", {"minutes": int(default_minutes)})


def _parse_hhmm(hhmm: str) -> Tuple[int, int]:
    hhmm = str(hhmm or "").strip()
    parts = hhmm.split(":")
    if len(parts) < 2:
        return 0, 0
    h = int(parts[0]) if parts[0].isdigit() else 0
    m = int(parts[1]) if parts[1].isdigit() else 0
    h = min(max(h, 0), 23)
    m = min(max(m, 0), 59)
    return h, m
