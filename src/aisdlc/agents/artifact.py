"""The artifact a run puts in front of a person, as a closed set of eight names.

**One concept, one name, and this is where it lives.** Eight node modules each declared the name
of the thing they produce, and the router imported all eight to spell the same eight strings a
ninth time — so an artifact had nine names in nine files and no single place a reader could look
for what the pipeline can produce. **The artifact a run begins with alone was written in four
files**, and what every one of the four was for is what a run presents first — which is exactly
the value a person is most likely to rename and least likely to check twice.

**The set is closed, and that is the property rather than a tidiness.** The state is a `TypedDict`,
so it is not validated when a node writes it — nothing at runtime would refuse
`"DiscoveryRepotr"`. What refuses it is this type, which `mypy` reads on every push: a module that
presents a name that is not here does not compile. **That is the difference between a failure at a
gate and a failure before the run started**, and it is worth a `str` becoming an enum to get.

**The names are the class names, because those are the names the artifacts have everywhere else.**
`Requirements`, `QaPlan`, `VerificationReport` are what the modules, the docstrings and the
artefact types on disk already call them; `PULL_REQUEST_REQUEST` is the one that reads as a noun
phrase because the artifact is a request and not a report, and it says so where it is declared.

**The set does not carry the pipeline.** Which artifact leads to which is `router.py`, and a
member added here with no route there is an artifact a run can produce and nobody can route — so
the two are asserted to agree rather than either one being trusted.
"""

from __future__ import annotations

from enum import StrEnum


class Artifact(StrEnum):
    """What a run puts in front of a person to rule on, and nothing else it ever presents."""

    DISCOVERY_REPORT = "DiscoveryReport"
    REQUIREMENTS = "Requirements"
    QA_PLAN = "QaPlan"
    ARCHITECTURE_REPORT = "ArchitectureReport"
    SECURITY_REPORT = "SecurityReport"
    IMPLEMENTATION_PLAN = "ImplementationPlan"
    VERIFICATION_REPORT = "VerificationReport"

    @classmethod
    def _missing_(cls, value: object) -> Artifact:
        """Refuse a name this pipeline does not produce, and hand back the eight that it does.

        **The message lists the set, and that is the whole of what this adds.** Python's own
        message is *"'DiscoveryRepotr' is not a valid Artifact"*, which says what is wrong and
        nothing about what to write instead — so a writer who misspelled a name has to go and
        find the set before trying again. **Every other refusal in this package names what is
        possible**, because that is what turns a wrong guess into a right one inside the same
        sentence.

        **Raised from here rather than returned as `None`**, which is how Python spells the
        default refusal: returning `None` produces the message this overrides, and raising is the
        only way to change it.
        """
        what_there_is = ", ".join(sorted(an_artifact.value for an_artifact in cls))
        raise ValueError(
            f"{value!r} is not an artifact this pipeline presents. These are the eight, and they "
            f"are the only ones: {what_there_is}"
        )

    PULL_REQUEST_REQUEST = "PullRequestRequest"
    """What the delivery produces, and the eighth gate.

    **A request and not a report, and that is the artifact's own type's name.** `deliver_node`
    builds a `PullRequestRequest` and presents it, so the value is that class's name rather than
    something phrased to fit the other seven — and the eighth gate is the one §10 is about, since a
    pull request is created only after a person has approved it.
    """
