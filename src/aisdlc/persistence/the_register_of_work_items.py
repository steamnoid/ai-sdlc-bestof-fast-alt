"""Where a work item is kept, so a run that resumes finds the same one.

**The register is the project directory, and that is the decision this module settles.** A work
item's run already has a directory named after it, and that directory is where a person goes to
find out what happened. A register kept elsewhere — a table, a second tree — is a second place a
record lives, and the two eventually disagree about whether work was commissioned at all. A
durable register with no database in it is possible because the file system is one.

**Commissioning is idempotent, and the second call hands back the first.** Not an error and not a
fresh work item: a commissioning act that could not happen twice would turn every retry into a
failure, and a run asked to resume must find the item it is resuming with whatever it already
knows. The pattern is `github_fork_repository`'s and the reason is the same — a delivery that runs
twice must not fail on its own first step.

**Nothing is loaded from a second source and merged.** The file is either there or it is not, so
there is no reconciliation to get wrong and no question of which of two records wins.

**A lookup that finds nothing raises rather than returning a new work item**, because a run that
invents one goes on to write a complete set of artifacts about nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

from aisdlc.domain.repository import Repository
from aisdlc.domain.work_item import WorkItem
from aisdlc.tools.the_project_directory import the_project_directory_of

A_RECORD_A_PERSON_CAN_READ = ".json"
WHERE_THE_WORK_ITEM_IS_REGISTERED = "WorkItem.json"


def a_work_item_is_left_where_its_run_happens(
    commissioned: WorkItem, projects_root: Path
) -> WorkItem:
    """The work item, written into the register — or the one that is already there.

    **Returns the first one rather than a second, and that is the whole of the idempotence.** A
    fresh work item built from the same inputs compares equal to the one already registered, so an
    equality check would pass while the register held two records of one piece of work; what
    makes it one is that this hands back the object the first call wrote.
    """
    the_register = _where_the_work_item_is_registered(commissioned, projects_root)

    if the_register.is_file():
        return _the_work_item_in(the_register)

    the_register.parent.mkdir(parents=True, exist_ok=True)
    the_register.write_text(
        json.dumps(commissioned.model_dump(mode="json"), indent=2), encoding="utf-8"
    )

    return commissioned


def the_work_item_is_recorded_at(where_it_got_to: WorkItem, projects_root: Path) -> Path:
    """Put the work item where it has got to, overwriting whatever the register said.

    **A separate function from commissioning, and the separation is a bug I paid for.** I made a
    transition record through the commissioning writer, which is idempotent — it
    writes once and afterwards returns what is there without writing. That is right for
    commissioning and exactly wrong for a move: every later transition found the file and left it
    alone, so a run went through eight gates and opened a pull request while the register still
    said `AWAITING_AGENT_PICKUP`. A run resuming from it would have picked up work a completed run
    had already finished.

    Commissioning asks "does this exist?" and answers once. Recording asks "where is it now?" and
    answers every time. Two questions, two functions, because one function answering both can only
    answer one of them.
    """
    the_register = _where_the_work_item_is_registered(where_it_got_to, projects_root)
    the_register.parent.mkdir(parents=True, exist_ok=True)
    the_register.write_text(
        json.dumps(where_it_got_to.model_dump(mode="json"), indent=2), encoding="utf-8"
    )

    return the_register


def the_work_item_registered_as(
    repository: Repository, work_item_id: str, projects_root: Path
) -> WorkItem:
    """The work item a previous run registered under this id, or a loud refusal.

    **A repository and an id rather than a `WorkItem`, because a caller that had one would not be
    looking anything up** — it would already be holding the answer. What a resuming run has is a
    repository somebody pointed this at and a work item id from a ticket, and that is what this
    takes.

    **Raised rather than returning a new one.** A run that cannot find its work item and invents
    one goes on to write eight artifacts and a summary about a delivery that was never
    commissioned, and every one of them looks like a record.
    """
    the_register = (
        projects_root / repository.owner / repository.name / work_item_id
    ) / WHERE_THE_WORK_ITEM_IS_REGISTERED

    if not the_register.is_file():
        raise NoSuchWorkItemError(repository, work_item_id, projects_root)

    return _the_work_item_in(the_register)


def _where_the_work_item_is_registered(work_item: WorkItem, projects_root: Path) -> Path:
    """The file this work item is registered in, inside the directory its runs happen in.

    **The project directory and not a path of its own**, so the register and the artifacts of a
    run cannot end up in two directories — which is the whole reason the register is here.
    """
    return the_project_directory_of(work_item, projects_root) / WHERE_THE_WORK_ITEM_IS_REGISTERED


def _the_work_item_in(the_register: Path) -> WorkItem:
    """A work item read back out of the register, validated rather than cast.

    The same rule every other reader in this package follows: a file on disk is data until
    something has checked it, and a work item that changed shape since it was written should be
    refused loudly here rather than failing three stages later in a way that names a node instead
    of a file.
    """
    return WorkItem.model_validate_json(the_register.read_text(encoding="utf-8"))


class NoSuchWorkItemError(Exception):
    """The rule is in this module: the register holds what was commissioned and nothing else.

    Raised rather than creating one, because the two failures look identical from outside and
    only one of them is a run that worked: a run that invents its work item produces a complete,
    plausible directory of artifacts about work nobody asked for.
    """

    def __init__(self, repository: Repository, work_item_id: str, projects_root: Path) -> None:
        """Name the repository, the id and where it looked, because a caller retries."""
        super().__init__(
            f"{work_item_id!r} is not registered against {repository.owner}/{repository.name}, "
            f"and nothing under {projects_root} is. A run that continued without its work item "
            f"would write a full set of artifacts about work nobody commissioned, so this stops "
            f"here instead."
        )
