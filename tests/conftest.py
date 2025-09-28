# pytest configuration and shared fixtures for Archon tests
import os
import pytest

@pytest.fixture(autouse=True)
def _set_env_defaults(monkeypatch):
	# Ensure predictable AWS/GitHub env for local tests
	monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
	monkeypatch.setenv("LOCAL_TESTING", "1")
	monkeypatch.setenv("GITHUB_TOKEN", "mock-github-token")
	yield
