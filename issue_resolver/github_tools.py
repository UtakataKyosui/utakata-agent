"""GitHub MCP tools for the issue-resolver workflow.

All GitHub interactions go through the `gh` CLI via `subprocess.run` with
`shell=False` to prevent shell injection.  Each tool is exposed as an MCP
tool via the `@tool` decorator and assembled into `github_server`, which is
a `McpSdkServerConfig` ready to be passed to
``ClaudeAgentOptions(mcp_servers={"github": github_server})``.

Public exports:
    _list_open_issues_impl  -- synchronous helper (also called by tests)
    _claim_issue_impl       -- synchronous helper (also called by tests)
    _release_issue_impl     -- synchronous helper (also called by tests)
    github_server           -- McpSdkServerConfig for use with ClaudeSDKClient
"""

import json
import subprocess

from claude_agent_sdk import create_sdk_mcp_server, tool

# Labels that indicate an issue is already handled by an agent.
# Issues bearing any of these labels are excluded from list_open_issues().
AGENT_LABELS: frozenset[str] = frozenset(
    {"agent-processing", "agent-resolved", "agent-skip", "agent-failed"}
)

# Valid outcome strings accepted by release_issue.
VALID_OUTCOMES: frozenset[str] = frozenset({"resolved", "skip", "failed"})


# ---------------------------------------------------------------------------
# Synchronous implementation helpers
# ---------------------------------------------------------------------------


def _list_open_issues_impl() -> list[dict]:
    """Return open issues that are not currently being handled by an agent.

    Calls ``gh issue list --json`` and filters out any issue that has at least
    one label whose name is in ``AGENT_LABELS``.

    Returns:
        List of dicts with keys: ``number`` (int), ``title`` (str),
        ``labels`` (list[str]).
    """
    result = subprocess.run(
        ["gh", "issue", "list", "--state", "open", "--json", "number,title,labels"],
        capture_output=True,
        text=True,
        check=True,
    )
    raw_issues: list[dict] = json.loads(result.stdout)

    filtered = []
    for issue in raw_issues:
        # Labels from gh CLI arrive as list[{"name": str, ...}]
        label_names: list[str] = [
            lbl["name"] for lbl in issue.get("labels", [])
        ]
        if AGENT_LABELS.isdisjoint(label_names):
            filtered.append(
                {
                    "number": issue["number"],
                    "title": issue["title"],
                    "labels": label_names,
                }
            )
    return filtered


def _claim_issue_impl(number: int) -> None:
    """Add the ``agent-processing`` label to the given issue.

    Args:
        number: GitHub issue number.
    """
    subprocess.run(
        ["gh", "issue", "edit", str(number), "--add-label", "agent-processing"],
        capture_output=True,
        text=True,
        check=True,
    )


def _release_issue_impl(number: int, outcome: str) -> None:
    """Remove ``agent-processing`` and add the outcome-specific label.

    Args:
        number:  GitHub issue number.
        outcome: One of ``"resolved"``, ``"skip"``, or ``"failed"``.

    Raises:
        ValueError: If *outcome* is not one of the valid values.
    """
    if outcome not in VALID_OUTCOMES:
        raise ValueError(
            f"Invalid outcome {outcome!r}. Must be one of {sorted(VALID_OUTCOMES)}."
        )

    # Remove the processing lock first.
    subprocess.run(
        ["gh", "issue", "edit", str(number), "--remove-label", "agent-processing"],
        capture_output=True,
        text=True,
        check=True,
    )
    # Add the outcome label.
    subprocess.run(
        ["gh", "issue", "edit", str(number), "--add-label", f"agent-{outcome}"],
        capture_output=True,
        text=True,
        check=True,
    )


def _create_branch_impl(name: str) -> None:
    """Create and check out a new git branch.

    Args:
        name: Branch name to create.
    """
    subprocess.run(
        ["git", "checkout", "-b", name],
        capture_output=True,
        text=True,
        check=True,
    )


def _create_pr_impl(branch: str, title: str, body: str) -> str:
    """Create a GitHub pull request and return its URL.

    Args:
        branch: Head branch name.
        title:  PR title.
        body:   PR description body.

    Returns:
        The URL of the newly created pull request (from ``gh pr create`` stdout).
    """
    result = subprocess.run(
        ["gh", "pr", "create", "--title", title, "--body", body, "--head", branch],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _comment_on_issue_impl(number: int, body: str) -> None:
    """Post a comment on a GitHub issue.

    Args:
        number: GitHub issue number.
        body:   Comment text.
    """
    subprocess.run(
        ["gh", "issue", "comment", str(number), "--body", body],
        capture_output=True,
        text=True,
        check=True,
    )


# ---------------------------------------------------------------------------
# Async @tool handlers (called by ClaudeSDKClient agents via MCP)
# ---------------------------------------------------------------------------


@tool("list_open_issues", "List open GitHub issues not already handled by an agent", {})
async def list_open_issues(args: dict) -> dict:
    """MCP tool: list open, unprocessed GitHub issues."""
    result = _list_open_issues_impl()
    return {"content": [{"type": "text", "text": json.dumps(result)}]}


@tool(
    "claim_issue",
    "Claim a GitHub issue by adding the agent-processing label",
    {"number": int},
)
async def claim_issue(args: dict) -> dict:
    """MCP tool: claim an issue so no other agent picks it up."""
    _claim_issue_impl(int(args["number"]))
    return {"content": [{"type": "text", "text": f"Claimed issue #{args['number']}"}]}


@tool(
    "release_issue",
    "Release a GitHub issue by removing agent-processing and adding outcome label",
    {"number": int, "outcome": str},
)
async def release_issue(args: dict) -> dict:
    """MCP tool: release an issue with a final outcome label."""
    _release_issue_impl(int(args["number"]), str(args["outcome"]))
    return {
        "content": [
            {
                "type": "text",
                "text": f"Released issue #{args['number']} with outcome '{args['outcome']}'",
            }
        ]
    }


@tool("create_branch", "Create and check out a new git branch", {"name": str})
async def create_branch(args: dict) -> dict:
    """MCP tool: create a new git branch."""
    _create_branch_impl(str(args["name"]))
    return {"content": [{"type": "text", "text": f"Created branch '{args['name']}'"}]}


@tool(
    "create_pr",
    "Create a GitHub pull request",
    {"branch": str, "title": str, "body": str},
)
async def create_pr(args: dict) -> dict:
    """MCP tool: create a pull request for a given branch."""
    url = _create_pr_impl(str(args["branch"]), str(args["title"]), str(args["body"]))
    return {"content": [{"type": "text", "text": url}]}


@tool(
    "comment_on_issue",
    "Post a comment on a GitHub issue",
    {"number": int, "body": str},
)
async def comment_on_issue(args: dict) -> dict:
    """MCP tool: add a comment to a GitHub issue."""
    _comment_on_issue_impl(int(args["number"]), str(args["body"]))
    return {
        "content": [
            {"type": "text", "text": f"Commented on issue #{args['number']}"}
        ]
    }


# ---------------------------------------------------------------------------
# MCP server assembly
# ---------------------------------------------------------------------------

github_server = create_sdk_mcp_server(
    name="github",
    version="1.0.0",
    tools=[
        list_open_issues,
        claim_issue,
        release_issue,
        create_branch,
        create_pr,
        comment_on_issue,
    ],
)
