"""JSON formatter. Port of lib/formatter/json.rb.

Internal `import json as _json` is an absolute import — it resolves to the
stdlib module, never to this sibling module.
"""

from __future__ import annotations

import json as _json

from sentinel.finding import SEVERITIES, Finding


class Json:
    """Pretty-printed JSON report with a per-severity summary block."""

    def format(self, *, repo: str, workflow_count: int, findings: list[Finding]) -> str:
        """Serialize {repo, workflows, findings[], summary{}} as pretty JSON."""
        summary = {s: sum(1 for f in findings if f.severity == s) for s in SEVERITIES}
        return _json.dumps(
            {
                "repo": repo,
                "workflows": workflow_count,
                "findings": [f.to_dict() for f in sorted(findings)],
                "summary": summary,
            },
            indent=2,
        )
