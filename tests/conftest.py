"""The test suite is strictly offline, including adapter and retry tests."""

import urllib.request

import pytest


@pytest.fixture(autouse=True)
def block_real_model_requests(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Tests must mock HTTP; real model calls are forbidden")
    monkeypatch.setattr(urllib.request, "urlopen", blocked)
