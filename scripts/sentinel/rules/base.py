"""Abstract rule interface + auto-registry.

Port of lib/rules/base.rb. Every concrete rule subclasses ``Rule`` and
sets class attributes ``name``, ``description``, ``severity`` plus a
``check(workflow)`` method. Concrete subclasses self-register via
``__init_subclass__`` so the engine and policy validator can enumerate
every rule without a hand-maintained import list.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sentinel.finding import Finding

if TYPE_CHECKING:
    from sentinel.workflow import Workflow


class Rule:
    """Base class for all detectors. Subclasses set name/description/severity."""

    name: str = ""
    description: str = ""
    severity: str = ""

    # Every concrete subclass appends itself here at import time.
    registry: list[type["Rule"]] = []

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Only register concrete rules — those that define their own `name`.
        if cls.__dict__.get("name"):
            Rule.registry.append(cls)

    def check(self, workflow: "Workflow") -> list[Finding]:
        """Return findings for one workflow. Must be overridden."""
        raise NotImplementedError

    def finding(
        self,
        workflow: "Workflow",
        *,
        line: int,
        code: str | None = None,
        message: str | None = None,
        fix: str | None = None,
    ) -> Finding:
        """Construct a Finding, defaulting code to the line content and message
        to the rule description (mirrors the Ruby ``finding`` helper)."""
        if code is None:
            lc = workflow.line_content(line)
            code = lc.strip() if lc else None
        return Finding(
            rule=self.name,
            severity=self.severity,
            file=workflow.filename,
            line=line,
            code=code,
            message=message if message is not None else self.description,
            fix=fix,
        )
