import pytest
from finboy.core.final_runtime import final_environment
from sqlalchemy.engine import make_url


def test_final_launcher_keeps_worktree_settings_and_secret_values_private(settings):
    original = settings.database_url
    local = settings.model_copy(
        update={
            "database_url": type(original)(
                "postgresql+psycopg://test:synthetic@127.0.0.1:5433/finboy_p5"
            )
        }
    )
    result = final_environment(local, {"PATH": "/synthetic", "UNRELATED": "kept"})
    assert make_url(result["DATABASE_URL"]).database == "finboy"
    assert local.database_url.get_secret_value().endswith("/finboy_p5")
    assert result["PATH"] == "/synthetic" and result["UNRELATED"] == "kept"
    assert result["WEB_APP_URL"] == "http://127.0.0.1:3000"
    assert result["GOOGLE_OAUTH_REDIRECT_URI"].startswith("http://127.0.0.1:8000/")
    assert result["WHATSAPP_ENABLED"] == "false"


@pytest.mark.parametrize(
    "url,environment",
    [
        ("postgresql+psycopg://test:test@remote.example:5433/finboy", "test"),
        ("postgresql+psycopg://test:test@127.0.0.1:5433/production", "test"),
        ("postgresql+psycopg://test:test@127.0.0.1:5433/finboy_p5", "production"),
        ("postgresql+psycopg://test:test@127.0.0.1:5432/finboy_p5", "test"),
    ],
)
def test_final_launcher_refuses_other_environments(settings, url, environment):
    changed = settings.model_copy(
        update={"database_url": type(settings.database_url)(url), "environment": environment}
    )
    with pytest.raises(ValueError, match="reviewed local"):
        final_environment(changed, {})
