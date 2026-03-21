"""Tests for validate_pre_pr() gate function (issue_resolver/validation.py)."""
import pytest
from unittest.mock import patch, MagicMock
from issue_resolver.context import IssueContext
from issue_resolver.validation import validate_pre_pr, ValidationError


def make_ctx(affected_files=None):
    ctx = IssueContext(issue_number=1, issue_title="T", started_at="2026-01-01T00:00:00Z")
    ctx.affected_files = affected_files or ["src/main.py"]
    return ctx


class TestOutOfScopeFiles:
    """UAT-4a: affected_files 外変更検出"""

    def test_passes_when_only_affected_files_changed(self):
        ctx = make_ctx(["src/main.py"])
        mock_result = MagicMock()
        mock_result.stdout = "src/main.py\n"
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            with patch("os.path.exists", return_value=False):
                validate_pre_pr(ctx)  # Should not raise

    def test_aborts_when_out_of_scope_file_changed(self):
        ctx = make_ctx(["src/main.py"])
        mock_result = MagicMock()
        mock_result.stdout = "src/main.py\nsrc/other.py\n"
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            with patch("os.path.exists", return_value=False):
                with pytest.raises(ValidationError, match="Out-of-scope"):
                    validate_pre_pr(ctx)


class TestExistingTestModification:
    """UAT-4b: 既存テスト変更検出"""

    def test_aborts_when_test_py_file_modified(self):
        ctx = make_ctx(["tests/test_foo.py"])
        mock_result = MagicMock()
        mock_result.stdout = "tests/test_foo.py\n"
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            with patch("os.path.exists", return_value=False):
                with pytest.raises(ValidationError, match="test"):
                    validate_pre_pr(ctx)

    def test_aborts_when_test_suffix_file_modified(self):
        ctx = make_ctx(["src/foo_test.py"])
        mock_result = MagicMock()
        mock_result.stdout = "src/foo_test.py\n"
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            with patch("os.path.exists", return_value=False):
                with pytest.raises(ValidationError, match="test"):
                    validate_pre_pr(ctx)


class TestSecurityScan:
    """UAT-4c: セキュリティスキャン（Python のみ）"""

    def test_aborts_when_bandit_fails(self):
        ctx = make_ctx(["src/main.py"])
        git_result = MagicMock()
        git_result.stdout = "src/main.py\n"
        git_result.returncode = 0

        bandit_result = MagicMock()
        bandit_result.returncode = 1
        bandit_result.stdout = "Issue: [B602] subprocess with shell=True"

        def run_side_effect(args, **kwargs):
            if args[0] == "git":
                return git_result
            return bandit_result

        with patch("subprocess.run", side_effect=run_side_effect):
            with patch("os.path.exists", return_value=True):  # pyproject.toml exists
                with pytest.raises(ValidationError, match="[Bb]andit"):
                    validate_pre_pr(ctx)

    def test_skips_bandit_for_non_python_repos(self):
        ctx = make_ctx(["src/main.go"])
        mock_result = MagicMock()
        mock_result.stdout = "src/main.go\n"
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            with patch("os.path.exists", return_value=False):  # no pyproject.toml
                validate_pre_pr(ctx)  # Should not raise


class TestTokenBudget:
    """UAT-4d: トークン予算超過"""

    def test_aborts_when_token_count_exceeds_150k(self):
        ctx = make_ctx(["src/main.py"])
        mock_result = MagicMock()
        mock_result.stdout = "src/main.py\n"
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            with patch("os.path.exists", return_value=False):
                with pytest.raises(ValidationError, match="[Tt]oken"):
                    validate_pre_pr(ctx, token_count=150_001)

    def test_passes_at_exactly_150k(self):
        ctx = make_ctx(["src/main.py"])
        mock_result = MagicMock()
        mock_result.stdout = "src/main.py\n"
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            with patch("os.path.exists", return_value=False):
                validate_pre_pr(ctx, token_count=150_000)  # Should not raise
