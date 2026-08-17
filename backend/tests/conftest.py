"""Test environment: isolated database, fixed seed, no external LLM.

These must be set before ``main`` (and therefore ``get_settings``) is imported,
which pytest guarantees because conftest is loaded before test modules.
"""
import os
import sys
import tempfile
from pathlib import Path

test_database = Path(tempfile.gettempdir()) / f"warehouse_control_tower_pytest_{os.getpid()}.db"
test_database.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{test_database.as_posix()}"
os.environ["DEMO_SEED"] = "1234"
os.environ["OPENAI_API_KEY"] = ""
os.environ["ALLOW_LEGACY_DIRECT_APPLY"] = "true"

# Demo reset normally refreshes human-readable exports for operators. Rewriting
# the same deterministic files for every isolated API test is unnecessary and
# especially expensive in a synced workspace.
from app.services import operations as operations_module

operations_module.export_dataset = lambda _dataset: None
operations_module.prepare_operational_markdown = lambda _dataset: None


def pytest_sessionfinish(session, exitstatus):
    del session, exitstatus
    # SQLite keeps an idle pooled handle open on Windows until the engine is
    # disposed. Release it before deleting the process-scoped test database.
    try:
        main_module = sys.modules.get("main")
        if main_module is not None:
            main_module.store.repository.engine.dispose()
    except AttributeError:
        pass
    for suffix in ("", "-wal", "-shm"):
        try:
            Path(f"{test_database}{suffix}").unlink(missing_ok=True)
        except PermissionError:
            # A short-lived Repository created directly by a test may still be
            # finalizing; the OS temporary directory can safely reclaim it.
            pass
