"""IssueContext dataclass — pipeline stage handoff data model.

This is the single source of truth for state shared between pipeline agents.
Each agent writes only to its designated zone (append-only after construction).
"""
from __future__ import annotations

import dataclasses
import json
from typing import Optional


@dataclasses.dataclass
class IssueContext:
    """Pipeline handoff object passed between all agents in the issue-resolver workflow.

    Construction requires the 3 immutable metadata fields. All write-zone fields
    have safe defaults so agents can write incrementally without coordination.
    """

    # --- Metadata (immutable after creation) ---
    issue_number: int
    issue_title: str
    started_at: str

    # --- Analyzer write zone (written by Analyzer agent only) ---
    issue_type: str = ""
    affected_files: list[str] = dataclasses.field(default_factory=list)
    implementation_plan: str = ""
    complexity_score: float = 0.0

    # --- Specialist write zone (written by BugFixer/FeatureDev/Refactorer only) ---
    changes_made: list[str] = dataclasses.field(default_factory=list)
    tests_run: bool = False
    tests_passed: bool = False
    error_message: Optional[str] = None

    # --- Reviewer write zone (written by Reviewer agent only) ---
    review_passed: Optional[bool] = None
    review_notes: str = ""
    security_issues: list[str] = dataclasses.field(default_factory=list)

    def to_json(self) -> str:
        """Serialize to JSON string for stage handoff or storage.

        Uses ensure_ascii=False to preserve non-ASCII characters in titles/notes.
        """
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, s: str) -> IssueContext:
        """Deserialize from JSON string produced by to_json()."""
        data = json.loads(s)
        return cls(**data)
