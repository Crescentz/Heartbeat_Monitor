from __future__ import annotations

from monitor.webapp import create_app


class _DummyEngine:
    services = {}

    def check_one(self, service_id: str):
        raise RuntimeError("not used")


def main() -> int:
    app = create_app(_DummyEngine(), scheduler=None)
    rules = sorted({str(r) for r in app.url_map.iter_rules()})
    for r in rules:
        if "disabled" in r or r.startswith("/api/admin"):
            print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

