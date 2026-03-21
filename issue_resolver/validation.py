"""Pre-PR safety gate for the issue-resolver pipeline.

validate_pre_pr() enforces 4 hard-abort conditions before a PR is created.
This is the safety foundation that prevents unsafe code from reaching GitHub.
"""
from __future__ import annotations

import os
import re
import subprocess
from typing import TYPE_CHECKING

from .context import IssueContext


class ValidationError(Exception):
    """Pre-PR validation failure. Message is posted as Issue comment."""


# Test file patterns — any changed file matching these patterns is rejected
_TEST_PATTERNS = [
    re.compile(r"^test_.*\.py$"),        # test_foo.py (pytest prefix convention)
    re.compile(r".*_test\.py$"),          # foo_test.py (suffix convention)
    re.compile(r".*\.test\..*$"),         # foo.test.js (JavaScript convention)
    re.compile(r"^tests/"),               # anything inside tests/ directory
]


def validate_pre_pr(ctx: IssueContext, token_count: int = 0) -> None:
    """Run 4 hard-abort checks before creating a PR.

    Checks (in order):
    1. No out-of-scope files changed (only ctx.affected_files allowed)
    2. No existing test files modified
    3. Bandit security scan passes (Python repos only)
    4. Token budget not exceeded (> 150,000 tokens)

    Raises:
        ValidationError: If any condition is violated. Message suitable for
            posting as a GitHub Issue comment.
    """
    # --- Check 1: Out-of-scope files ---
    git_result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    changed_files = {f for f in git_result.stdout.splitlines() if f}
    allowed_files = set(ctx.affected_files)
    out_of_scope = changed_files - allowed_files
    if out_of_scope:
        files_list = ", ".join(sorted(out_of_scope))
        raise ValidationError(
            f"Out-of-scope files modified: {files_list}. "
            f"Only changes to {sorted(allowed_files)} are permitted for this issue."
        )

    # --- Check 2: Existing test files modified ---
    for changed_file in changed_files:
        filename = os.path.basename(changed_file)
        for pattern in _TEST_PATTERNS:
            if pattern.match(changed_file) or pattern.match(filename):
                raise ValidationError(
                    f"Existing test file modified: {changed_file}. "
                    "Agents must not modify existing test files to avoid test gaming."
                )

    # --- Check 3: Bandit security scan (Python repos only) ---
    if os.path.exists("pyproject.toml") or os.path.exists("pytest.ini"):
        bandit_result = subprocess.run(
            ["bandit", "-ll", "-r", "."],
            capture_output=True,
            text=True,
        )
        if bandit_result.returncode != 0:
            raise ValidationError(
                f"Bandit security scan failed with exit code {bandit_result.returncode}. "
                f"Output:\n{bandit_result.stdout}"
            )

    # --- Check 4: Token budget ---
    if token_count > 150_000:
        raise ValidationError(
            f"Token budget exceeded: {token_count:,} tokens used, limit is 150,000. "
            "Aborting to prevent runaway costs."
        )
