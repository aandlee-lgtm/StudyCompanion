"""Simulation tests (selection-21). The 12-week runs are marked ``slow`` and run on request:

    python3 -m pytest -m slow tests/sim          # or HSC_RUN_SLOW=1 python3 -m pytest
"""
from __future__ import annotations

import os

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: long longitudinal simulations (run with -m slow or HSC_RUN_SLOW=1)")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("HSC_RUN_SLOW") == "1" or "slow" in (config.option.markexpr or ""):
        return
    skip = pytest.mark.skip(reason="slow simulation: run with -m slow or HSC_RUN_SLOW=1")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


@pytest.fixture()
def sim_dir(tmp_path, monkeypatch):
    from app.ai import factory
    from app.config import config
    from app.services import clock

    monkeypatch.setattr(config, "data_dir", tmp_path)
    yield tmp_path
    clock.set_today(None)
    factory.set_test_provider(None)
