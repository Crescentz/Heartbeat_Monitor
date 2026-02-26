from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

import requests


def match_expected(response: requests.Response, expected: Any) -> Tuple[bool, str]:
    if response.status_code >= 500:
        return False, f"HTTP {response.status_code}"
    if expected is None:
        return (200 <= response.status_code < 300), f"HTTP {response.status_code}"
    if isinstance(expected, list):
        last_reason = ""
        for one in expected:
            ok, reason = match_expected(response, one)
            if ok:
                return True, ""
            last_reason = reason
        return False, last_reason or "No expected matched"
    if isinstance(expected, str):
        if expected in (response.text or ""):
            return True, ""
        return False, f"Expected substring not found: {expected}"
    if isinstance(expected, dict):
        expected_type = str(expected.get("__type") or "").strip().lower()
        if expected_type in ("text", "html"):
            return _match_text(response, expected)
        return _match_json(response, expected)
    return False, f"Bad expected_response type: {type(expected).__name__}"


def _match_text(response: requests.Response, expected: Dict[str, Any]) -> Tuple[bool, str]:
    text = response.text or ""
    contains = expected.get("__contains")
    if isinstance(contains, str) and contains:
        if contains not in text:
            return False, f"Expected substring not found: {contains}"
    regex = expected.get("__regex")
    if isinstance(regex, str) and regex:
        try:
            if re.search(regex, text) is None:
                return False, f"Expected regex not matched: {regex}"
        except Exception as e:
            return False, f"Bad regex: {e}"
    return (200 <= response.status_code < 300), f"HTTP {response.status_code}"


def _match_json(response: requests.Response, expected: Dict[str, Any]) -> Tuple[bool, str]:
    try:
        body = response.json()
    except Exception:
        return False, "Response is not JSON"
    if "__rules" in expected:
        rules = expected.get("__rules")
        if not isinstance(rules, list):
            return False, "__rules must be a list"
        for i, rule in enumerate(rules):
            if not isinstance(rule, dict):
                return False, f"Rule {i+1} is not an object"
            ok, reason = _eval_rule(body, rule, response_text=(response.text or ""))
            if not ok:
                return False, reason
        return True, ""
    for k, v in expected.items():
        if str(k).startswith("__"):
            continue
        if not isinstance(body, dict) or body.get(k) != v:
            return False, f"Expected {k}={v}"
    return True, ""


def _eval_rule(body: Any, rule: Dict[str, Any], response_text: str) -> Tuple[bool, str]:
    path = str(rule.get("path") or "").strip()
    op = str(rule.get("op") or "==").strip().lower()
    value = rule.get("value")
    if not path:
        return False, "Rule missing path"
    if path == "$text":
        actual = response_text
    else:
        ok, actual, err = _get_path(body, path)
        if not ok:
            return False, err
    if op == "exists":
        return True, ""
    if op in ("==", "eq"):
        return (actual == value), f"Rule failed: {path} == {value}"
    if op in ("!=", "ne"):
        return (actual != value), f"Rule failed: {path} != {value}"
    if op in ("contains",):
        if isinstance(actual, str) and isinstance(value, str):
            return (value in actual), f"Rule failed: {path} contains {value}"
        if isinstance(actual, list):
            return (value in actual), f"Rule failed: {path} contains {value}"
        return False, f"Rule failed: {path} contains expects string/list"
    if op in ("in",):
        if isinstance(value, list):
            return (actual in value), f"Rule failed: {path} in {value}"
        return False, f"Rule failed: {path} in expects list"
    if op in ("regex",):
        if not isinstance(actual, str) or not isinstance(value, str):
            return False, f"Rule failed: {path} regex expects string"
        try:
            return (re.search(value, actual) is not None), f"Rule failed: {path} regex {value}"
        except Exception as e:
            return False, f"Bad regex: {e}"
    if op in ("gt", "ge", "lt", "le"):
        try:
            a = float(actual)
            b = float(value)
        except Exception:
            return False, f"Rule failed: {path} {op} expects numbers"
        if op == "gt":
            return (a > b), f"Rule failed: {path} > {value}"
        if op == "ge":
            return (a >= b), f"Rule failed: {path} >= {value}"
        if op == "lt":
            return (a < b), f"Rule failed: {path} < {value}"
        return (a <= b), f"Rule failed: {path} <= {value}"
    if op.startswith("len_"):
        try:
            n = len(actual)
            b = int(value)
        except Exception:
            return False, f"Rule failed: {path} {op} expects len and int"
        if op == "len_gt":
            return (n > b), f"Rule failed: len({path}) > {value}"
        if op == "len_ge":
            return (n >= b), f"Rule failed: len({path}) >= {value}"
        if op == "len_lt":
            return (n < b), f"Rule failed: len({path}) < {value}"
        if op == "len_le":
            return (n <= b), f"Rule failed: len({path}) <= {value}"
        return False, f"Unknown op: {op}"
    return False, f"Unknown op: {op}"


def _get_path(root: Any, path: str) -> Tuple[bool, Any, str]:
    cur = root
    for part in _split_path(path):
        if isinstance(part, int):
            if not isinstance(cur, list):
                return False, None, f"Path not a list: {path}"
            if part < 0 or part >= len(cur):
                return False, None, f"Path index out of range: {path}"
            cur = cur[part]
            continue
        if not isinstance(cur, dict):
            return False, None, f"Path not an object: {path}"
        if part not in cur:
            return False, None, f"Path not found: {path}"
        cur = cur[part]
    return True, cur, ""


def _split_path(path: str) -> List[Any]:
    parts: List[Any] = []
    buf = ""
    i = 0
    while i < len(path):
        ch = path[i]
        if ch == ".":
            if buf:
                parts.append(buf)
                buf = ""
            i += 1
            continue
        if ch == "[":
            if buf:
                parts.append(buf)
                buf = ""
            j = path.find("]", i + 1)
            if j == -1:
                parts.append(path[i:])
                return parts
            idx = path[i + 1 : j].strip()
            try:
                parts.append(int(idx))
            except Exception:
                parts.append(idx)
            i = j + 1
            continue
        buf += ch
        i += 1
    if buf:
        parts.append(buf)
    return parts
