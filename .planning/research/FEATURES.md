# Feature Landscape: GitHub Actions Integration for Autonomous AI Agents

**Domain:** GitHub Actions + gh CLI + Python AI Agent automation
**Researched:** 2026-03-22
**Overall confidence:** HIGH (GitHub Actions and gh CLI are stable, well-documented APIs)

---

## 1. GitHub Actions Workflow YAML Structure (Cron-triggered Python)

### Minimal working structure

```yaml
# .github/workflows/issue-resolver.yml
name: Issue Resolver

on:
  schedule:
    # Every hour during business hours (UTC). Adjust to taste.
    - cron: '0 * * * *'
  workflow_dispatch:  # Allow manual triggers for testing

jobs:
  resolve-issues:
    runs-on: ubuntu-latest
    # Prevent concurrent runs — critical for agents that mutate state
    concurrency:
      group: issue-resolver
      cancel-in-progress: false  # false = queue, not cancel

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          # Required: default GITHUB_TOKEN cannot push without this
          token: ${{ secrets.GITHUB_TOKEN }}
          # Fetch full history for branch operations
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv sync

      - name: Run issue resolver
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}  # gh CLI reads GH_TOKEN
        run: uv run python main.py
```

### Key structural notes

- `concurrency.group` with `cancel-in-progress: false` queues overlapping runs instead of cancelling them. This prevents two agents racing on the same issue set.
- `workflow_dispatch` is essential during development — cron cannot be manually triggered.
- `fetch-depth: 0` gives full git history. Required if the agent creates branches off non-HEAD commits or needs to `git log` history.

---

## 2. Secrets: Passing GITHUB_TOKEN and ANTHROPIC_API_KEY

### GITHUB_TOKEN (built-in)

`GITHUB_TOKEN` is automatically provisioned by GitHub Actions for every run. It does NOT need to be added to repository secrets — it is injected automatically.

```yaml
# Access via secrets context
${{ secrets.GITHUB_TOKEN }}

# Or via the github context (read-only metadata, not the token)
${{ github.token }}
```

**Permissions must be explicitly granted** in the workflow YAML (GitHub's default is restrictive since 2023):

```yaml
permissions:
  contents: write      # Required: push branches, create commits
  issues: write        # Required: comment on issues, add labels
  pull-requests: write # Required: create PRs
```

Place `permissions` at the job level (not workflow level) to follow least-privilege:

```yaml
jobs:
  resolve-issues:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      issues: write
      pull-requests: write
```

### ANTHROPIC_API_KEY (repository secret)

Must be added manually: Repository Settings → Secrets and variables → Actions → New repository secret.

```yaml
env:
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

In Python code, read via `os.environ`:

```python
import os
api_key = os.environ["ANTHROPIC_API_KEY"]
```

The claude-agent-sdk reads `ANTHROPIC_API_KEY` from the environment automatically — no explicit passing needed if the env block is set in the workflow.

### gh CLI authentication

The `gh` CLI authenticates via the `GH_TOKEN` environment variable (preferred over `GITHUB_TOKEN` env var name):

```yaml
env:
  GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

With `GH_TOKEN` set, all `gh` commands authenticate without any `gh auth login` step.

---

## 3. gh CLI Command Reference

### List open issues

```bash
# List open issues as JSON (most useful for programmatic parsing)
gh issue list --state open --json number,title,body,labels,assignees --limit 50

# Filter by label
gh issue list --state open --label "bug" --json number,title,body

# Filter by no assignee (unowned issues)
gh issue list --state open --assignee "" --json number,title,body

# Filter out issues with a specific label (e.g. "agent-processing")
gh issue list --state open --json number,title,labels | \
  jq '[.[] | select(.labels | map(.name) | contains(["agent-processing"]) | not)]'
```

### Add labels to issues

```bash
# Add a label to mark an issue as being processed
gh issue edit 42 --add-label "agent-processing"

# Remove a label after processing completes (or fails)
gh issue edit 42 --remove-label "agent-processing"
```

Labels must exist in the repository first. Create them via:

```bash
gh label create "agent-processing" --color "0075ca" --description "Being processed by AI agent"
gh label create "agent-skip" --color "e4e669" --description "Too complex for auto-resolution"
```

### Comment on issues

```bash
# Add a comment (useful for status updates and skip explanations)
gh issue comment 42 --body "Starting automated analysis of this issue."

# Comment with multi-line body
gh issue comment 42 --body "$(cat <<'EOF'
**Agent Status:** Processing complete

Branch: \`fix/issue-42-null-pointer\`
PR: #87

Confidence: HIGH
EOF
)"
```

### Create branches

The `gh` CLI does not have a `branch create` command. Use `git` directly:

```bash
# Create and push a branch for the issue
git checkout -b "fix/issue-42-null-pointer-exception"
git push origin "fix/issue-42-null-pointer-exception"
```

Branch naming convention for agents: `{type}/issue-{number}-{slug}`

```python
import re

def make_branch_name(issue_number: int, issue_type: str, title: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower())[:40].strip('-')
    return f"{issue_type}/issue-{issue_number}-{slug}"
    # e.g. "fix/issue-42-null-pointer-exception"
```

### Create pull requests

```bash
# Basic PR creation
gh pr create \
  --title "Fix: Null pointer exception in user service (#42)" \
  --body "Closes #42" \
  --base main \
  --head fix/issue-42-null-pointer-exception

# With labels and reviewers
gh pr create \
  --title "Fix: Null pointer exception in user service (#42)" \
  --body "$(cat pr_body.md)" \
  --base main \
  --head fix/issue-42-null-pointer-exception \
  --label "automated-pr" \
  --draft  # Create as draft until tests pass, then mark ready
```

**Critical:** The `--body` flag accepts inline text. For multi-line PR bodies, write to a temp file first and use `--body-file`:

```bash
gh pr create --title "..." --body-file /tmp/pr_body.md --base main
```

### Mark a PR as ready (remove draft status)

```bash
gh pr ready <PR_NUMBER>
# or
gh pr ready <branch-name>
```

### Check if a PR already exists for a branch

```bash
# Returns exit code 0 if PR exists, non-zero otherwise
gh pr view fix/issue-42-null-pointer-exception --json number,state
```

---

## 4. Git Identity Setup in GitHub Actions

GitHub Actions does not configure git identity by default. Every workflow that commits must set `user.email` and `user.name` before committing:

```yaml
- name: Configure git identity
  run: |
    git config --global user.email "github-actions[bot]@users.noreply.github.com"
    git config --global user.name "github-actions[bot]"
```

**Use the official bot identity.** This email and name are recognized by GitHub's UI and show the Actions bot avatar on commits. Do not invent a custom address.

In Python, this can also be done programmatically before running subprocess git commands:

```python
import subprocess

def configure_git():
    subprocess.run(["git", "config", "--global", "user.email",
                    "github-actions[bot]@users.noreply.github.com"], check=True)
    subprocess.run(["git", "config", "--global", "user.name",
                    "github-actions[bot]"], check=True)
```

### Checkout action token vs push authentication

When using `actions/checkout@v4`, the `token` parameter controls what credential is stored for subsequent `git push` calls:

```yaml
- uses: actions/checkout@v4
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
    # This stores the token as the remote credential.
    # git push will work without additional auth setup.
```

Without `token: ${{ secrets.GITHUB_TOKEN }}`, `git push` will fail with authentication errors even if `GITHUB_TOKEN` is in the environment.

---

## 5. Preventing Infinite Loops

This is the most critical operational concern for autonomous agents that create PRs.

### Root cause

A workflow trigger on `push` or `pull_request` events will re-trigger if the agent pushes a branch or creates a PR. Cron-triggered workflows do not have this problem for the trigger itself, but agents may still create recursive work.

### Prevention strategy 1: Use `concurrency` to serialize runs

```yaml
concurrency:
  group: issue-resolver
  cancel-in-progress: false
```

This ensures only one agent run processes issues at a time, preventing two instances from picking up the same issue.

### Prevention strategy 2: Label-based locking (most reliable)

Before processing an issue, add a label. Check for the label before processing:

```python
import json
import subprocess

PROCESSING_LABEL = "agent-processing"
DONE_LABEL = "agent-resolved"
SKIP_LABEL = "agent-skip"

def get_processable_issues() -> list[dict]:
    result = subprocess.run(
        ["gh", "issue", "list", "--state", "open",
         "--json", "number,title,body,labels", "--limit", "50"],
        capture_output=True, text=True, check=True
    )
    issues = json.loads(result.stdout)

    # Exclude issues that already have agent labels
    excluded = {PROCESSING_LABEL, DONE_LABEL, SKIP_LABEL}
    return [
        issue for issue in issues
        if not any(label["name"] in excluded for label in issue["labels"])
    ]

def claim_issue(issue_number: int) -> None:
    """Mark issue as claimed before starting work."""
    subprocess.run(
        ["gh", "issue", "edit", str(issue_number),
         "--add-label", PROCESSING_LABEL],
        check=True
    )

def release_issue(issue_number: int, succeeded: bool) -> None:
    """Release the processing lock and mark final state."""
    final_label = DONE_LABEL if succeeded else SKIP_LABEL
    subprocess.run(
        ["gh", "issue", "edit", str(issue_number),
         "--remove-label", PROCESSING_LABEL,
         "--add-label", final_label],
        check=True
    )
```

### Prevention strategy 3: PR-based deduplication

Before creating a PR, check if one already references the issue:

```bash
# Check open PRs that mention the issue number
gh pr list --state open --json number,title,body | \
  jq '[.[] | select(.body | contains("#42"))]'
```

In Python:

```python
def pr_exists_for_issue(issue_number: int) -> bool:
    result = subprocess.run(
        ["gh", "pr", "list", "--state", "open",
         "--json", "number,title,body"],
        capture_output=True, text=True, check=True
    )
    prs = json.loads(result.stdout)
    marker = f"#{issue_number}"
    return any(marker in (pr.get("body") or "") for pr in prs)
```

### Prevention strategy 4: Branch existence check

```bash
# If the branch already exists, the issue is already being processed
git ls-remote --heads origin fix/issue-42-* | grep -q . && echo "branch exists"
```

```python
def branch_exists(branch_name: str) -> bool:
    result = subprocess.run(
        ["git", "ls-remote", "--heads", "origin", branch_name],
        capture_output=True, text=True
    )
    return bool(result.stdout.strip())
```

### Prevention strategy 5: Filter out PRs and bot-created issues

```python
def is_human_issue(issue: dict) -> bool:
    """Exclude issues created by bots or that are actually PRs."""
    # GitHub PRs also appear in issue list — filter them out
    if "pull_request" in issue:
        return False
    # Exclude issues from known bot accounts
    bot_patterns = ["[bot]", "-bot", "dependabot", "github-actions"]
    author = issue.get("author", {}).get("login", "")
    return not any(p in author.lower() for p in bot_patterns)
```

---

## 6. GitHub API Rate Limiting

### Limits (as of 2025)

| Token type | Requests/hour | GraphQL points/hour |
|------------|---------------|---------------------|
| GITHUB_TOKEN (Actions) | 1,000 | 1,000 |
| Personal Access Token | 5,000 | 5,000 |
| GitHub App token | 15,000 | 15,000 |

**GITHUB_TOKEN in Actions is throttled to 1,000 requests/hour**, which is significantly lower than a PAT. This matters for agents processing many issues.

### gh CLI and rate limits

The `gh` CLI uses the REST API by default. Each `gh issue list`, `gh pr create`, `gh issue comment` consumes one request. A pipeline that processes 10 issues could easily make 50+ API calls.

### Checking current rate limit

```bash
# Returns remaining requests and reset time
gh api rate_limit
```

```python
def get_rate_limit() -> dict:
    result = subprocess.run(
        ["gh", "api", "rate_limit"],
        capture_output=True, text=True, check=True
    )
    data = json.loads(result.stdout)
    return data["resources"]["core"]
    # {"limit": 1000, "used": 42, "remaining": 958, "reset": 1711234567}
```

### Rate limit strategy for agents

1. **Process one issue per run, not all issues.** Pick the oldest unprocessed issue, work on it fully, stop. The next cron run handles the next issue. This bounds API usage per run.

2. **Check rate limit before starting.** If remaining < 100, skip the run and log a warning.

3. **Add delays between API calls.** `time.sleep(0.5)` between `gh` subprocess calls to avoid burst throttling.

4. **Use GraphQL for bulk reads.** One GraphQL query can fetch all issue data (number, title, body, labels, author) in a single request vs. multiple REST calls.

```bash
gh api graphql -f query='
  query($owner: String!, $repo: String!) {
    repository(owner: $owner, name: $repo) {
      issues(states: OPEN, first: 20, orderBy: {field: CREATED_AT, direction: ASC}) {
        nodes {
          number
          title
          body
          labels(first: 10) { nodes { name } }
          author { login }
        }
      }
    }
  }
' -f owner=OWNER -f repo=REPO
```

5. **Cache issue list.** Fetch once at the start of a run, pass in memory rather than re-fetching.

---

## 7. Labeling Issues to Avoid Duplicate Work

### Required labels to create

```bash
# Create all agent-management labels once during repo setup
gh label create "agent-processing" \
  --color "0075ca" \
  --description "Currently being processed by AI agent"

gh label create "agent-resolved" \
  --color "0e8a16" \
  --description "Processed by AI agent — PR created"

gh label create "agent-skip" \
  --color "e4e669" \
  --description "Too complex for auto-resolution — needs human review"

gh label create "agent-failed" \
  --color "d93f0b" \
  --description "Agent attempted but failed — needs human review"
```

### Label lifecycle

```
Issue opened (no agent labels)
  → agent-processing  (agent claims the issue)
  → agent-resolved    (PR created successfully)
  → agent-skip        (complexity too high, agent left a comment)
  → agent-failed      (agent crashed or timed out mid-process)
```

### Ensure labels exist before using them

Labels that don't exist cause `gh issue edit --add-label` to fail silently or error. Check and create at startup:

```python
def ensure_labels_exist(labels: list[dict]) -> None:
    existing = json.loads(
        subprocess.run(["gh", "label", "list", "--json", "name"],
                       capture_output=True, text=True, check=True).stdout
    )
    existing_names = {l["name"] for l in existing}

    for label in labels:
        if label["name"] not in existing_names:
            subprocess.run([
                "gh", "label", "create", label["name"],
                "--color", label["color"],
                "--description", label["description"]
            ], check=True)
```

### Stale lock recovery

If a previous run crashed while `agent-processing` was set, the issue stays locked forever. Add a staleness check:

```python
import subprocess
import json
from datetime import datetime, timezone, timedelta

def find_stale_processing_issues(max_age_hours: int = 2) -> list[int]:
    """Find issues stuck in 'agent-processing' for too long."""
    result = subprocess.run(
        ["gh", "issue", "list", "--state", "open",
         "--label", "agent-processing",
         "--json", "number,updatedAt"],
        capture_output=True, text=True, check=True
    )
    issues = json.loads(result.stdout)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    stale = []
    for issue in issues:
        updated = datetime.fromisoformat(issue["updatedAt"].replace("Z", "+00:00"))
        if updated < cutoff:
            stale.append(issue["number"])
    return stale

def recover_stale_issues(stale_numbers: list[int]) -> None:
    for number in stale_numbers:
        subprocess.run(
            ["gh", "issue", "edit", str(number),
             "--remove-label", "agent-processing",
             "--add-label", "agent-failed"],
            check=True
        )
        subprocess.run(
            ["gh", "issue", "comment", str(number),
             "--body", "Agent run timed out or crashed. Releasing lock for human review."],
            check=True
        )
```

---

## 8. Checkout Action Configuration for Git Operations

### Full checkout configuration for an agent that pushes branches

```yaml
- name: Checkout
  uses: actions/checkout@v4
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
    fetch-depth: 0          # Full history — needed for branch operations
    # ref: main             # Explicit base branch (optional, defaults to triggered ref)
```

### Why `fetch-depth: 0` matters

With the default `fetch-depth: 1` (shallow clone):
- `git log` shows only 1 commit
- `git checkout -b new-branch` may fail if the branch point is not in the shallow history
- `git merge-base` fails
- Branch creation from a specific commit hash fails if that commit is not fetched

Use `fetch-depth: 0` for any agent that needs to create branches, inspect history, or cherry-pick.

### Enabling push without additional auth

With `token: ${{ secrets.GITHUB_TOKEN }}`, the checkout action writes the token into `.git/config` as the credential for `origin`. No additional `git remote set-url` or credential helper is needed:

```bash
# This works after checkout with token:
git push origin fix/issue-42-my-fix
```

Without the `token` parameter, pushing fails with:
```
remote: Permission to owner/repo.git denied to github-actions[bot].
```

### Full workflow step sequence for agent commits

```yaml
- uses: actions/checkout@v4
  with:
    token: ${{ secrets.GITHUB_TOKEN }}
    fetch-depth: 0

- name: Configure git identity
  run: |
    git config --global user.email "github-actions[bot]@users.noreply.github.com"
    git config --global user.name "github-actions[bot]"

- name: Run agent
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: uv run python main.py
  # Agent internally runs:
  #   git checkout -b fix/issue-42-...
  #   git add -A && git commit -m "..."
  #   git push origin fix/issue-42-...
  #   gh pr create ...
```

---

## Table Stakes Features (Must Have)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Cron-triggered execution | Core automation requirement | Low | Standard GitHub Actions pattern |
| GITHUB_TOKEN authentication | Required for all GitHub operations | Low | Built-in, no secret management needed |
| Issue label locking | Prevents duplicate processing | Medium | Requires label pre-creation |
| Git identity configuration | Required for any commit | Low | Two-line config step |
| Branch-per-issue strategy | Isolates changes per issue | Low | Standard git workflow |
| PR creation with issue link | Closes issue when PR merges | Low | "Closes #N" in PR body |
| Concurrency control | Prevents race conditions | Low | Single YAML field |

## Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Stale lock recovery | Prevents permanently stuck issues | Medium | Time-based check at run start |
| Rate limit preflight | Prevents failed runs mid-processing | Low | One API call before starting |
| Draft PR workflow | Human review before merge | Low | `--draft` flag + `gh pr ready` |
| GraphQL bulk fetch | 1 API call vs N calls for issue list | Medium | Saves rate limit budget |
| Per-issue timeout | Prevents agent from running forever | Medium | `asyncio.timeout` or subprocess timeout |

## Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Auto-merge PRs | Bypasses human review, high risk | Create PR as draft, require approval |
| Processing all issues in one run | API rate limit exhaustion, timeout | Process one issue per run |
| Using PAT instead of GITHUB_TOKEN | Secret management burden | GITHUB_TOKEN is sufficient with correct permissions |
| `git push --force` | Destroys history, dangerous in automation | Never force-push; create new branches |
| Catching all exceptions silently | Hides bugs, issues appear processed | Always release label lock on exception |

## Feature Dependencies

```
Labels pre-created → Issue claiming (label-based locking)
Issue claiming → Duplicate prevention
Branch exists check → Branch creation
Git identity configured → git commit
Checkout with token → git push
git push → gh pr create
gh pr create → Issue close on merge (via "Closes #N")
```

## MVP Recommendation

Prioritize for initial implementation:

1. Cron workflow YAML with correct `permissions` and `concurrency`
2. Git identity configuration step
3. Label-based issue locking (claim before work, release after)
4. Single-issue-per-run processing (prevents rate limit exhaustion)
5. Branch naming convention + PR creation with `Closes #N` body

Defer:
- GraphQL bulk fetch (REST is fine for low volume)
- Draft PR workflow (can add later without architectural changes)
- Stale lock recovery (add in a follow-up once basic flow is working)

---

## Sources

- GitHub Actions documentation (training data, HIGH confidence for stable features)
- gh CLI documentation (training data, HIGH confidence — stable CLI since 2021)
- GitHub API rate limiting: 1,000 req/hour for GITHUB_TOKEN in Actions (HIGH confidence, documented behavior)
- `actions/checkout@v4` token parameter behavior (HIGH confidence — widely used, stable)
- `concurrency` field behavior (HIGH confidence — introduced 2021, stable)
- Bot email `github-actions[bot]@users.noreply.github.com` (HIGH confidence — official GitHub convention)
