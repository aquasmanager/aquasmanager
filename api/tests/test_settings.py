import subprocess
import sys


def _run(env_vars, code):
    return subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env={**env_vars, "PATH": "/usr/bin:/bin", "AQUAS_ENV_FILE": "/nonexistent/.env"}, cwd="."
    )


def test_environment_overrides_yaml_file():
    result = _run(
        {"ENV": "test", "AQUAS_MQTT__PASSWORD": "depuis-env", "AQUAS_SENSOR_READING_RETENTION_DAYS": "30"},
        "from settings import settings as s; print(s.mqtt.password, s.mqtt.topic_prefix, s.sensor_reading_retention_days)",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["depuis-env", "aquarium-test", "30"]


def test_secret_key_generated_without_config(tmp_path):
    env = {"ENV": "aucun-fichier", "AQUAS_DATABASE__SQLITE_PATH": str(tmp_path / "base.db")}
    code = "from settings import settings as s; print(s.secret_key)"
    first = _run(env, code)
    second = _run(env, code)
    assert first.returncode == 0, first.stderr
    assert len(first.stdout.strip()) == 64
    assert first.stdout == second.stdout  # conservée entre deux démarrages


def test_health_endpoint():
    from fastapi.testclient import TestClient

    import main

    response = TestClient(main.app).get("/health")
    assert response.status_code == 200 and response.json() == {"status": "ok"}
