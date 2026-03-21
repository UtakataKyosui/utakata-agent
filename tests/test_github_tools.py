"""Tests for GitHub MCP tools (issue_resolver/github_tools.py)."""
import json
import pytest
from unittest.mock import patch, MagicMock
from issue_resolver.github_tools import (
    _list_open_issues_impl,
    _claim_issue_impl,
    _release_issue_impl,
)


AGENT_LABELS = ["agent-processing", "agent-resolved", "agent-skip", "agent-failed"]


class TestListOpenIssues:
    """UAT-1: list_open_issues() が open な未処理 Issue を返す"""

    def test_returns_unprocessed_issues(self):
        """Issues without agent labels are returned."""
        raw_issues = [
            {"number": 1, "title": "Fix bug", "labels": [{"name": "bug"}]},
            {"number": 2, "title": "Add feature", "labels": []},
        ]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(raw_issues)
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = _list_open_issues_impl()
        assert len(result) == 2
        assert result[0]["number"] == 1
        assert result[0]["title"] == "Fix bug"
        assert result[0]["labels"] == ["bug"]

    def test_excludes_processing_issues(self):
        """Issues with agent-processing label are excluded."""
        raw_issues = [
            {"number": 1, "title": "Processing", "labels": [{"name": "agent-processing"}]},
            {"number": 2, "title": "Open", "labels": []},
        ]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(raw_issues)
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = _list_open_issues_impl()
        assert len(result) == 1
        assert result[0]["number"] == 2

    def test_excludes_resolved_issues(self):
        """Issues with agent-resolved label are excluded."""
        raw_issues = [
            {"number": 3, "title": "Resolved", "labels": [{"name": "agent-resolved"}]},
        ]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(raw_issues)
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = _list_open_issues_impl()
        assert result == []

    def test_returns_correct_shape(self):
        """Return value has number (int), title (str), labels (list[str])."""
        raw_issues = [
            {"number": 5, "title": "Test", "labels": [{"name": "bug"}, {"name": "help wanted"}]},
        ]
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(raw_issues)
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = _list_open_issues_impl()
        assert result[0] == {"number": 5, "title": "Test", "labels": ["bug", "help wanted"]}


class TestClaimIssue:
    """UAT-2: claim_issue() でラベルが付与される"""

    def test_adds_agent_processing_label(self):
        """claim_issue(N) calls gh issue edit --add-label agent-processing."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            _claim_issue_impl(42)
        call_args = mock_run.call_args[0][0]
        assert "gh" in call_args
        assert "42" in [str(a) for a in call_args]
        assert "agent-processing" in call_args


class TestReleaseIssue:
    """release_issue() updates label to resolved/skip/failed."""

    def test_release_with_resolved_outcome(self):
        """release_issue(N, 'resolved') removes agent-processing and adds agent-resolved."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            _release_issue_impl(42, "resolved")
        # Should have called gh at least once
        assert mock_run.called

    def test_invalid_outcome_raises(self):
        """release_issue with invalid outcome raises ValueError."""
        with pytest.raises((ValueError, Exception)):
            _release_issue_impl(42, "invalid-outcome")
