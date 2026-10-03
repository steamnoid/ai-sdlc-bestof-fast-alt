"""That a discovery report saying nothing at all is refused, and says why that is a fault.

**This is the last of four refusals the package raises with no test naming them**, and the only
one with no run behind it - which makes it the one worth reading rather than the one worth
trusting. Measured: every `*Error` class in `src/aisdlc/agents/` against every file in `tests/`.

**The rule is a model validator, so the test builds the model and not the exception.** A test that
constructed `EmptyDiscoveryReportError("...")` would assert that the constructor stores a string,
which is not the rule: **the rule is that a report with every field empty cannot be built at all**,
and only a validator can prove that.

**And the reason is asserted, because the reason is the half that is a judgement.** The refusal
says *a person cannot tell an empty report from a real one by looking at it* - which is the
sentence that makes it a fault to be told about rather than an artifact to be tolerated. **A refusal
that only said "empty" would be indistinguishable from the model having described a repository that
genuinely has nothing**, which is the outcome the neighbouring rule explicitly protects: *absence is
representable, and a rule demanding every field would only ever be satisfied by a report that
guesses*.

**So the two halves of this file's rules are opposites and are both here.** Every field empty is
refused; **no** single field empty is refused, because a repository with no CI has nothing to say
about CI. **Without the second test a reader cannot tell which of the two rules this file holds.**
"""

from __future__ import annotations

import pytest

from aisdlc.agents.discovery_report import DiscoveryReport, EmptyDiscoveryReportError


def test_a_report_saying_nothing_at_all_cannot_be_built() -> None:
    """Every field empty is refused, and the refusal says why that is a fault.

    **No arguments at all**, because a report where nothing was said is the shape, and any value
    in any field is what the validator is looking for.
    """
    with pytest.raises(EmptyDiscoveryReportError) as it_raised:
        DiscoveryReport()

    the_refusal = str(it_raised.value)

    assert "cannot tell" in the_refusal, (
        "the refusal does not say that a person cannot tell an empty report from a real one, which "
        "is the whole reason this is a fault rather than an artifact. It says: " f"{the_refusal}"
    )
    assert "aisdlc-discover" in the_refusal, (
        f"the refusal does not name the agent whose answer was empty, so a reader has to work out "
        f"which stage produced it. It says: {the_refusal}"
    )


def test_a_report_saying_one_thing_is_built() -> None:
    """The opposite rule, and the reason the first one is not a demand that every field be filled.

    **This is the half that would be lost if only the refusal were tested.** A validator that
    refused any empty field would be satisfied only by a report that guesses - which is precisely
    what `evidence_files` and `ci_system` are shaped so a model cannot do.
    """
    the_report = DiscoveryReport(ci_system="none")

    assert the_report.ci_system == "none", (
        "a report that said only that the repository has no CI was refused, so the file's rule is "
        "that every field must be filled - and a repository with no CI has nothing to say about CI"
    )
