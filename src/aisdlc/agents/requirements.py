"""What the product analyst concluded should be built, in the fields the glossary lists.

The field names are not chosen here. `docs/domain-glossary.md` already fixed the contents
of this artifact — requirements, acceptance criteria, ambiguities — and the agent's name is
the contract, so a field that drifts from that table is a broken promise rather than a rename.
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator

from aisdlc.agents.a_value_that_says_something import a_value_that_says_something, as_absence
from aisdlc.agents.requirements_answer import AnAmbiguity

THE_PRODUCT_ANALYST_AGENT = "aisdlc-po-analyze"


class EmptyRequirementsError(Exception):
    """The rule is in `Requirements`, and this is the only thing that may say it broke.

    Raised rather than returned as a Pydantic `ValidationError`, for the reason
    `EmptyDiscoveryReportError` gives: the caller can ask a model to fix an answer that said
    nothing, and cannot do anything of the sort with a field of the wrong shape.
    """


class Requirements(BaseModel):
    """What a product analyst proposes, in the words a person would approve or refuse.

    The three collections are the glossary's, kept flat and unpaired. Acceptance criteria
    are not hung off the requirement they verify, because `PullRequestRequest` is the
    artifact that traces a change back to what it was for, and pairing them here would
    build the same traceability twice — in the artifact where nobody asked for it, and in
    the one where §10 does.
    """

    requirements: list[str] = []
    acceptance_criteria: list[str] = []
    ambiguities: list[AnAmbiguity] = []

    def everything_it_says(self) -> tuple[object, ...]:
        """Every field's value, in the order the glossary lists them."""
        return (
            self.requirements,
            self.acceptance_criteria,
            self.ambiguities,
        )

    @model_validator(mode="after")
    def a_field_that_said_nothing_is_absence(self) -> Requirements:
        """A field holding whitespace becomes the absence this system already represents.

        **The same rule as the other two artifacts, and it is here because the rule is the
        rule.** A real model answered the QA plan with a `test_strategy` of one space, and the
        emptiness check asked whether the *plan* said anything rather than whether each field
        did — so a collection of real requirements carried a blank acceptance criterion into a
        gate. Fixing that one shape would have been a third fix in this repository made where
        the bug was found rather than where the rule is.
        """
        for a_field in type(self).model_fields:
            setattr(self, a_field, as_absence(getattr(self, a_field)))
        return self

    @model_validator(mode="after")
    def it_must_propose_something(self) -> Requirements:
        """At least one collection must carry something, or this is a fault and not a proposal.

        "At least one" and not "all of them", because a repository can be unambiguous — and
        then the honest artifact says so with two empty lists rather than inventing an
        ambiguity to fill the third. A rule demanding every field would only ever be
        satisfied by a proposal that guessed.
        """
        if not any(a_value_that_says_something(value) for value in self.everything_it_says()):
            raise EmptyRequirementsError(
                f"{THE_PRODUCT_ANALYST_AGENT} proposed nothing at all about "
                f"{'the project'}: every field was empty. That is a fault rather than an "
                "artifact, because a person cannot tell an empty proposal from a real one "
                "by looking at it — and a blank page is the one thing a run may not put in "
                "front of the person who commissioned the work."
            )

        return self
