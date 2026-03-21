"""issue-resolver workflow entry point.

Called by main.py as: from issue_resolver.run import run; run()

Pipeline flow (Phase 1 skeleton — agents are stubs until Phase 2-4):
  1. list_open_issues() -> find first unprocessed issue
  2. claim_issue(number) -> lock with agent-processing label
  3. Analyzer -> populate IssueContext.analyzer_output (stub)
  4. Specialist -> implement changes (stub)
  5. validate_pre_pr() -> safety gate
  6. Reviewer -> review changes (stub)
  7. PR Creator -> create PR (Phase 5)
  8. release_issue(number, outcome) -> update label
"""
import asyncio
from datetime import datetime, timezone

from .context import IssueContext
from .github_tools import github_server, _list_open_issues_impl, _claim_issue_impl, _release_issue_impl
from .validation import validate_pre_pr, ValidationError


def run() -> None:
    """Entry point for the issue-resolver workflow. Runs one issue per invocation."""
    asyncio.run(_run_pipeline())


async def _run_pipeline() -> None:
    issues = _list_open_issues_impl()
    if not issues:
        print("[run] No open unprocessed issues found. Exiting.")
        return

    issue = issues[0]
    number = issue["number"]
    title = issue["title"]
    print(f"[run] Processing issue #{number}: {title}")

    _claim_issue_impl(number)
    print(f"[run] Claimed issue #{number} with agent-processing label")

    ctx = IssueContext(
        issue_number=number,
        issue_title=title,
        started_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    try:
        # Phase 2: Analyzer (stub — raises NotImplementedError)
        # Phase 3: Specialist (stub — raises NotImplementedError)
        # Phase 4: Reviewer (stub — raises NotImplementedError)
        # Phase 5: PR Creator
        # validate_pre_pr(ctx) — called after specialist completes
        print(f"[run] Pipeline skeleton complete. IssueContext: {ctx.to_json()}")
        _release_issue_impl(number, "skip")  # Skip until agents are implemented
        print(f"[run] Released issue #{number} as agent-skip (agents not yet implemented)")
    except ValidationError as e:
        print(f"[run] Validation failed: {e}")
        _release_issue_impl(number, "failed")
    except Exception as e:
        print(f"[run] Pipeline error: {e}")
        _release_issue_impl(number, "failed")
