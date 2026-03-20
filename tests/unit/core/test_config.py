from agent_trader.core.config import get_settings


def test_grouped_settings_are_available() -> None:
    settings = get_settings()

    assert settings.system.name == settings.app_name
    assert settings.mongo.database == settings.mongo_database
    assert settings.influx.bucket == settings.influx_bucket
    assert settings.worker.timezone
    assert settings.agent.max_concurrency > 0