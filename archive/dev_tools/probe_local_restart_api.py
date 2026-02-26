from __future__ import annotations

import json
import sys
import time
import urllib.request


def main() -> int:
    with urllib.request.urlopen("http://127.0.0.1:18081/health", timeout=2) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        print(resp.status, body)
        data = json.loads(body or "{}")
        if not data.get("ok"):
            return 2

    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        req = urllib.request.Request(
            "http://127.0.0.1:18081/toggle",
            data=json.dumps({"ok": False}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            print("toggle:", resp.status, resp.read().decode("utf-8", errors="replace"))

        for _ in range(12):
            try:
                with urllib.request.urlopen("http://127.0.0.1:18081/health", timeout=2) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                    data = json.loads(body or "{}")
                    print("health:", resp.status, body)
                    if data.get("ok") is True:
                        return 0
            except Exception as e:
                print("health:", str(e))
            time.sleep(1)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

