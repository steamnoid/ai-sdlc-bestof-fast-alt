"""What the development planning agent produced, in the four fields `§10` lists.

The field names are not chosen here. `docs/domain-glossary.md` fixes the contents of this
artifact, and the agent's name is the contract, so a field that drifts from that table is a
broken promise rather than a rename. There is no separate shape for the model's answer, the
way `DiscoveryAnswer` exists beside `DiscoveryReport`, because that split exists to keep a
derived field away from a model: a link a reviewer clicks is derived from
`owner`/`name`/`branch`/`path` and must not be asked for, and nothing here is derived. A
second type for the same four lists would be a shape with no reason to differ, and the
model is asked for this one directly.

**`tests_to_add` is the one list whose paths are not checked against the clone.** A test
that does not exist yet is the whole point of it. `files_to_change` is the opposite: every
one of those is a file of the repository as it stands, and `plan_the_change` proves it
before a plan exists.
"""

from __future__ import annotations

from pydantic import BaseModel, model_validator

from aisdlc.agents.a_value_that_says_something import as_absence


class EmptyPlanError(Exception):
    """The rule is in `ImplementationPlan`, and this is the only thing that may say it broke.

    Raised rather than returned as a Pydantic `ValidationError`, for the reason
    `EmptyDiscoveryReportError` is: the caller has something to do about this that it
    cannot do about a malformed field. Five empty lists is a fault to be told about in our
    own words, because a person cannot tell it from a real plan by looking at it — and the
    next thing that happens to a real plan is that a person approves it.
    """


class ImplementationPlan(BaseModel):
    """Which files change, which tests are added, what is depended on, what must migrate."""

    files_to_change: list[str] = []
    files_to_add: list[str] = []
    tests_to_add: list[str] = []
    dependencies: list[str] = []
    migrations: list[str] = []

    def everything_it_says(self) -> tuple[object, ...]:
        """Every field's value, in the order the glossary lists them.

        **All five, and it read four until a real plan said otherwise.** `files_to_add` was added
        to this artifact for a real run that asked for an endpoint, and this method was never
        extended — so a plan whose whole change is a new file, which is the ordinary shape of
        *add an endpoint*, was refused as empty by a rule that could not see the one thing it
        had named. **A guard that reads some of a type's fields is a guard over part of the
        type**, and the part that was missing is the part a new kind of plan arrives in.
        """
        return (
            self.files_to_change,
            self.files_to_add,
            self.tests_to_add,
            self.dependencies,
            self.migrations,
        )

    @model_validator(mode="after")
    def a_field_that_said_nothing_is_absence(self) -> ImplementationPlan:
        """A field holding whitespace becomes the absence this system already represents.

        **The same rule as the other three artifacts that carry a model's answer, and it is here
        for their reason.** A real model answered a QA plan with a `test_strategy` of one space,
        and the emptiness check asked whether the *plan* said anything rather than whether each
        field did — so real scenarios carried a blank strategy into a gate. A plan here is the
        same shape: a list field the model filled with `["  "]` reads as a plan naming a file
        called `"  "`, and a delivery would then try to write it.
        """
        for a_field in type(self).model_fields:
            setattr(self, a_field, as_absence(getattr(self, a_field)))
        return self

    @model_validator(mode="after")
    def it_must_say_something_to_do(self) -> ImplementationPlan:
        """At least one of the five lists must name something, or this is a fault.

        "At least one" and not "all of them", because a plan that adds a dependency and
        changes no file is a plan — that is what `dependencies` is for — and a plan whose whole
        content is a new file is a plan for the same reason. A rule demanding every field would
        be satisfied only by a plan that guesses. What is refused is the plan with nothing in it,
        which is what a model returns when it did not do the reading, and which is
        indistinguishable from a real plan to a person approving it.

        **The refusal names every field, and it is built from the fields rather than written out,
        for the reason this method was wrong once.** It listed four things a plan can be empty of
        and the plan had named the fifth — so a reader who watched a plan be refused went looking
        in four places and found nothing wrong in any of them. A message that enumerates a subset
        of the reasons sends the reader to the wrong ones, and the fix is a message derived from
        the same list the rule is.
        """
        if not any(self.everything_it_says()):
            raise EmptyPlanError(
                f"The planning agent returned a plan that is empty in every one of its "
                f"{len(type(self).model_fields)} fields "
                f"({', '.join(type(self).model_fields)}). That is a fault rather than a plan, "
                "because the next thing that happens to a plan is that a person is asked to "
                "approve it, and a person cannot tell an empty plan from a real one by looking "
                "at it."
            )

        return self
