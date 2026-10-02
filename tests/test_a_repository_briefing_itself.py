"""A repository briefs itself, a person picks two of five, and two work items exist.

**The other half of the product, and it is the half that was missing.** Everything else in this
repository takes a sentence somebody typed. This takes a repository, reads it, and proposes the
work it could be given — which is a different kind of question, because the answer is not derived
from anything the deployment said.

**A real clone of a repository made locally, and two things faked, each named where it is
replaced.** The clone, the state machine, the gate, the register, the idempotence of the filing
and the HTTP surface are all production code. What is replaced is the model and the issue API,
because those two need a network and a credential and neither is what this file is about.

**The test worth reading is the last one.** A briefing that cites a file the repository does not
have is refused, and the model is asked again with the refusal quoted. That is the whole of why
`proving_what_they_cite` exists, and it is a real behaviour rather than a claim: the first
briefing this system ever asked for proposed `src/App.jsx` four times in a repository with no
`src/` at all.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from aisdlc.creative.a_repository_briefing_itself import (
    NotAnOpportunityInThisBriefingError,
    a_repository_briefed_itself,
    filing_the_picks_a_person_made,
)
from aisdlc.creative.an_opportunity import AnOpportunity
from aisdlc.creative.filing_what_the_briefing_found import AnIssueThatWasOpened
from aisdlc.creative.the_opportunities_this_repository_offers import (
    AnOpportunityCitingAFileTheCloneDoesNotHoldError,
    TheOpportunitiesThisRepositoryOffers,
)
from aisdlc.domain.repository import Repository
from aisdlc.store.the_board_reads import AColumnOfTheBoard, the_board_this_register_holds
from aisdlc.store.the_register_of_work_items import the_work_item_registered_at
from aisdlc.store.where_the_register_lives import holding_the_register, the_register_lives_at
from aisdlc.tools.github_client import Addresses
from aisdlc.tools.github_clone_repository import a_repository_to_clone, clone_repository
from aisdlc.tools.github_list_open_issues import AnOpenIssue

A_REPOSITORY = Repository(owner="pikuniu", name="a-project")
THE_NEXT_ISSUE_NUMBER = 41
A_COMMIT = "0000000000000000000000000000000000000000"


@pytest.fixture
def creative_mode_on(monkeypatch) -> None:
    """The deployment says a repository may brief itself, in the one word that means it.

    **And the tests that need it off are in this file**, because a setting only ever read as `on`
    has not been tested as a setting.
    """
    monkeypatch.setenv("AISDLC_CREATIVE_MODE", "on")


@pytest.fixture
def a_repository_to_brief(tmp_path: Path) -> Path:
    """A bare repository with two files, made locally, and a clone of it on disk.

    **A real `git init`, a real commit, a real push and a real `git clone`.** A briefing's first
    act is a read of a repository and a doubled clone would leave the one step everything else
    depends on unproven. **Both the bare repository and a clone of it**, because a bare repository
    has no working tree — it holds objects and `hooks/*.sample` — and pointing a clone at one
    produces an inspection of git's sample scripts, which is 23 paths and none of them the
    project's.
    """
    the_bare = tmp_path / "the-origin.git"
    the_bare.mkdir()
    _git(the_bare, "init", "--bare", "--initial-branch=main")

    a_working_copy = tmp_path / "a-working-copy"
    a_working_copy.mkdir()
    _git(a_working_copy, "init", "--initial-branch=main")
    _git(a_working_copy, "config", "user.email", "a-briefing@example.com")
    _git(a_working_copy, "config", "user.name", "a briefing")
    (a_working_copy / "README.md").write_text("# a project\n", encoding="utf-8")
    (a_working_copy / "auth.js").write_text(
        "const secret = process.env.SECRET || 'dev-change-me';\n", encoding="utf-8"
    )
    _git(a_working_copy, "add", ".")
    _git(a_working_copy, "commit", "-m", "the first commit")
    _git(a_working_copy, "remote", "add", "origin", str(the_bare))
    _git(a_working_copy, "push", "origin", "main")

    return the_bare


@pytest.fixture
def a_clone_of_the_repository(a_repository_to_brief: Path, tmp_path: Path):
    """A real working-tree clone, which is what an inspection is ever taken of."""
    return clone_repository(
        a_repository_to_clone(
            A_REPOSITORY,
            Addresses(
                fetch_from=str(a_repository_to_brief),
                origin_of_the_code=str(a_repository_to_brief),
            ),
            tmp_path / "a-clone",
        )
    )


def _git(where: Path, *what: str) -> str:
    what_happened = subprocess.run(
        ["git", *what], cwd=where, capture_output=True, text=True, check=False
    )
    if what_happened.returncode != 0:
        pytest.fail(f"git {' '.join(what)} in {where} failed: {what_happened.stderr}")
    return what_happened.stdout


def _an_opportunity(
    what: str = "Remove the fallback secret from the authentication module",
    citing: str = "auth.js",
) -> AnOpportunity:
    """One well-formed opportunity, citing a file the local repository really has.

    **The citation is the field the whole type exists for**, so it is a real path of the
    repository this file clones rather than a string that looks like one.
    """
    return AnOpportunity(
        what_could_be_done=what,
        why_it_is_worth_doing=(
            "auth.js falls back to a literal when SECRET is unset, so a deployment that forgets "
            "the setting signs sessions with a value that is in the repository"
        ),
        the_files_that_show_this=[citing],
        how_it_would_be_known_to_have_worked=(
            "a test asserts auth.js refuses to load when SECRET is unset"
        ),
        the_discipline_that_owns_it="SEC",
        the_risk_of_it="Touches every session this application issues",
    )


def _a_briefing_with(*opportunities: AnOpportunity) -> TheOpportunitiesThisRepositoryOffers:
    """A report of the given opportunities, which is what the node would have returned."""
    from aisdlc.agents.what_an_agent_judged import WhatAnAgentJudged

    return TheOpportunitiesThisRepositoryOffers(
        about=A_REPOSITORY,
        what_this_repository_is="a project with an authentication module and no tests",
        opportunities=list(opportunities),
        what_the_briefing_could_not_settle=["whether the deployment sets SECRET"],
        agent_judgement=WhatAnAgentJudged(
            what_it_found="an authentication module with a literal fallback",
            what_it_could_not_settle="whether the deployment sets SECRET",
            what_it_expects_next="a person picks which opportunities become work",
        ),
    )


def _the_seams_a_real_run_would_not(
    the_report: TheOpportunitiesThisRepositoryOffers, the_bare: Path
) -> tuple[object, object, object]:
    """A briefing that returns a prepared report, and a clone from a local repository.

    **All three seams at once and in one place, because a test that passes one and forgets
    another is a test that reached GitHub.** The first version of this file handed in a briefing
    and let the clone planner default, so the run under test did the one thing it was not supposed
    to: it tried to clone `pikuniu/a-project` from github.com and died on a credential prompt
    rather than on anything this file is about. The issue reader arrived later and repeated it —
    a briefing that reaches for the open issues of a repository this test made, on this machine,
    against github.com.

    **Three replacements, all named.** The model is replaced because a briefing against a real
    model takes minutes and this file is about what happens to the answer rather than the answer.
    The address is replaced because the repository is one this test made, on this machine. The
    issue list is replaced with an empty one because **a repository with no issues is the common
    real case** and is worth testing — what is *not* worth testing is a unit suite reading a
    stranger's repository.
    """

    def planning(source: Repository, into: Path):
        return a_repository_to_clone(
            source,
            Addresses(fetch_from=str(the_bare), origin_of_the_code=str(the_bare)),
            into,
        )

    def briefing(
        clone, repository, how_many: int = 5, what_is_already_tracked=()
    ) -> TheOpportunitiesThisRepositoryOffers:
        return the_report

    def no_issues_are_open(_repository: Repository) -> list[AnOpenIssue]:
        return []

    return briefing, planning, no_issues_are_open


def _an_issue_opener_that_records() -> tuple[object, list[AnOpportunity]]:
    """A stand-in for GitHub's issue API, and the list of what it was asked to open.

    **The list and not a count, because the caller files each opportunity's own words.** A
    counting double would pass a filing that opened the same issue twice with the wrong body, and
    an issue is a thing a person reads.
    """
    what_was_opened: list[AnOpportunity] = []

    def opening(an_opportunity: AnOpportunity, _repository: Repository) -> AnIssueThatWasOpened:
        what_was_opened.append(an_opportunity)
        a_number = THE_NEXT_ISSUE_NUMBER + len(what_was_opened)
        return AnIssueThatWasOpened(
            number=a_number,
            address=f"https://example.invalid/{A_REPOSITORY.address}/issues/{a_number}",
        )

    return opening, what_was_opened


def _an_open_register(tmp_path: Path, monkeypatch) -> None:
    """A register in a temporary directory and a projects root beside it.

    **Both named at once, because the filing writes to both.** A filing that opened a real issue
    and could not find its work item would leave a ticket somebody is asked to rule on and a board
    that does not show it, and only the second of those is visible from inside this process.
    """
    monkeypatch.setenv("AISDLC_PROJECTS_DIR", str(tmp_path / "projects"))
    the_register_lives_at(tmp_path / "the-register.sqlite3")


def test_a_person_picking_two_of_five_gets_two_work_items_on_the_board(
    tmp_path: Path, monkeypatch, a_repository_to_brief: Path, creative_mode_on: None
) -> None:
    """A briefing of five opportunities, two picked, becomes two tickets and two cards.

    **Five are proposed and only two are chosen, because that is the rule this is really about.**
    Filing is an external write, and a write that happens for every proposal is a backlog this
    system invented rather than a decision anybody made.

    **The work items are read back out of the register**, not taken from the filing's return
    value, because the return value is what the filing says it did and the register is where
    anything can be checked by a third party.
    """
    _an_open_register(tmp_path, monkeypatch)

    the_five = [
        _an_opportunity(),
        _an_opportunity("Say in the README where the data goes", citing="README.md"),
        _an_opportunity("Add a test runner so the suite can fail"),
        _an_opportunity("Name the secret in the deployment notes", citing="README.md"),
        _an_opportunity("Rotate the secret that was in the history"),
    ]

    the_briefing = a_repository_briefed_itself(
        A_REPOSITORY,
        *_the_seams_a_real_run_would_not(_a_briefing_with(*the_five), a_repository_to_brief),
    )
    assert len(the_briefing.opportunities) == 5, "a briefing that proposed five"

    the_issue_opener, what_was_opened = _an_issue_opener_that_records()
    the_filing = filing_the_picks_a_person_made(the_briefing, [1, 2], the_issue_opener)

    assert the_filing.how_many_opportunities_were_found == 5
    assert the_filing.how_many_became_filings == 2, (
        "two opportunities were chosen, so two were filed. A briefing filing all five is a "
        "backlog this system invented rather than a decision anybody made"
    )
    assert [an_opportunity.what_could_be_done for an_opportunity in what_was_opened] == [
        the_five[1].what_could_be_done,
        the_five[2].what_could_be_done,
    ]

    with holding_the_register() as a_register:
        the_cards = the_board_this_register_holds(a_register)

    assert len(the_cards) == 2, "two tickets, and a board showing any other number is lying"
    for a_card in the_cards:
        assert a_card.column is AColumnOfTheBoard.TO_DISCUSS, (
            "a freshly filed ticket is at READY, which the board reads as *to discuss*. The "
            "table of legal moves has no edge into READY, which is the whole reason it cannot be "
            "reached any other way — a briefing cannot put a ticket in its own queue"
        )

    with holding_the_register() as a_register:
        the_filed = the_work_item_registered_at(a_register, the_cards[0].work_item_id)

    assert the_filed.requested is not None
    assert the_filed.requested.filed_as is not None, (
        "a request out of an issue and a request out of a sentence are different evidence, and a "
        "delivery names the filing twice — once in the branch and once in the pull request's "
        "body. Dropping it here would make the two indistinguishable on the card"
    )
    assert the_filed.requested.filed_as.address.startswith("https://")


def test_filing_the_same_picks_twice_opens_no_second_issue(
    tmp_path: Path, monkeypatch, a_repository_to_brief: Path, creative_mode_on: None
) -> None:
    """A briefing picked twice files once, because an issue opened twice is two tickets.

    **Idempotence for a write to the outside world.** Filing is a `POST` to GitHub and there is no
    undo. A briefing retried because its answer was slow is a briefing retried for a reason that
    happens, and the second attempt must find the first's work rather than duplicate it.

    **The second attempt goes through a fresh briefing object carrying the same opportunities**,
    which is what a retry actually is: the report is rebuilt, the opportunities are the same
    words, and the recognition is of the words rather than of a run that would have to be carried
    into the second process.
    """
    _an_open_register(tmp_path, monkeypatch)

    the_first = a_repository_briefed_itself(
        A_REPOSITORY,
        *_the_seams_a_real_run_would_not(
            _a_briefing_with(_an_opportunity()), a_repository_to_brief
        ),
    )
    the_issue_opener, what_was_opened = _an_issue_opener_that_records()
    filing_the_picks_a_person_made(the_first, [0], the_issue_opener)

    the_second = a_repository_briefed_itself(
        A_REPOSITORY,
        *_the_seams_a_real_run_would_not(
            _a_briefing_with(_an_opportunity()), a_repository_to_brief
        ),
    )
    the_second_filing = filing_the_picks_a_person_made(the_second, [0], the_issue_opener)

    assert len(what_was_opened) == 1, (
        "the same opportunity was filed twice, so two issues exist and a person will be asked to "
        "rule on each. An issue cannot be un-opened, which is the whole reason the filing is "
        "remembered against the opportunity's own words"
    )
    assert the_second_filing.how_many_became_filings == 1, (
        "the second attempt found the first's work and reported the same count, because the work "
        "item exists — it is not a new one and it is not a failure"
    )

    with holding_the_register() as a_register:
        assert len(the_board_this_register_holds(a_register)) == 1


def test_choosing_something_this_briefing_never_proposed_files_nothing_at_all(
    tmp_path: Path, monkeypatch, a_repository_to_brief: Path, creative_mode_on: None
) -> None:
    """A bad index is refused by name, and the good ones beside it are not filed either.

    **Two of three is a person who was told they chose three.** A filing that stopped at the bad
    index would leave a board with one card and a person who believes they asked for two, and the
    next thing they learn about this system would be that its numbers do not mean what they say.
    """
    _an_open_register(tmp_path, monkeypatch)

    the_briefing = a_repository_briefed_itself(
        A_REPOSITORY,
        *_the_seams_a_real_run_would_not(
            _a_briefing_with(
                _an_opportunity(),
                _an_opportunity("Say in the README where the data goes", citing="README.md"),
            ),
            a_repository_to_brief,
        ),
    )
    the_issue_opener, what_was_opened = _an_issue_opener_that_records()

    with pytest.raises(NotAnOpportunityInThisBriefingError) as refused:
        filing_the_picks_a_person_made(the_briefing, [0, 7], the_issue_opener)

    assert "7" in str(refused.value), "the refusal names the index that is not one"
    assert what_was_opened == [], (
        "the good index was filed and the bad one refused, so a person who chose two was told "
        "they chose two and got one"
    )

    with holding_the_register() as a_register:
        assert the_board_this_register_holds(a_register) == []


def test_a_briefing_is_refused_when_the_deployment_did_not_ask_for_one(
    tmp_path: Path, monkeypatch, a_repository_to_brief: Path
) -> None:
    """No setting, no briefing — and a value that is not `on` is refused rather than read as off.

    **Both halves, because they are different mistakes.** Absent is a deployment that said
    nothing, and it means off. A value that is not `on` is a deployment that wrote something this
    system cannot read, and reading it as off is a repository that quietly filed nothing while
    somebody watched a board expecting cards.
    """
    from aisdlc.creative.is_creative_mode_on import ACreativeSettingThatIsNotOnError

    _an_open_register(tmp_path, monkeypatch)

    def asking_for_a_briefing() -> object:
        return a_repository_briefed_itself(
            A_REPOSITORY,
            *_the_seams_a_real_run_would_not(
                _a_briefing_with(_an_opportunity()), a_repository_to_brief
            ),
        )

    monkeypatch.delenv("AISDLC_CREATIVE_MODE", raising=False)
    with pytest.raises(ACreativeSettingThatIsNotOnError) as not_asked:
        asking_for_a_briefing()
    the_refusal = str(not_asked.value)
    assert "AISDLC_CREATIVE_MODE" in the_refusal and "'on'" in the_refusal, (
        "the refusal has to name both the setting and the one value that means on, because a "
        f"person reading it is holding a configuration file and not a document about one. It "
        f"said: {the_refusal}"
    )

    for a_value_that_is_not_on in ("true", "1", "ON", "yes", ""):
        monkeypatch.setenv("AISDLC_CREATIVE_MODE", a_value_that_is_not_on)
        with pytest.raises(ACreativeSettingThatIsNotOnError):
            asking_for_a_briefing()


def test_a_citation_to_a_file_the_repository_does_not_have_is_refused(
    a_clone_of_the_repository,
) -> None:
    """An invented path fails the whole briefing, and a grounded one comes back proved.

    **This is the behaviour that did not exist and the real briefing needed.** The first briefing
    this system asked for proposed `src/App.jsx` in all four opportunities — a file the repository
    does not have, describing a React application the repository is not. Nothing caught it, because
    the check read `evidence_files`, which a model cannot write, and an empty list proves nothing.

    **The check is on the model's own field and the node fills the other one from it.** That is
    the whole of the split between the two fields, and getting it the wrong way round is a check
    that cannot fail.
    """
    from aisdlc.agents.brief_this_repository import what_the_clone_holds

    the_clone = a_clone_of_the_repository
    what_is_there = what_the_clone_holds(the_clone)

    assert "auth.js" in what_is_there, (
        "the clone this test is inspecting holds no auth.js, so every citation in the rest of "
        "this test is a citation to a file that is not there and the whole file proves the wrong "
        "thing"
    )
    assert "src/App.jsx" not in what_is_there

    with pytest.raises(AnOpportunityCitingAFileTheCloneDoesNotHoldError) as refused:
        TheOpportunitiesThisRepositoryOffers.proving_what_they_cite(
            _a_briefing_with(_an_opportunity(citing="src/App.jsx")), what_is_there
        )

    assert "src/App.jsx" in str(refused.value)

    proved = TheOpportunitiesThisRepositoryOffers.proving_what_they_cite(
        _a_briefing_with(_an_opportunity(citing="auth.js")), what_is_there
    )
    assert proved.opportunities[0].evidence_files == ["auth.js"], (
        "`evidence_files` is what the clone held and `the_files_that_show_this` is what the model "
        "wrote. The model cannot know the answer to the first, which is why the check reads the "
        "second and the node fills the first"
    )


def test_a_refusal_names_every_citation_and_not_only_the_one_that_failed() -> None:
    """Three opportunities, three invented paths, and the refusal carries all three.

    **A refusal naming only the failure produces a second answer naming a different file that
    also does not exist.** That is not a theory: a model asked to correct itself once was given
    one bad path, fixed that one, and produced a second answer citing a second file that was
    also not there. The whole list is what makes one correction enough.
    """
    the_report = _a_briefing_with(
        _an_opportunity("One", citing="src/One.jsx"),
        _an_opportunity("Two", citing="src/Two.jsx"),
        _an_opportunity("Three", citing="README.md"),
    )

    with pytest.raises(AnOpportunityCitingAFileTheCloneDoesNotHoldError) as refused:
        TheOpportunitiesThisRepositoryOffers.proving_what_they_cite(the_report, ["README.md"])

    the_message = str(refused.value)
    for an_invented_path in ("src/One.jsx", "src/Two.jsx"):
        assert an_invented_path in the_message, (
            f"{an_invented_path} was cited and is not in the clone, and the refusal does not name "
            "it — so a model correcting itself fixes the one it was told about and produces a "
            "second answer citing another file that is also not there"
        )
