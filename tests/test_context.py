"""Tests for IssueContext dataclass (issue_resolver/context.py)."""
import pytest
from issue_resolver.context import IssueContext


class TestIssueContextDefaults:
    def test_metadata_fields_required(self):
        """issue_number, issue_title, started_at are required at construction."""
        ctx = IssueContext(issue_number=42, issue_title="Fix bug", started_at="2026-03-22T00:00:00Z")
        assert ctx.issue_number == 42
        assert ctx.issue_title == "Fix bug"
        assert ctx.started_at == "2026-03-22T00:00:00Z"

    def test_analyzer_zone_defaults(self):
        """Analyzer write zone fields have sensible defaults."""
        ctx = IssueContext(issue_number=1, issue_title="T", started_at="2026-01-01T00:00:00Z")
        assert ctx.issue_type == ""
        assert ctx.affected_files == []
        assert ctx.implementation_plan == ""
        assert ctx.complexity_score == 0.0

    def test_specialist_zone_defaults(self):
        """Specialist write zone fields have sensible defaults."""
        ctx = IssueContext(issue_number=1, issue_title="T", started_at="2026-01-01T00:00:00Z")
        assert ctx.changes_made == []
        assert ctx.tests_run is False
        assert ctx.tests_passed is False
        assert ctx.error_message is None

    def test_reviewer_zone_defaults(self):
        """Reviewer write zone fields have sensible defaults. review_passed=None means abort."""
        ctx = IssueContext(issue_number=1, issue_title="T", started_at="2026-01-01T00:00:00Z")
        assert ctx.review_passed is None
        assert ctx.review_notes == ""
        assert ctx.security_issues == []

    def test_mutable(self):
        """IssueContext is mutable — each stage writes to its own zone."""
        ctx = IssueContext(issue_number=1, issue_title="T", started_at="2026-01-01T00:00:00Z")
        ctx.issue_type = "bug"
        assert ctx.issue_type == "bug"


class TestIssueContextSerialization:
    def test_to_json_roundtrip(self):
        """to_json() / from_json() roundtrip preserves all fields."""
        ctx = IssueContext(
            issue_number=99,
            issue_title="Roundtrip test",
            started_at="2026-03-22T12:00:00Z",
            issue_type="feature",
            affected_files=["src/foo.py", "src/bar.py"],
            complexity_score=3.5,
            review_passed=True,
            review_notes="LGTM",
        )
        restored = IssueContext.from_json(ctx.to_json())
        assert restored.issue_number == 99
        assert restored.issue_title == "Roundtrip test"
        assert restored.issue_type == "feature"
        assert restored.affected_files == ["src/foo.py", "src/bar.py"]
        assert restored.complexity_score == 3.5
        assert restored.review_passed is True
        assert restored.review_notes == "LGTM"

    def test_to_json_produces_string(self):
        """to_json() returns a str (not bytes)."""
        ctx = IssueContext(issue_number=1, issue_title="T", started_at="2026-01-01T00:00:00Z")
        result = ctx.to_json()
        assert isinstance(result, str)
        assert '"issue_number"' in result

    def test_from_json_none_review_passed(self):
        """from_json() correctly deserializes review_passed=None."""
        ctx = IssueContext(issue_number=1, issue_title="T", started_at="2026-01-01T00:00:00Z")
        assert ctx.review_passed is None
        restored = IssueContext.from_json(ctx.to_json())
        assert restored.review_passed is None
