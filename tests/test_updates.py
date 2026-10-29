import httpx
import pytest

from launcher import updates
from launcher.bridge import Bridge


@pytest.fixture(autouse=True)
def clear_cache():
    updates._cache = None
    yield
    updates._cache = None


def test_version_parts_accepts_the_v_prefix():
    assert updates.version_parts("v3.7.1") == (3, 7, 1)
    assert updates.version_parts("3.7") == (3, 7)
    assert updates.version_parts("release") == ()


def test_is_newer_compares_each_part():
    assert updates.is_newer("3.7.1", "3.7.0") is True
    assert updates.is_newer("v3.8", "3.7.9") is True
    assert updates.is_newer("3.7.0", "3.7.0") is False
    assert updates.is_newer("3.7.0.0", "3.7") is False
    assert updates.is_newer("nightly", "3.7.0") is False


def test_check_reports_an_available_update(monkeypatch):
    monkeypatch.setattr(
        updates,
        "_fetch",
        lambda timeout: {
            "tag_name": "v3.8.0",
            "html_url": "https://github.com/x01Jin/discord-games-launcher/releases/tag/v3.8.0",
        },
    )

    result = updates.check(force=True)

    assert result["update_available"] is True
    assert result["latest"] == "3.8.0"
    assert result["version"] == updates.__version__
    assert result["release_url"].endswith("/v3.8.0")


def test_check_keeps_the_current_version_when_github_fails(monkeypatch):
    def fail(timeout):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(updates, "_fetch", fail)

    result = updates.check(force=True)

    assert result["update_available"] is False
    assert result["version"] == updates.__version__
    assert "offline" in result["error"]


def test_bridge_exposes_the_running_version():
    info = Bridge(None).get_app_info()

    assert info["version"] == updates.__version__
    assert info["repo_url"] == updates.REPO_URL


def test_bridge_opens_the_release_or_repository(monkeypatch):
    opened = []
    monkeypatch.setattr(
        "launcher.bridge.webbrowser.open",
        lambda url, new=0: opened.append(url) or True,
    )
    bridge = Bridge(None)

    release = bridge.open_project_page("latest")
    repository = bridge.open_project_page("repo")

    assert release["ok"] is True
    assert repository["ok"] is True
    assert opened == [updates.RELEASES_URL, updates.REPO_URL]
