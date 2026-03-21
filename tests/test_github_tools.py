"""Tests for GitHub MCP tools in issue_resolver/github_tools.py.

Tests call the synchronous implementation helpers directly (not the async
@tool handlers) so they run without an async event loop.
"""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from issue_resolver.github_tools import (
    _claim_issue_impl,
    _list_open_issues_impl,
    _release_issue_impl,
    github_server,
)


# ---------------------------------------------------------------------------
# _list_open_issues_impl
# ---------------------------------------------------------------------------

def _make_gh_output(issues: list[dict]) -> MagicMock:
    """Return a mock CompletedProcess whose stdout is JSON of *issues*."""
    mock_result = MagicMock()
    mock_result.stdout = json.dumps(issues)
    return mock_result


def test_list_open_issues_returns_only_unprocessed(monkeypatch):
    """Issues with any agent-* label are excluded from the result."""
    raw_issues = [
        {
            "number": 1,
            "title": "Fix the bug",
            "labels": [{"name": "bug"}, {"name": "good first issue"}],
        },
        {
            "number": 2,
            "title": "Processing now",
            "labels": [{"name": "agent-processing"}],
        },
        {
            "number": 3,
            "title": "Already resolved",
            "labels": [{"name": "agent-resolved"}],
        },
        {
            "number": 4,
            "title": "Skipped",
            "labels": [{"name": "agent-skip"}],
        },
        {
            "number": 5,
            "title": "Failed",
            "labels": [{"name": "agent-failed"}],
        },
        {
            "number": 6,
            "title": "Another open issue",
            "labels": [],
        },
    ]

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kwargs: _make_gh_output(raw_issues),
    )

    result = _list_open_issues_impl()

    # Only issues 1 and 6 should be returned
    assert len(result) == 2
    numbers = {issue["number"] for issue in result}
    assert numbers == {1, 6}


def test_list_open_issues_result_shape(monkeypatch):
    """Each returned item has exactly: number (int), title (str), labels (list[str])."""
    raw_issues = [
        {
            "number": 10,
            "title": "Sample issue",
            "labels": [{"name": "enhancement"}],
        }
    ]

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kwargs: _make_gh_output(raw_issues),
    )

    result = _list_open_issues_impl()

    assert len(result) == 1
    item = result[0]
    assert isinstance(item["number"], int)
    assert isinstance(item["title"], str)
    assert isinstance(item["labels"], list)
    # Labels must be plain strings, not dicts
    assert all(isinstance(label, str) for label in item["labels"])
    assert item["labels"] == ["enhancement"]


def test_list_open_issues_agent_processing_excluded(monkeypatch):
    """agent-processing label causes the issue to be excluded."""
    raw_issues = [
        {
            "number": 7,
            "title": "In progress",
            "labels": [{"name": "bug"}, {"name": "agent-processing"}],
        }
    ]

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kwargs: _make_gh_output(raw_issues),
    )

    result = _list_open_issues_impl()
    assert result == []


def test_list_open_issues_agent_resolved_excluded(monkeypatch):
    """agent-resolved label causes the issue to be excluded."""
    raw_issues = [
        {
            "number": 8,
            "title": "Done",
            "labels": [{"name": "agent-resolved"}],
        }
    ]

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kwargs: _make_gh_output(raw_issues),
    )

    result = _list_open_issues_impl()
    assert result == []


# ---------------------------------------------------------------------------
# _claim_issue_impl
# ---------------------------------------------------------------------------

def test_claim_issue_calls_subprocess_with_correct_args():
    """_claim_issue_impl(42) calls gh issue edit 42 --add-label agent-processing."""
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        mock = MagicMock()
        mock.stdout = ""
        return mock

    with patch("subprocess.run", side_effect=fake_run):
        _claim_issue_impl(42)

    assert len(calls) == 1
    cmd = calls[0]
    assert "gh" in cmd
    assert "42" in cmd
    assert "agent-processing" in cmd


def test_claim_issue_uses_list_args():
    """subprocess.run must be called with a list, not a shell string."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="")
        _claim_issue_impl(99)

    # Ensure shell=False (the default when args is a list, but verify no shell=True)
    _call = mock_run.call_args
    # First positional arg must be a list
    assert isinstance(_call.args[0], list)


# ---------------------------------------------------------------------------
# _release_issue_impl
# ---------------------------------------------------------------------------

def test_release_issue_resolved_succeeds():
    """_release_issue_impl(42, 'resolved') completes without raising."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="")
        # Should not raise
        _release_issue_impl(42, "resolved")


def test_release_issue_skip_succeeds():
    """_release_issue_impl(42, 'skip') completes without raising."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="")
        _release_issue_impl(42, "skip")


def test_release_issue_failed_succeeds():
    """_release_issue_impl(42, 'failed') completes without raising."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="")
        _release_issue_impl(42, "failed")


def test_release_issue_invalid_outcome_raises():
    """_release_issue_impl with an unknown outcome raises ValueError."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="")
        with pytest.raises((ValueError, KeyError)):
            _release_issue_impl(42, "invalid-outcome")


def test_release_issue_removes_processing_label():
    """_release_issue_impl calls --remove-label agent-processing."""
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return MagicMock(stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        _release_issue_impl(42, "resolved")

    # At least one call should include --remove-label and agent-processing
    remove_calls = [c for c in calls if "--remove-label" in c and "agent-processing" in c]
    assert len(remove_calls) >= 1


def test_release_issue_adds_outcome_label():
    """_release_issue_impl(42, 'resolved') adds agent-resolved label."""
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return MagicMock(stdout="")

    with patch("subprocess.run", side_effect=fake_run):
        _release_issue_impl(42, "resolved")

    # At least one call should add agent-resolved
    add_calls = [c for c in calls if "--add-label" in c and "agent-resolved" in c]
    assert len(add_calls) >= 1


# ---------------------------------------------------------------------------
# github_server
# ---------------------------------------------------------------------------

def test_github_server_is_importable():
    """github_server can be imported from issue_resolver.github_tools."""
    # If import succeeded at module load, this trivially passes.
    assert github_server is not None


def test_github_server_has_correct_type():
    """github_server is a McpSdkServerConfig instance."""
    from claude_agent_sdk import McpSdkServerConfig

    assert isinstance(github_server, McpSdkServerConfig)
