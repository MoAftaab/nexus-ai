"""Test environment: isolated database, fixed seed, no external LLM.

These must be set before ``main`` (and therefore ``get_settings``) is imported,
which pytest guarantees because conftest is loaded before test modules.
"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./nexus_test.db"
os.environ["DEMO_SEED"] = "1234"
os.environ["OPENAI_API_KEY"] = ""
