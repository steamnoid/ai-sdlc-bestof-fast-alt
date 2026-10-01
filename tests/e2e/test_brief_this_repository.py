"""A repository briefs itself, against a real model and a real clone.

**This is the other half of the product and the only stage whose question nothing in the
deployment supplied.** Every other agent in this system answers a question a person asked — *add
a health endpoint*, *check this for security risk* — and each one is told what to look at. This
one is handed a repository and asked what it should be given, so the answer is derived from
nothing the operator wrote. **A model that has not read a repository's files will invent work
for it, and inventing work is this stage's ordinary failure** — which is why the assertion here
is about grounding and not about whether the proposals were any good.

**Grounding is checkable, and the check is the whole of this file.** Every path an opportunity
cites is proved against the clone before the report is returned, and the proof is what separates
a briefing from a list of plausible sentences: the first real briefing this system asked for
proposed `src/App.jsx` in all four opportunities, in a repository with no `src/` at all,
describing a React application the repository is not. **A briefing reaches a person as a list of
tickets, and a ticket citing a link that resolves to nothing is work somebody else pays for** —
so this test re-looks-up every path on the file system rather than trusting the node that proved
them, because a test that trusted the node would pass on a node whose check was commented out.

**The other half of the claim is that an opportunity says all six of its things.** `AnOpportunity`
refuses a blank in five of them and an empty citation list in the sixth, so reaching these
assertions is itself evidence — but only if a briefing proposed something, and **a briefing that
found nothing is a result and not a failure.** So the test that reads the opportunities skips
loudly and says why when the list is empty, rather than reporting a green run beside assertions
that never ran. The tests that hold on an empty briefing — what the repository is, what could
not be settled, and the judgement beside the report — are the ones that do not need an
opportunity, and they are what a run over a repository in good shape is judged on.

**The duplicate refusal is not re-proved here.** `what_is_already_tracked` is passed empty and
`tests/test_work_already_tracked_is_not_proposed_again.py` holds the rule that a briefing shows
the repository's open issues and that filing refuses a duplicate before anything is opened. A
file whose job is to isolate one stage should not re-prove a rule another file owns, and this
one would be proving it about a stand-in list rather than about a real repository's issues.
"""

from __future__ import annotations

import pytest

from aisdlc.agents.brief_this_repository import (
    WHAT_EACH_OPPORTUNITY_MAY_NAME,
    brief_this_repository,
    what_the_clone_holds,
)
from aisdlc.agents.what_an_agent_judged import NOTHING_WAS_FOUND, NOTHING_WAS_UNSETTLED
from aisdlc.creative.an_opportunity import AnOpportunity
from aisdlc.creative.the_opportunities_this_repository_offers import (
    TheOpportunitiesThisRepositoryOffers,
)
from aisdlc.domain.repository import Repository
from aisdlc.llm.model_provider import LlmProvider
from aisdlc.tools.github_clone_repository import ClonedRepository

pytestmark = pytest.mark.e2e

HOW_MANY_OPPORTUNITIES_WERE_ASKED_FOR = 5
"""The ceiling the deployment's setting would have given this stage, stated rather than read.

**Stated here because a briefing's count is a ceiling and not a target**, and the artifact says
an empty list is a result — so a test that read the deployment's setting would be asserting
about a number this file's own question can change. What is checked is the contract; the count
is the deployment's business.
"""


@pytest.fixture(scope="module")
def a_real_briefing(
    the_cloned_repository: ClonedRepository,
    the_repository: Repository,
    the_model_for,
    request,
) -> TheOpportunitiesThisRepositoryOffers:
    """One real briefing of one real clone, shared by every assertion about it.

    **Module scope, because a clone and a model call are the expensive parts and the four
    assertions below are four contracts about *one* briefing.** Asserting separately about
    separate runs would only prove that the model proposes something different each time, which
    is true and is not what this file is for.

    **`what_is_already_tracked` is empty and the reason is in the module docstring**: the rule
    about what is already filed belongs to another file, which holds it against a real
    repository's issues. The provider is `request.param` and the tests parametrise it indirectly,
    so a deployment configured for one provider *skips* the others with the reason printed.
    """
    return brief_this_repository(
        the_cloned_repository,
        the_repository,
        the_model_for(request.param),
        HOW_MANY_OPPORTUNITIES_WERE_ASKED_FOR,
        what_is_already_tracked=(),
    )


def _the_opportunities_a_person_would_read(
    the_briefing: TheOpportunitiesThisRepositoryOffers,
) -> list[AnOpportunity]:
    """The opportunities in this briefing, or a loud skip saying there were none.

    **A skip that prints its reason rather than a green run.** The artifact treats an empty list
    as a true sentence about a repository, so there is nothing to fail here — but a test that
    looped over nothing and reported passed would be claiming to have checked six sentences per
    opportunity when it checked none, and this repository's own rule is that a green run which
    never asked is a lie told with a tick.
    """
    if not the_briefing.opportunities:
        pytest.skip(
            "this briefing proposed no opportunities, which the artifact says is a result and "
            "not a failure — so the claims about what an opportunity says were not reached. "
            "This is printed rather than hidden because a green run beside assertions that "
            "never ran is the outcome this tier exists to prevent."
        )
    return the_briefing.opportunities


@pytest.mark.parametrize("a_real_briefing", list(LlmProvider), indirect=True)
def test_the_report_is_the_artifact_about_the_repository_that_was_briefed(
    a_real_briefing: TheOpportunitiesThisRepositoryOffers,
    the_repository: Repository,
) -> None:
    """The report is the type a person rules on, and it is about the repository that was read.

    **Two claims, and the second is the one a chain can quietly get wrong.** The node is handed
    a clone and a `Repository` and is free to disagree with them; a report about a different
    repository would propose work on somebody's project, and every path in it would be
    unopenable. Asserted on the artifact rather than on the prompt, so a model that ignored the
    question and returned the wrong repository is caught on the output.
    """
    assert isinstance(a_real_briefing, TheOpportunitiesThisRepositoryOffers), (
        f"the stage answered with {type(a_real_briefing).__name__} rather than the artifact a "
        "person picks opportunities from, so nothing downstream can rely on which fields it "
        "carries"
    )
    assert a_real_briefing.about == the_repository, (
        f"the briefing is about {a_real_briefing.about.address} and the repository that was "
        f"cloned and read is {the_repository.address}. Every citation in the report is relative "
        "to the clone, so a report about another repository is a list of work whose evidence "
        "resolves to nothing"
    )


@pytest.mark.parametrize("a_real_briefing", list(LlmProvider), indirect=True)
def test_every_path_every_opportunity_cites_is_a_file_the_clone_really_holds(
    a_real_briefing: TheOpportunitiesThisRepositoryOffers,
    the_cloned_repository: ClonedRepository,
) -> None:
    """Every citation is a real file, and it is the repository's own rather than a dependency's.

    **Looked up on the file system rather than trusted from the node, and that is the whole
    point of the test.** `proving_what_they_cite` checks the model's own field and fills the
    other one from it, so `evidence_files` is the answer to a question the model was never asked
    — which is what makes the split the check rather than a second copy of the claim. Asserting
    the model's paths against the disk is an independent second check, and it is the one that
    would fail if the node's own check were ever weakened to a warning.

    **And `evidence_files` is asserted equal to what the model wrote, so an empty one fails.**
    The check inside the node is invisible from here: a node that skipped `proving_what_they_cite`
    entirely would return a report whose `evidence_files` is the default empty list, and every
    other assertion in this file would pass. An opportunity whose evidence is empty has had
    nothing proved about it.
    """
    the_repository_paths = set(what_the_clone_holds(the_cloned_repository))

    for an_opportunity in a_real_briefing.opportunities:
        assert an_opportunity.evidence_files == an_opportunity.the_files_that_show_this, (
            f"an opportunity cites {an_opportunity.the_files_that_show_this} and its proved "
            f"evidence is {an_opportunity.evidence_files}. The model writes one field and the "
            "node fills the other from it after checking it against the clone, so the second "
            "being empty means nothing was proved — and the first is a question only the node "
            "can answer"
        )

        for a_cited_path in an_opportunity.the_files_that_show_this:
            assert (the_cloned_repository.path / a_cited_path).is_file(), (
                f"{a_cited_path!r} is cited as showing why this repository should be given this "
                f"work, and the clone does not hold it. A real briefing of a real repository "
                "proposed `src/App.jsx` in all four opportunities, in a repository with no "
                "`src/` at all — and a citation a reader cannot open is a ticket somebody else "
                "pays for"
            )
            assert a_cited_path in the_repository_paths, (
                f"{a_cited_path!r} is a real file in the clone but is not one of the "
                "repository's own paths — it is inside a directory holding somebody else's code, "
                "or inside git's own. A briefing built on one of those is a briefing about a "
                "dependency or about the clone rather than about the project"
            )


@pytest.mark.parametrize("a_real_briefing", list(LlmProvider), indirect=True)
def test_an_opportunity_says_all_six_of_the_things_it_is_asked_to_say(
    a_real_briefing: TheOpportunitiesThisRepositoryOffers,
    the_cloned_repository: ClonedRepository,
    the_placeholders: frozenset[str],
) -> None:
    """Each of the six fields says something, in a card a person is about to choose from.

    **The six are read out of production rather than written here.** The prompt names them and
    the artifact validates them, and a list typed into this file would be a fourth copy of the
    same six — so this asks the node's own tuple what an opportunity may name, and a field added
    to or removed from that tuple is a field this test follows without being edited.

    **Reaching this assertion is itself half the evidence.** `AnOpportunity` refuses a blank in
    five of them and an empty citation list in the sixth, so a report holding one opportunity
    with all six filled is a report where the model wrote sentences rather than a shape — which
    is the failure this system's first real briefing produced, in a single opportunity with
    every sentence empty. Placeholder text is the version of that which reads as an answer.
    """
    for an_opportunity in _the_opportunities_a_person_would_read(a_real_briefing):
        for a_field in WHAT_EACH_OPPORTUNITY_MAY_NAME:
            said = getattr(an_opportunity, a_field)

            if isinstance(said, list):
                assert said, (
                    f"{a_field} is empty on an opportunity proposing "
                    f"{an_opportunity.what_could_be_done!r}. This is the field the whole type "
                    "exists for: a claim nobody can open is not a claim, and this one is going "
                    "to become a work item a person is asked to rule on"
                )
                said_values: tuple[object, ...] = tuple(said)
            else:
                said_values = (said,)

            for one_of_them in said_values:
                assert str(one_of_them).strip(), (
                    f"{a_field} holds {one_of_them!r} on an opportunity proposing "
                    f"{an_opportunity.what_could_be_done!r}. That is neither an answer nor an "
                    "absence — a person choosing this opportunity is being asked to rule on a "
                    "field with a blank in it, and a blank is indistinguishable from a short "
                    "answer on a card"
                )
                assert str(one_of_them).strip().lower() not in the_placeholders, (
                    f"{one_of_them!r} is placeholder text in {a_field}, which means the model "
                    "returned a shape rather than a proposal somebody could choose"
                )


@pytest.mark.parametrize("a_real_briefing", list(LlmProvider), indirect=True)
def test_the_briefing_says_what_the_repository_is_and_what_it_could_not_settle(
    a_real_briefing: TheOpportunitiesThisRepositoryOffers,
    the_placeholders: frozenset[str],
) -> None:
    """One sentence about the repository, a list of doubts, and a judgement the model wrote.

    **The one sentence may not be blank while the opportunity list may be empty, and the
    difference is the whole distinction between the two.** "This repository has nothing worth
    doing" is a true sentence and the most useful thing a briefing can conclude; a briefing that
    does not say what the repository *is* is a model that filled a shape without reading
    anything, and the two are indistinguishable from a board unless one of them is refused.

    **The judgement is asserted not to be the type's own default, which is what makes it
    non-vacuous.** `agent_judgement` falls back to two sentences saying this run asked and the
    answer carried no finding worth naming — so a test checking only that its fields are
    non-empty would pass on a model that never judged anything, and a board would show a
    briefing that had one in it. Both sentinels are named out of the module that holds them, so
    a report still carrying one was judged by nobody.


    **The doubts are a list, and each entry is only asked to be there.** An empty list is an
    answer here: a briefing that settled everything would be a briefing with nothing said about
    its own limits, and this system has an analyst that admitted a question it could not answer
    rather than a plan written about a cleaner problem than the one it was given. A blank *entry*
    is refused and nothing more is asked of the words — "none" is what a briefing writes when it
    settled everything, and a test that called that a placeholder would be failing a model for
    answering.
    """
    assert a_real_briefing.what_this_repository_is.strip(), (
        "the briefing proposes nothing about what this repository *is*, which is a model that "
        "filled a shape without reading anything. The opportunity list may be empty and this "
        "sentence may not, because an empty list is a finding and a blank description is a gap"
    )
    assert a_real_briefing.what_this_repository_is.strip().lower() not in the_placeholders, (
        f"{a_real_briefing.what_this_repository_is!r} is placeholder text, which means the model "
        "returned a shape rather than a description of a repository somebody is being asked to "
        "fund work on"
    )

    assert isinstance(a_real_briefing.what_the_briefing_could_not_settle, list), (
        f"what the briefing could not settle is "
        f"{type(a_real_briefing.what_the_briefing_could_not_settle).__name__} rather than a list, "
        "so a reader cannot count what this briefing was unsure about"
    )
    for a_doubt in a_real_briefing.what_the_briefing_could_not_settle:
        assert a_doubt.strip(), (
            f"one of the doubts the briefing recorded is blank, and the list is rendered into a "
            f"person's own words further down — so a blank entry reaches a card as a sentence "
            f"ending in a separator and a reader sees a doubt nobody had: "
            f"{a_real_briefing.what_the_briefing_could_not_settle}"
        )

    the_sentences_no_model_wrote = (NOTHING_WAS_FOUND, NOTHING_WAS_UNSETTLED)
    for what_the_model_said in (
        a_real_briefing.agent_judgement.what_it_found,
        a_real_briefing.agent_judgement.what_it_could_not_settle,
    ):
        assert what_the_model_said not in the_sentences_no_model_wrote, (
            f"{what_the_model_said!r} is the sentence this report type falls back on when a model "
            "judged nothing, so the briefing beside its opportunities is carrying the default and "
            "a board would read a judgement nobody made"
        )
        assert what_the_model_said.strip().lower() not in the_placeholders, (
            f"{what_the_model_said!r} is placeholder text in the judgement beside the "
            "opportunities, which is the note a person reads afterwards to decide whether the "
            "briefing was worth running"
        )

    assert a_real_briefing.agent_judgement.what_it_expects_next.strip(), (
        "the judgement beside the opportunities names nothing about what happens next, and that "
        "is the sentence a person reads to know whether a briefing ended at a board or went "
        "somewhere on its own"
    )
