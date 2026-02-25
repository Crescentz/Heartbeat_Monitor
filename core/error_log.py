from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


LOG_DIR = os.path.join("data", "logs")
ERROR_LOG_PATH = os.path.join(LOG_DIR, "errors.jsonl")
RETENTION_DAYS_DEFAULT = 7

_last_prune_day: Optional[str] = None


def append_error(service_id: str, service_name: str, reason: str) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    _prune_if_needed(RETENTION_DAYS_DEFAULT)
    now = datetime.now()
    record = {
        "ts": now.strftime("%Y-%m-%d %H:%M:%S"),
        "ts_epoch": int(time.time()),
        "service_id": service_id,
        "service_name": service_name,
        "reason": reason,
    }
    with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def tail_errors(limit: int = 10, retention_days: int = RETENTION_DAYS_DEFAULT) -> List[Dict[str, Any]]:
    items, _ = query_errors(limit=limit, page=1, page_size=limit, retention_days=retention_days)
    return items


def query_errors(
    service_id: Optional[str] = None,
    retention_days: int = RETENTION_DAYS_DEFAULT,
    page: int = 1,
    page_size: int = 20,
    limit: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    if not os.path.exists(ERROR_LOG_PATH):
        return [], 0

    cutoff = int(time.time()) - int(retention_days) * 86400
    records: List[Dict[str, Any]] = []
    with open(ERROR_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            ts_epoch = _record_ts_epoch(rec)
            if ts_epoch < cutoff:
                continue
            if service_id and str(rec.get("service_id") or "") != service_id:
                continue
            rec["ts_epoch"] = ts_epoch
            if not rec.get("ts"):
                rec["ts"] = datetime.fromtimestamp(ts_epoch).strftime("%Y-%m-%d %H:%M:%S")
            records.append(rec)

    records.sort(key=lambda r: int(r.get("ts_epoch") or 0), reverse=True)
    total = len(records)
    if limit is not None:
        records = records[: int(limit)]
        return records, min(total, int(limit))

    page = max(int(page), 1)
    page_size = max(int(page_size), 1)
    start = (page - 1) * page_size
    end = start + page_size
    return records[start:end], total


def prune_errors(retention_days: int = RETENTION_DAYS_DEFAULT) -> None:
    if not os.path.exists(ERROR_LOG_PATH):
        return
    cutoff = int(time.time()) - int(retention_days) * 86400
    kept: List[str] = []
    with open(ERROR_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except Exception:
                continue
            if _record_ts_epoch(rec) >= cutoff:
                kept.append(json.dumps(rec, ensure_ascii=False))

    tmp = ERROR_LOG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for line in kept:
            f.write(line + "\n")
    os.replace(tmp, ERROR_LOG_PATH)


def _prune_if_needed(retention_days: int) -> None:
    global _last_prune_day
    today = datetime.now().strftime("%Y-%m-%d")
    if _last_prune_day == today:
        return
    prune_errors(retention_days)
    _last_prune_day = today


def _record_ts_epoch(rec: Dict[str, Any]) -> int:
    v = rec.get("ts_epoch")
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    ts = rec.get("ts")
    if isinstance(ts, str) and ts.strip():
        try:
            return int(datetime.strptime(ts.strip(), "%Y-%m-%d %H:%M:%S").timestamp())
        except Exception:
            return 0
    return 0

