"""Cold-start bind path must not import yfinance or construct Celery."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def test_yfinance_is_not_imported_at_module_level() -> None:
    hits: list[str] = []
    for path in (_ROOT / "backend" / "app").rglob("*.py"):
        if path.name == "yfinance_client.py":
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("import yfinance") or stripped.startswith("from yfinance"):
                indent = len(line) - len(stripped)
                if indent == 0:
                    hits.append(f"{path.relative_to(_ROOT)}:{line_no}")
    assert hits == []


def test_core_package_does_not_construct_celery() -> None:
    text = (_ROOT / "backend" / "app" / "core" / "__init__.py").read_text(encoding="utf-8")
    assert "from app.core.celery_app import celery_app" not in text


def test_lifespan_yields_before_hydrate() -> None:
    text = (_ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    assert text.find("create_task(_hydrate())") < text.find("\n    yield")


def test_keep_warm_retries_health_for_cold_boot() -> None:
    text = (_ROOT / ".github" / "workflows" / "keep-api-warm.yml").read_text(
        encoding="utf-8"
    )
    assert 'while [ "$attempt" -le 6 ]' in text
    assert "--max-time 50" in text
    assert "sleep 12" in text


def test_importing_app_does_not_load_yfinance_or_celery() -> None:
    """uvicorn bind must not pay for Yahoo or a Celery worker that Render does not run."""
    script = (
        "import sys\n"
        "import app.main  # noqa: F401\n"
        "heavy = [\n"
        "    name for name in ('yfinance', 'celery')\n"
        "    if name in sys.modules\n"
        "    or any(key.startswith(name + '.') for key in sys.modules)\n"
        "]\n"
        "print(','.join(heavy) or 'ok')\n"
        "raise SystemExit(1 if heavy else 0)\n"
    )
    env = os.environ.copy()
    env["SIGNAL_STORE"] = "memory"
    env["APP_ENV"] = "development"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_ROOT / "backend",
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "ok"
