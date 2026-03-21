"""utakata-agent entry point.

Dispatches to workflow run.py modules.
Currently supports: issue-resolver workflow.
"""
from issue_resolver.run import run


def main() -> None:
    run()


if __name__ == "__main__":
    main()
