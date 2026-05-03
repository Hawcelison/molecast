from app.api.routes import health


class FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement):
        self.statement = statement


def test_health_check_reports_database_readiness(monkeypatch) -> None:
    monkeypatch.setattr(health, "SessionLocal", lambda: FakeSession())

    payload = health.health_check()

    assert payload == {"status": "ok", "database": "ok"}
