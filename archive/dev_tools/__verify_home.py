from monitor.webapp import create_app


class _DummyEngine:
    services = {}

    def control(self, service_id: str, action: str):
        return True, "ok"


def main() -> int:
    app = create_app(_DummyEngine())
    app.testing = True
    with app.test_client() as client:
        resp = client.get("/")
        print(resp.status_code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

