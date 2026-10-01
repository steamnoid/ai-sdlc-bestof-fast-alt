"""Whether a value carries anything a person could read, and what to write when it does not.

Two rules with one cause, and the cause is a real model rather than a theoretical one. Three
artifacts — `DiscoveryReport`, `Requirements` and `QaPlan` — each ask "does this say
something?", and each answered with `any()` over the raw values, which is `True` for a string
of spaces. A QA plan whose entire test strategy was `" "` passed the rule, and a run would
have put it in front of a person to approve.

So the first rule is not "is this value truthy" but "is there anything in it once whitespace
is gone", and the two are different questions. **The second rule is what came second, and it
is the half the first was mistaken for:** detecting emptiness correctly is not the same as
acting on it, and a plan whose *scenarios* were real passed the check carrying a strategy
that was a single space. `as_absence` is that half.

Both live in one module because a fourth artifact would otherwise arrive with a fourth
`any()`, which is how the first three all got it.
"""

from __future__ import annotations

from collections.abc import Iterable


def a_value_that_says_something(value: object) -> bool:
    """Whether there is anything in this value a person could read.

    Four kinds of value, four answers, and each is a value the domain actually uses:

    * `None` says nothing. It is absence, which this system represents deliberately —
      `DiscoveryReport.build_system` is `str | None` because a repository with no CI has
      nothing to say about CI — and absence is not emptiness.
    * text says something when a non-whitespace character is left after stripping.
    * a list says something when any one of its entries says something, so one real
      requirement among three blank strings is a run with one requirement.
    * anything else is said by the model rather than the domain, and is not guessed at: a
      report must not become approvable because a field holds a truthy object nobody read.
    """
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    if isinstance(value, Iterable):
        return any(a_value_that_says_something(entry) for entry in value)

    return False


def as_absence(value: object) -> object:
    """This value, with anything that said nothing written as this system's absence.

    **Added because detecting emptiness was never the half that was missing.** A real model
    returned the QA plan's `test_strategy` as a single space. `a_value_that_says_something`
    already answered correctly — a string of whitespace says nothing — and the plan still
    passed, because the question the artifact asks is whether it says *anything at all* and
    the scenarios were real. So the blank strategy rode into a `QaPlan` that a gate presents
    to a person, where a field holding `" "` is indistinguishable from a field holding a
    strategy.

    **A model that is free to answer badly is the input; a gate is the output.** Every
    artifact here is validated rather than cast, and validating a shape is not the same as
    reading what it says. The gate presents whatever the model wrote, so a field that said
    nothing has to be absent by the time the artifact exists — and the artifact is the one
    place that knows both the rule and the field.

    **Absence is the vocabulary already in use, not a new one.** `""` for a field this
    system means "nothing was said here", `None` where the domain models a thing that may
    not exist (`build_system` for a repository with no build system), and an empty list for
    a collection. A field of whitespace is none of those and is read as none of them, which
    is what a person looking at a card cannot tell otherwise.

    **Not refused, and that is deliberate.** A repository with nothing ambiguous about it
    has no edge cases to name, and the honest artifact says so with three filled fields and
    one empty one. Refusing the whole artifact over one blank field would force a model to
    invent a boundary condition to fill a list — the guess the emptiness rule exists to
    prevent. A blank becomes absent; an artifact that is *entirely* blank is still a fault,
    and that is the validator each of these models already carries.

    **A list keeps the entries that said something, in the order they were given.** Order is
    a model's reasoning and a card reads in it, and dropping a blank from the middle of a
    list of scenarios leaves the reader with no way to know one had been dropped. A blank
    entry is not a scenario, so it is not one here either.
    """
    if value is None:
        return None

    if isinstance(value, str):
        return value if value.strip() else ""

    if isinstance(value, list):
        return [
            as_absence(entry) for entry in value if a_value_that_says_something(entry)
        ]

    return value
