# ai-sdlc-bestof-fast

An AI-native software lifecycle with a board. A repository goes in, a sentence says what should
change, and a pull request comes out with every decision in the trail.

```text
  a repository and a sentence
              │
              ▼
   discovery ─▶ requirements ─▶ scenarios ─▶ architecture ─▶ security
       │            │              │             │             │
     a gate        a gate         a gate        a gate        a gate
       │            │              │             │             │
       ▼            ▼              ▼             ▼             ▼
      plan ─▶ implementation ─▶ verification ─▶ pull request ─▶ DONE
       │              │              │
     a gate        a gate         a gate
       │              │              │
       └──────── a refusal or a red suite goes to the repair supervisor ─┘
```

Eight gates, and a person is asked at every one. A refusal ends the run where it was refused,
with the reason on the card.

---

[![gate](https://github.com/steamnoid/ai-sdlc-bestof-fast/actions/workflows/gate.yml/badge.svg)](https://github.com/steamnoid/ai-sdlc-bestof-fast/actions/workflows/gate.yml)

## Run it

```bash
uv sync --all-groups
uv run aisdlc serve            # the board, on http://127.0.0.1:842
```

Open the address, type a repository and a sentence, press **start a run**. A card appears
immediately — before the clone, before the first model call — and then moves on its own until it
reaches a gate and waits for you. Click the card to read what the run found and to answer.

A run in a terminal instead, with the gates in your own shell:

```bash
uv run aisdlc run paligakrzychu/wellbeing-tracker-public "add a /health endpoint"
```

### Configuration

A run needs a model, and the deployment says which:

```bash
LLM_PROVIDER=openai_compatible
LLM_ENDPOINT=https://...
LLM_MODEL=...
LLM_THREAD_ID=aisdlc            # the gateway routes by session and refuses without it
OPENAI_API_KEY=...               # the name LangChain's clients read, so this one reads it too
```

| setting | what it does |
|---|---|
| `AISDLC_PROJECTS_DIR` | where every run's directory goes, and where the register file sits. Defaults to `./aisdlc-projects` |
| `AISDLC_APPROVAL_POLICY` | a bare name. The policy that answers the gates instead of a person, recorded as `autopilot:<name>` and never as a person |
| `AISDLC_FORK_OWNER` | whose copy a run pushes to. Delivery needs it; a run that only reasons does not |
| `AISDLC_CORRECTION_BUDGET` | how many times a run may ask a model for an answer it already had |
| `AISDLC_REPEAT_BUDGET` | how many times the supervisor may put an agent back on a ticket |
| `AISDLC_WHAT_A_RUN_IS_DOING` | `1` sends every tool call and every token to the terminal |

`GITHUB_TOKEN` is needed for delivery and not for reasoning. Every one of these is **refused
rather than defaulted** when it holds something this system cannot read — a setting nobody
noticed and an answer nobody asked for are the same failure wearing different names.

---

## The test

```bash
uv run pytest -q     # 54 passed, 1 skipped, 5s, no network, no model, no credential, no container

# The one test that asks a model runs when a deployment has stated LLM_PROVIDER / LLM_ENDPOINT /
# LLM_MODEL, and skips with the reason printed when it has not. To watch it judge:
set -a && . ./.env && set +a && uv run pytest -q -s \
  tests/test_a_real_model_judging_a_real_refusal.py

# The e2e tier is not separated here: `uv run pytest` is the whole suite, and a live-model run is
# driven through the same board by starting the server with a `.env` in place.
```

One file, and it is the whole product: a person posts a repository and a sentence over real
HTTP, answers eight gates one at a time, and gets a pull request — with a **real `git clone`** of
a repository made locally on the spot, the real state machine, the real gate, the real register
and a real board. Four things are replaced and each is named where it is replaced: the seven
agents do not call a model, the two delivery collaborators do not call GitHub, and the clone is
fetched from a path rather than a host. Everything else is production code on its real path.

It asserts the things that would be a lie otherwise: that a card exists before the run has done
anything, that the work item really is at `DONE` when the board says delivered, that a refusal
leaves one decision and no approval, and that an `aisdlc-` identifier posted as a decider is
refused with the gate's own sentence.

---

## It has run for real, twice, and both runs found something

Every proof above uses a faked model, which makes it a proof about the wiring and not about the
product. So the pipeline was pointed at `paligakrzychu/wellbeing-tracker-public` with the
deployment's real model, a real container and a real fork, and `AISDLC_APPROVAL_POLICY` answering
the gates unattended.

**Run 1: five gates approved, the sixth refused.** The security analyst was refused for a reason
no test would ever have produced:

> The report never read the item it was commissioned to review: it states the entire inspection
> was a top-level listing plus the contents of `package.json` … Six of the seven entries are then
> speculation from filenames and dependency declarations alone

It was right. The run stopped where it was refused, with the reason on the card.

**Two real defects, both found only by running it.**

**A security analyst shown no source code.** `an_inspection_of` was built for *discovery*, whose
job is a repository's shape — its own docstring says "Source files are not in it, because a
discovery report is a summary of a repository's shape and not a copy of its contents" — and the
security analyst was later wired to the same one. It was therefore asked to find authentication
and authorization problems while being handed a directory listing and a `package.json`. Now
`an_inspection_of_the_code` shows the code, chosen by the names security problems live in, and
**ends by naming what it did not show**. The same model on the same repository then produced:

| before | after |
|---|---|
| 7 findings, six reasoning from `Dockerfile`, `.dockerignore` and `bcryptjs` | 7 findings, every one quoting code |
| 1,434 characters of evidence | 10,835 |
| coverage gap filed as `informational` | *"I could not verify dependency resolution"* — the model naming the limit of its own evidence |

The first finding after the fix, quoted from the model, at severity **high**:

> `function secret() { return new TextEncoder().encode(process.env.JWT_SECRET ||
> "dev-secret-change-me"); }` in `web-app/src/lib/auth.js` and the identical helper in
> `web-app/src/middleware.ts`

A hardcoded JWT secret fallback, in a real public repository, found by this system and delivered
as a report with every quotation checked back to a file it read.

**A symlinked projects root broke the planner.** `plan_the_change` asked the confinement check
where a test's directory was, got back a path that had been **resolved**, and compared it against
a root that had **not**. On any machine where the two spellings differ the comparison raised
Python's own `ValueError` about a subpath, out of a stage, twenty minutes into a run:

> `'/private/tmp/…/repository/tests' is not in the subpath of '/tmp/…/repository'`

macOS makes `/tmp` a link to `/private/tmp`. **No unit test could have found it**: pytest hands
out an already-resolved `tmp_path` and every test in the suite ran from one. `filesystem_read`
already resolved both sides for exactly this reason and says so in its own docstring — the same
bug, one module over, never fixed there.

**Run 2, with both fixed: the same five gates, and the security gate approved on the evidence.**

> Every finding is anchored to quoted code in a named file (the duplicated
> `process.env.JWT_SECRET || "dev-secret-change-me"` in `web-app/src/lib/auth.js` and
> `web-app/src/middleware.ts`, the `||`-short-circuited bcrypt compare …), severities are
> calibrated

and the planner produced a plan, which gate 6 refused for its own independent reason — that the
plan named `vitest.config.ts` without saying what change it needed. The run stopped cleanly,
`how_it_ended: None`, because a refusal is a decision and not a fault.

**And then four more, from one run each — and a pattern.**

Every one of these is the same shape: **the gate was right and something underneath it was
wrong.** That is what a real run is for. Four runs, four refusals, and in three of them the
refusal named the defect precisely enough to fix it.

| what the gate said | what was actually wrong |
|---|---|
| *"The report never opens the Dockerfile — the only file this work item actually changes."* | `Dockerfile` carries **no extension**, and the source-suffix filter excluded exactly the files that carry none. A `Dockerfile` and a `Makefile` were invisible to every agent in the system |
| *"Its one nod to the healthcheck is an inference from the repository's branch name."* | the file selection was named after the **security** question — which fixed the security analyst and was then applied to every agent. A selection framed around one consumer is the wrong selection for the others, and it is now what a *change* tends to touch |
| *"the suite passed identically with the file present and deleted"* | the implementer wrote the file back byte-for-byte, and that refusal **killed the run** instead of reaching the supervisor — the one refusal where the answer is least in doubt, because the plan named the file and said what to change in it |
| *"while `Dockerfile` nonetheless appears in `evidence_files` with blob links as though they had been read"* | discovery cites were proved to be **files of the clone** and never checked against **what the model was shown**. A report could say a file's contents were not shown and cite it anyway, and the check that existed could not see it |

The fourth one has a test that bites: a file that genuinely exists in the clone — `.gitignore` —
is refused because the inspection did not contain it. Before, the existence check passed it.

**A fifth, and it is the one worth having.** Six gates, five approvals, and a refusal at the plan
that reads like a person who has read the repository:

> The plan names `Dockerfile` as the only file to change and explicitly declares
> `tests_to_add` as empty, so nothing in this run will ever exercise the healthcheck it is
> adding. **A `HEALTHCHECK` whose path, port, or interval is wrong does not fail loudly — the
> container simply reports unhealthy forever** — and this plan contains no build-and-run step
> confirming the endpoint exists and that the container reaches "healthy".

And it was right: `tests/unit/wellbeingt-17-docker-static.test.ts` asserts `--interval=30s`, so
the change this run was asked for makes that suite red, and the plan said nothing about it.

**And the repair supervisor ran, for the first time, against a real card.** Three stages hand a
refusal to it — a plan whose test is in a directory the suite does not collect, a test that
passed without the change, a suite that went red — and it reads the card, asks a model, and names
one of two stages to start again at. Both real runs above were answered by a policy that never
refused, so none of the three fired; the mechanism was carried across unexercised, and a
mechanism nobody has watched is a claim.

Asked with the **real card from run 2** — five notes real agents left about a real repository —
and a real refusal, a real model decided in 6 seconds:

> **the run starts again at: the planner**
>
> what has not changed: *No observation has contradicted the requirement that the root
> `package.json` be asserted, and `vitest.config.ts` still has no include that collects anything
> under `tests/e2e/WELLBEINGT-201`, so the repository's test runner reads exactly as much of the
> change as it did on the first attempt.*
>
> **`aisdlc-dev-plan`: repeat** — *This is the vacuous-test failure and the plan owns it. The plan
> named `tests/e2e/WELLBEINGT-201/package-json-typecheck.test.ts` while no include in
> `vitest.config.ts` reaches it, so the suite passed identically with the file present and
> deleted.*

It named the planner and only the planner, and its reason is the one the engine's own log records
from a run two years of work ago: *a plan that lands a test the runner never collects is a plan
that misunderstood the repository.*

**A refusal is a refusal, and stopping is a refusal too — two different ones.** Every agent told
to stand down **raises**, because a run that returned quietly reads as a run that finished. An
agent out of turns raises a *different* error naming `AISDLC_REPEAT_BUDGET`, because a clean stop
and a judgement the deployment overruled must not look alike in a record. And `0` lifts the
ceiling rather than forbidding every repeat — which is the opposite of a count, and reading it as
"no repeats" would make the setting mean two things depending on which agent it was read for.

**A note is written before the supervisor acts, not after.** Every verdict goes on the card,
including the ones that stand an agent down: a record saying only who repeats cannot be argued
with afterwards by a reader who disagrees with the planner being sent back.

**One thing a real run showed about the board.** A run spent twenty minutes inside the
planner and the board said "working" for all of it. The run's own record carries a timestamp on
every line, so a card now says `on begin_planning_the_change · 20 minutes`. The first version of
that card read `on __interrupt__`, because when a run parks, the node that last "ran" is
LangGraph's own.

---

## The other half: a repository briefs itself

**A run answers a sentence somebody typed. A briefing answers "what should this repository be
given",** which is a different kind of question — nothing in it came from the deployment, and a
model that is not shown the repository's own files will invent the work.

```bash
AISDLC_CREATIVE_MODE=on uv run aisdlc serve
```

Then press **what should this repository be given?**. It clones read-only, forks nothing, needs no
credential, and takes two to three minutes — which the button says, because a button that appears
to have done nothing is worse than one that says it is waiting.

A real briefing of `paligakrzychu/wellbeing-tracker-public`, 2m42s, five opportunities, every
citation proved against the clone:

> **[1] Replace the ticket-named end-to-end specs with tests named for the behaviour they assert**
> — QA — *"A check enumerates tests/e2e and fails on any spec whose file name does not match"*
>
> **[3] Assert the authentication contract in `tests/unit` rather than only through the browser**
> — SEC — *"a test calls the login route handler and asserts the `Set-Cookie` header carries
> `HttpOnly`…"*
>
> **[4] Check that `web-app/schema.sql` and the queries the application actually issues agree**
> — DEV — *"the integration test applies `schema.sql` to an empty database, inserts a row…"*

and what it could not settle, which is the half that matters:

> Whether the hex-named spec files in `tests/e2e` carry their ticket meaning in the spec bodies or
> in `tests/e2e/mapping.ts`

**A person then picks, and the picks become work.** Filing is a `POST` to GitHub and there is no
undo, so it is a second call carrying indices rather than a briefing that files itself: a briefing
which became tickets without anybody choosing would be a backlog this system invented. Filing is
idempotent against the opportunity's own words, because a briefing retried because its answer was
slow is a briefing retried for a reason that happens.

**And what a real briefing found, twice, about the same model on the same repository:**

| | first briefing | after the paths were listed |
|---|---|---|
| the repository it described | *"a small web application… `src/App.jsx`"* — a React app the repository is not | *"a Next.js web application… cookie-session auth"*, which is what it is |
| citations | `src/App.jsx` × 4 — **a path the repository does not have** | 31 real files, every one proved |
| opportunities | 0, after the refusal corrected it | 5, specific enough to file |

The first briefing invented `src/App.jsx` in all four opportunities. **Nothing caught it, because
the check read `evidence_files` — a field the model cannot write — and an empty list proves
nothing.** The check now reads what the model wrote, and the prompt lists the sixty paths a
citation may name, which turns citing from a recall into a lookup.

---

## Where this came from

This is an assembly of two half-products that are each other's missing half, and being explicit
about that is more useful than pretending it was written from nothing.

| | |
|---|---|
| **`ai-sdlc-os`** | the engine, unchanged and unrewritten. Eight agents with real prompts, the GitHub tools, the containerised test runner, the delivery, the repair supervisor, LangGraph. It has opened three real pull requests on a public repository. What it had not: any way to see or start a run — its own `AGENTS.md` says "What is genuinely not built is the API and the CLI" |
| **`ai-sdlc-bestof`** | the interface, unchanged and unrewritten. The SQLite store, the five-column board, the FastAPI over it, the browser UI, the event stream, the derived column rule. What it had not: a way to start a run, any GitHub tool, and six of its eight stages had no agent at all — it was a board over a store nothing wrote |

So the engine got the board and the board got an engine. The parts written here are the ones
neither had:

- `application/a_run_being_assembled.py` — the composition root. Before this, the only code that
  ever assembled a run was a test in a real-dependency tier, which is a test suite doing a
  product's job.
- `application/the_runs_this_process_is_holding.py` — the bridge. A run is a compiled graph with
  a checkpoint in memory; this holds it between the moment it parks at a gate and the moment
  somebody answers, and it is where a decision enters.
- `store/what_a_run_records.py` — five write-through recorders, hung on the five places the
  engine already had a function that made something a fact. **No new nodes and no rewiring.**
- `web/the_api.py` — `POST /api/runs`, the endpoint neither project had.
- `cli.py` — the two commands.
- the form on the board, and the run-status line that joins what is on disk to what is in memory.

### Two more bugs, found by running rather than reading

**`the_lifecycle` took a `plan_the_clone` parameter and one of its own wiring functions ignored
it**, reading the module constant instead. The parameter was a claim about the function that was
false, and nothing could have found it but a test that passed a clone planner and watched the
real one run instead.

**Two locks on one SQLite connection.** The board and the run each had their own, which is the
same as no lock at all: `InterfaceError: bad parameter or other API misuse` from a query that
worked a moment earlier. There is now one lock, taken by both, in one module.

---

## Every issue and pull request carries the project's full name

**An issue lands in a queue among hundreds and a pull request in a review list among dozens**, and
with nothing on them saying which project asked, the only way to tell a briefing's issue from a
person's is to read every body and recognise the formatting — which stops working silently the
moment the formatting changes.

**The tag is *this system's* project — not the repository it files into.** This is the whole rule
and it took six attempts to get right, so it is written plainly. **A tag answers *who produced
this*, and that is a fact about the codebase, not about where the work landed.** The first version
derived it from the repository being filed into, so a briefing on somebody's project opened issues
there tagged with *that project's* name — which looks like a tag about their work, answers nothing
about which tool wrote the issue, and would make two automations filing into one repository
indistinguishable to a person reading the queue.

**So the function takes no repository at all.** Taking one is what invited the mistake: the
argument was there, it was the only name in scope, and it was the wrong name. An argument nobody
needs is an argument that will be used wrongly. The name is a constant, and `AISDLC_PROJECT_NAME`
overrides it for a deployment that forks this.

**It is the full name, `owner/name`, not the bare name** — a repository name is only unique within
an owner, and two forks of one project share a name.

**One rule, one module, read by both writes.** `github.open_an_issue` and
`github.create_pull_request` are the only two things here that write to a repository somebody else
owns. A rule stated in each is two rules that drift — somebody tags issues and forgets pull requests,
and every filing after that is half-tagged, with neither tool individually wrong. A test reads both
against the same rule.

**And the label is created first, because GitHub refuses an issue carrying a label it has never
heard of.** A 422 there reads as "the delivery failed" and costs somebody twenty minutes of
reasoning to diagnose. A 422 to the *creation* is success, because a label that already exists is
exactly what GitHub says when it refuses to create one — which is what makes filing several issues
against one repository work at all.

**A pull request is labelled *after* it is opened, and that is not a style choice.** GitHub's
create-pull-request endpoint does not take `labels`. It does not reject the field and it does not
warn: it answers **201**, opens the pull request, and discards the labels. A pull request *is* an
issue in GitHub's data model, which is exactly why labels work on one and silently do nothing on
the other. **Every pull request this system opened for a week arrived untagged while all eleven
assertions about it passed**, because every one of them was about the request rather than about the
pull request. The label now goes on through `POST /repos/{owner}/{name}/issues/{number}/labels`,
which is where GitHub keeps a pull request's labels at all — and this is written down beside the
code that was wrong, because the test that found it is the whole argument for testing a thing
against the thing it talks to.

**It costs one write per delivery, and after the first that write is refused.** A deployment running
ten deliveries against one repository makes ten label requests and GitHub answers nine with 422.
Caching it would avoid those, and would also mean a label deleted halfway through a run's life is
silently absent from every filing after it — found out by a person filtering by project and seeing
nothing. A wasted write is visible in a rate limit; a stale cache is visible in a wrong answer.

**And a deployment that cannot create labels still delivers.** Labels live on GitHub's *issues*
API: opening a pull request needs `pull_requests: write`, creating a label needs `issues: write`,
and a deployment provisioned for delivering has no reason to hold the second. **The first version
of this rule refused every delivery on such a deployment, with an error about a label, twenty
minutes after a run had pushed a branch** — a worse outcome than an untagged pull request by a
distance nobody would defend. So a tag that cannot be created is not used and the pull request still
goes out, untagged. The tag is how a person finds the work; the pull request is the work.

**And it is proven against real GitHub, not only against a stand-in.**
`tests/test_the_tag_reaching_real_github.py` files one real issue, reads it back through GitHub's
own record of it, asserts the label is on the thing rather than in the request, and closes it
again. It skips loudly unless a deployment states both `GITHUB_TOKEN` and
`AISDLC_THE_REPOSITORY_TO_FILE_AGAINST`, because a test that files into a repository nobody named
writes to a stranger's board. **It is what found the pull-request bug above**, by opening a real
pull request and reading GitHub's record of it rather than its answer. **It also opens, labels, reads back, closes and deletes a real pull request**, and that is the
half which was broken: `labels` in the create-pull-request payload is accepted and discarded, so
eleven request-level assertions passed while every pull request arrived untagged. **The branch is
genuinely deleted; the pull request is only closed**, because GitHub has no endpoint for deleting
one — which is the same kind of claim as the field it does ignore, and this file held one too.

**Each run leaves one closed issue and one closed pull request behind.** Both are opt-in, and both
are the visible record that the tag arrived; a deployment running these on every push accumulates
them, which is a cost to know about rather than a reason not to file.

Set `AISDLC_PROJECT_NAME` when a project spans repositories or a monorepo's repository name is the
container rather than the thing being worked on.

## main is protected, and it was not for the first hour

**`main` accepted a direct push for the first hour of this repository existing**, and I proved it
by pushing a stray line straight to it while testing something else. The line is gone. What
matters is the three things that took to fix, and each was found by testing the rule rather than by
trusting the response:

| what was wrong | how it showed up |
|---|---|
| `enforce_admins: false` | the protection was on and the push went through anyway — **the owner is the one person it does not stop** |
| `required_approving_review_count` defaulted to 1 | every pull request sat `BLOCKED` forever, because nobody can approve their own |
| the required context was `gate` | the workflow's name, while GitHub's status context is the **job's** name, `the_gate` — so the requirement could never be met and every merge was blocked |

**What is required now:** a pull request, the `the_gate` check green, up to date with `main`, stale
approvals dismissed, no force pushes, no deletions, **and it applies to administrators** — verified
by pushing again and reading `GH006: Protected branch update failed`.

Not required: a second human. One approval was the default and it makes a one-person repository
unmergeable, which is not a safety property.

## A briefing reads the issues, and filing refuses a duplicate anyway

**Two changes, because one of them is not enough.**

**The briefing is shown what is already tracked.** A model told to "propose work" proposes work it
knows about — it is a retrieval task and it recalls a different project. `github.list_open_issues`
reads the open issues of whatever repository is being briefed, and the prompt lists them and says
not to propose them again. **No credential**, because issue listing is public where filing is not:
a briefing is a reading operation all the way through, and making it need a token would put the
harmless half of creative mode behind the same door as the half that touches a stranger's board.

**And filing refuses a duplicate anyway.** A prompt is not a check — this repository has a standing
rule about that, learned from a model citing a file that did not exist while being told to cite
real ones. The model may ignore the list, misread it, or re-word the work it names, and **an issue
that is opened and then found to be a duplicate has already landed in somebody's queue** and can
only be removed by a person closing it. So the refusal is in `filing_what_the_briefing_found`,
ahead of `open_the_issue`.

**The comparison is about the work, not the string.** Two titles for the same work rarely match as
text, so this compares the words they share — after dropping the words that appear in nearly every
title, because "Add a test" and "Add a health endpoint" share `Add` and nothing else, and refusing
the second because of the first would make creative mode useless on any repository with a backlog.
Two meaningful words in common is the threshold. **That is a judgement, and the cost of being wrong
is asymmetric**: a duplicate is noise in a queue, a dropped opportunity is work nobody hears about.

**A repository with no issues says so in one line** rather than saying nothing, because "nobody has
filed anything" and "you were not shown anything" read identically to a model and only one is true.

**And GitHub refusing to answer refuses the briefing**, rather than returning an empty list. An
empty list reads as "nothing is tracked", which is a fact — and a false one would mean proposing
work a team has already agreed to do, which is the exact failure this is for.

**The limit, named.** The list is read once, at briefing time. An issue filed between the briefing
and a person's pick is not in it.

## What is not built

Stated rather than left to be discovered.

- ~~**Every repair in this system crashed the run.**~~ **Fixed, and it is the most important
  finding in this repository's history, because it made the whole supervisor unreachable.** The
  node that makes the change returned a plain state update on success and a `Command(goto=...)` on
  a repairable refusal — *and* the graph also carried a static edge out of that node. A
  `Command`'s `goto` and a static edge from the same node **both fire**. So a refusal did not
  divert the run: the run went to the supervisor *and* carried on down the ordinary path, the two
  arrived at the same node in the same step, both wrote `requested_stage`, and LangGraph refused
  it:

      At key 'requested_stage': Can receive only one value per step.

  The refusal was correct, the routing was correct, the supervisor ran, and the run still died —
  **at the moment the repair was being performed, with a message about concurrent writes rather
  than about the repair.** Every refusal-routing test here passed, because they call the function
  and read the `Command` it returns; the defect was entirely in the wiring, and no unit test
  builds the graph. The node now names its own destination on both outcomes and carries no edge,
  which is what the supervisor already did and for the same reason.
- **A repairing run does re-present the verification gate, and that is correct.** A person
  approved it *for a change*; the run then found the change did not happen; asking again is the
  only honest thing left, and delivering on that approval would be delivering something nobody
  saw. It is why a whole-run test cannot use the "nobody has answered yet" wait for this shape.
- ~~**Open: a run that repairs does not reach `DONE`.**~~ **False, and it was this repository's
  own test lying.** A repairing run reaches `DONE`, like any other. The run that appeared to stop
  at `AWAITING_HUMAN_APPROVAL` was answering every question twice — the graph clears a question
  when it records the answer, which happens after the POST returns, so the second read is the race
  every other test in the file works around — and a second answer to the *delivery* gate left the
  run approved-everything and delivered nothing. Three attempts at that test failed the same way,
  each looking like impatience rather than the wrong question: answer-whatever-appears,
  count-sixteen, and report-finished-by-returning-`None`. The fourth used the pattern the other
  tests already use, and the defect was not there.
- ~~**The supervisor still has not fired inside a whole run.**~~ **It has** — on a whole run
  through the real graph, and on that run it found the wiring was broken in a way no routing test
  could see.
- **The rule that would catch an unobservable change was never wrong — it was never asked.** The
  check that a test passes with the change undone runs the *whole suite* with the change removed,
  precisely so it can ask "does anything notice". But it returns early when the plan named no
  test, on the reasoning that a plan adding no test has nothing to observe the change. That is true
  of the plan's tests and false of the suite, and it is the exact case that mattered: the Dockerfile
  run's plan named no test, so the one rule that could have said *"nothing here notices this
  healthcheck"* stayed silent and a policy had to notice it by reading two suite outputs.
  **The docstring now argues against its own early return**, and
  `tests/test_whether_anything_observed_the_change.py` pins the gap so whoever closes it is closing
  something named.
- **Not fixed, because the obvious fix is worse.** Deleting the early return refuses every
  documentation change this pipeline is asked for — the truthful answer to "did anything notice?"
  about a README is no, and there was nothing wrong. Separating a silent change from a harmless one
  needs to know whether the change touched something a suite could read, and
  `refuse_a_change_nothing_observed` is not told what the change wrote. That is a design decision
  with a cost on both sides, and it is written down rather than made overnight.
- ~~**An end-to-end proof of the *delivery* repair was attempted and abandoned.**~~ **It was the
  harness, and the answer was to stop using it.** The board clears a question before it records the
  answer, so a run that repairs and re-presents the verification looks identical to the race every
  other test in that file works around. Four shapes of loop were tried — count the gates, count
  twice the gates, report-finished-by-returning-`None`, and count quiet moments per artifact — and
  each failed on its own cleverness rather than on anything to do with the graph. **The graph
  compiles with its own checkpointer and its gates ask with `interrupt`, so the whole run can be
  walked without the board at all**: stream it, answer with `Command(resume=...)`, stream again.
  Nothing polls, so there is no race to lose. The delivery repair is now proved on a run that goes
  all the way — suite red, delivery refuses, supervisor sends it back, change made again, suite
  green, run reaches `DONE`.
  **And re-adding the edge the delivery node used to carry makes that test fail**, which is the only
  thing that distinguishes a check that is armed from one that is merely green. Not with the error
  the implementer's defect produced — this one dies of `DONE cannot move to AWAITING_AGENT_PICKUP`
  rather than of `Can receive only one value per step`. Both are a dead run and both are invisible
  to a unit test, which is the whole point of walking the graph.
- **And a live model has now made it seven gates on the same repository, twice refused by the
  policy and never once by an exception.** The first refusal is still the strongest thing in this
  file:

  > The plan names `Dockerfile` as the only file to change and explicitly declares `tests_to_add`
  > as empty, so nothing in this run will ever exercise the healthcheck it is adding. **A
  > `HEALTHCHECK` whose path, port, or interval is wrong does not fail loudly — the container
  > simply reports unhealthy forever** — and this plan contains no build-and-run step confirming
  > the endpoint exists and that the container reaches "healthy".

  The second is the same judgement made independently, at the verification gate, by reading the
  suite rather than the plan: the two runs are indistinguishable, and the nine integration tests
  that would exercise the interval were skipped in both. **A run whose plan adds no test is a run
  the engine cannot check**, because the check that a test passes with the change undone needs a
  test to undo it beside — so a genuinely unobservable change is caught by a person or a policy
  reading the evidence, and not by the machinery. That is a design decision with a real cost, and
  the cost is that the last line of defence is a judgement rather than an assertion. It has been asked, by a real model,
  with a real card and a real refusal, and it answered correctly — and its routing is now covered
  for all four refusals that reach it. What has not happened is an end-to-end run tripping one,
  and the reason is now clear rather than mysterious: **a gate refusal stops the run by design**,
  and both runs refused at a gate, where the supervisor is deliberately not involved. Reaching a
  node refusal needs the plan to be *right* and the implementation to be *wrong*, which is not a
  thing to ask a model for on purpose. `tests/test_the_supervisor_deciding_what_to_repeat.py` and
  a whole run through the real graph both drive the routing; what neither can do is make a real
  model misbehave on demand.
- **A durable checkpointer.** Runs are held in memory, so **a restart loses every parked run**.
  The register, the clone and every artifact survive; the graph's place in the pipeline does
  not. What *is* built is the honesty about it: the API says whether this process is holding a
  run at all, and a card for a run nobody is in reads *"the process this run was in has gone —
  ask for it again to start another attempt"* rather than *waiting for you*. Before that, the
  board invited a decision on a gate that would then answer `410`, which is a button that
  discards what is pressed into it. Making the memory durable is a real change with a real cost;
  making the board stop lying about not having one was the part that was owed today.
- **Nobody has filed a real briefing.** The filing path is proven with a stand-in for GitHub's
  issue API, and the four refusals around it were checked against a live server against a real
  briefing — but opening five issues on a third party's public repository is an outward-facing
  write with no undo, so it is the one thing left deliberately untriggered. Start a server with
  `AISDLC_CREATIVE_MODE=on`, press the button, and tick the boxes.
- **Authentication.** There is none. Anybody who can reach `127.0.0.1:842` can start a run on a
  real repository and answer every gate on it. The loopback address is the whole of the
  boundary, and a deployment that needs it exposed has to put its own authentication in front.
- **A browser test tier.** The UI is served and the JSON it renders is proven; nothing drives a
  real browser. The two defects the board had when it arrived — a refused gate drawn in the
  colour and the word of an approved one, and no way to start a run at all — were found by
  reading the source, and the first is fixed. The third was found by looking at a real card, which
  is `on __interrupt__`.
- ~~**Every unit and graph test the engine had.**~~ **The per-agent contracts are proven here
  now, and the tier that proves them is the thing this repository did not have.** Its 686 unit
  tests, 150 graph tests and 45 end-to-end tests were still not copied, and the claim below used
  to be that the per-agent contracts could only be proven in `ai-sdlc-os`. That was a real gap and
  it was the whole reason this copy exists: **every claim this repository made about discovery, the
  requirements, the QA plan, the architecture report, the security report, the plan, the change and
  the repair supervisor was a claim about a whole run**, and a test reading a run's end state cannot
  say which stage produced what. A stage that stopped working would be a stage that fails silently
  inside a pipeline still reaching its next gate.

  So the real tier is split the way a failure is cheapest to find: **one file per stage, each
  proving that stage alone against a real model and a real clone, and then the handovers in pairs.**
  A defect inside one agent's contract is minutes against a whole run's tens of minutes, and the
  pair files cover the seams the isolated ones cannot see — that a real `Requirements` is
  something a real QA analyst accepts, and that nothing the first stage said is contradicted by the
  second.

  | the default suite, no network and no credential | what it holds this repository to |
  |---|---|
  | `test_a_run_from_a_request_to_a_delivery.py` | a run from a sentence to a delivery, and both repairs walked end to end |
  | `test_what_two_real_runs_found.py` | the defects two real runs found, and the inspections that carry the code now |
  | `test_the_supervisor_deciding_what_to_repeat.py` | every refusal routes to the supervisor, and no node chooses a destination *and* carries an edge |
  | `test_a_repository_briefing_itself.py` | a repository briefs itself, and filing is refused without a credential |
  | `test_the_tag_this_system_leaves_on_what_it_writes.py` | every issue and pull request carries the project's full name, or still goes out untagged |
  | `test_whether_anything_observed_the_change.py` | the rule that catches a change nothing observed, and its one gap |
  | `test_a_real_model_judging_a_real_refusal.py` | a real model's judgement inside a real graph; skips loudly without a credential |
  | `test_the_readme_names_what_this_repository_holds_itself_to.py` | that these tables name every test file, which this repository has now got wrong three times |
  | `test_the_tag_reaching_real_github.py` | that the tag is on a real issue and not only in a payload; files one and closes it — it found the pull-request bug |
  | `test_work_already_tracked_is_not_proposed_again.py` | that a briefing reads the repository's open issues, and that filing refuses a duplicate before anything is opened |
  | `test_the_default_suite_reads_no_deployment_file.py` | that importing the real tier loads no `.env`, which is the claim `gate.yml` makes in a comment and a real run made false |
  | `test_a_field_of_whitespace_is_absence.py` | that a field holding `" "` is neither an answer nor an absence, asked of every field of the three artifacts that share the rule |
  | `test_a_file_a_plan_brings_into_being_is_committed.py` | that a file a plan creates is in the commit the delivery pushes, asked of `git show` and not of the arguments |
  | `test_a_plan_that_adds_a_file_is_a_plan.py` | that a plan whose whole content is a new file is a plan, and that its refusal names every field it can be empty of |
  | `test_a_test_at_the_repository_root_is_judged_too.py` | that a test at the repository root is judged by the runner's own `include` lines like any other directory |
  | `test_every_field_a_stage_asks_for_is_a_field_the_answer_has.py` | that every stage's question names only fields the artefact has — the planner asked for `what_it_expectes_next`, which no type has |
  | `test_a_build_system_names_what_the_build_runs_on.py` | that the question asks what the build runs on, and that `build_system: npm` is refused — two real runs were stopped at their first gate over that field |
  | `test_what_an_inspection_says_it_did_not_show_is_every_file_it_did_not_show.py` | that every source file not read is named under *what was not shown*, including the ones a name filter never selected |
  | `test_a_reader_does_not_commit_a_write_it_did_not_make.py` | that a reader of the register does not commit a write it did not make, which is what every `_prepared` did while a board polled a run |
  | `test_a_supervisor_that_cannot_answer_stops_the_run_with_a_reason.py` | that a repair supervisor whose answer cannot validate stops the run by refusing, naming the agents the model forgot, and leaves the reason on the card |
  | `test_every_stage_reasoning_about_a_file_is_shown_it.py` | that every stage reading a repository is shown what is *inside* the files, and that the set of such stages is derived from the signatures rather than written out |
  | `test_the_tables_are_read_rather_than_kept_up_to_date.py` | that the tables here are read rather than trusted — and the third count this repository let go stale |

  | the real tier, a real model and a real repository, opt-in with `-m e2e` | what it holds this repository to |
  |---|---|
  | `test_discovery.py` | that a real model reads a real repository, and that every path a report names is a file the clone holds |
  | `test_analyze_the_repository.py` | that a real analyst answers a real request, and that every ambiguity says who can settle it |
  | `test_analyze_the_requirements.py` | that a real QA plan is built from approved requirements and names no file in a repository it was never shown |
  | `test_analyze_the_architecture.py` | that every package a report claims at a named version is in the manifest, and that a module list is a judgement nothing here can grade |
  | `test_inspect_for_security_risk.py` | that no finding's evidence is a file the run never saw, and that every finding is weighed on all five of its fields |
  | `test_plan_the_change.py` | that a real plan names only paths the clone holds or is allowed to create, in a directory the suite collects |
  | `test_implement_the_plan.py` | that a real model's change lands on the disk holding exactly what it proposed, and that nothing outside the plan was written |
  | `test_apply_the_plan.py` | that the change is committed under the agent's name, the suite is asked on both sides, and a change nothing observed is refused |
  | `test_supervise_a_repair.py` | that a real model's verdict names a node the compiled graph actually has, and that the run did not die of the wiring |
  | `test_review_an_artifact.py` | that a real model's decision is signed `autopilot:<policy>` and never as a person, at the version that was presented |
  | `test_brief_this_repository.py` | that every opportunity cites a file the clone holds, and that the run's own judgement is not the type's default |
  | `test_propose_the_work_this_repository_shows.py` | that a proposed request carries no address, and that a title without a body is refused |

  **And the pairs: two neighbouring stages, both on real models, everything else mocked.** Four of
  the seven neighbouring pairs hand *nothing* over — four stages are given the same clone, and the
  planner is given requirements and not the security report a person approved four gates earlier.
  **A pair that shares a substrate cannot be wrong *about* what its neighbour concluded, and can be
  wrong about the same file from a different starting point** — which is what a gate holding both
  artifacts is for, and what nothing in the graph compares. So each pair asserts both halves: that
  the second stage was *not* shown the first stage's conclusion or its judgement, and what a
  person holding both cards can mechanically check.

  | a pair, both stages real | what it holds this repository to |
  |---|---|
  | `pairs/test_the_requirements_into_the_qa_plan.py` | the one true seam: a real `Requirements` is accepted by a real QA analyst, every admitted ambiguity reaches the question, and no judgement does |
  | `pairs/test_discovery_into_the_product_analyst.py` | the analyst is not handed the report, so the requirements cannot be a summary of what the repository *is*; the derived evidence links are the sharpest half, since nothing on disk can hold one |
  | `pairs/test_the_qa_plan_into_the_architecture.py` | the architect is handed the clone, not the plan, and so is shown no source and may say nothing about test coverage |
  | `pairs/test_the_architecture_into_the_security_report.py` | the security analyst reads the inspection that carries file *contents* and names what it left out — the asymmetry that bit a real run |
  | `pairs/test_the_security_report_into_the_plan.py` | the sharpest pair: the planner never sees the report, so a plan *can* contradict a finding a person approved, and nothing downstream compares the two |
  | `pairs/test_the_plan_into_the_implementation.py` | the implementer wrote what the plan named and nothing else, and never saw the plan's own judgement |
  | `pairs/test_the_implementation_into_the_verification.py` | the change was on the disk **at the moment** the second suite call was made, read out of a recording witness rather than inferred afterwards |

  **And the table is checked rather than trusted**, by that last row. The tag feature landed with
  eleven tests and a commit message describing a README section that was never written — the edit
  anchored on a heading belonging to another repository, so it silently did nothing, and the commit
  passed because an unrelated line in the same edit did land. Two days later this table still said
  "four test files" when there were six. **Both times a count went stale and nothing noticed, and
  the third time the table said the per-agent contracts were unprovable here four days after a tier
  that proves them landed.**
- **The quality gates the engine was built under.** Strict TDD, the readability guards, the
  glossary guard, the per-cycle commit discipline, `mypy --strict`, the e2e and container tiers.
  This repository was assembled for speed and carries `ruff` and a non-strict `mypy`. That is a real
  trade: the engine's safeguards are not reproduced here, and the engine is where they still run.

---

## Four real runs against `wellbeing-tracker-public`, and every one of them stopped at a gate

**The honest count is zero pull requests.** Four runs, `AISDLC_APPROVAL_POLICY` answering
unattended, decisions recorded as `autopilot:overnight-autopilot` and never as a person — and
four refusals, each one specific, each one correct, and **three of the four about the request
rather than about the system.** That distinction is the finding, so it is made first and it is
made about my own runs.

**Run 1, on this repository rather than the intended one, and the refusal was right to stop it:**

> The artifact asks for a README line naming the runtime and version, while its own ambiguities
> record that `.github/workflows/gate.yml` only runs `setup-uv` + pytest/ruff/mypy and installs no
> Node, and that no `package.json` or `.nvmrc` exists — so the premise in the work item title
> (name the Node version) has no referent, and requirements 2 and 3 are jointly unsatisfiable
> under it.

A Python repository does not have a Node version. **The policy compared the requirement against
the repository and refused, which is the loop working.** I had pointed the run at the wrong
repository.

**Run 2, on the right repository. The request asked for two mutually exclusive things:**

> Criteria 1–4 and criterion 5 are mutually exclusive branches — the same change cannot both list
> README in `git diff --name-only` and have an empty diff.

`wellbeing-tracker-public` has no `README.md` at all; its `Dockerfile` pins `node:22-bookworm`. I
wrote *"if the repository already states it, do not change anything"* and that branch is
unsatisfiable alongside the other. **Correct refusal, and it named which two criteria collided.**

**Runs 3 and 4 are the ones that are about the system, and the second one is the finding worth
keeping.** Both asked for an `engines` field in `package.json` naming the Node version. Both were
refused at **discovery** — before any of the stages this repository spent a week proving — with:

> The report never records the runtime floors that would bound an engines range … Add a finding
> stating whether package.json already declares engines and which Node versions the repo actually
> builds and runs against (with evidence links) before this run continues.

**`DiscoveryReport` has no field for what a repository declares about its runtime.** It has
`build_system`, `ci_system`, `languages`, `frameworks` — and a work item *about a declared runtime*
is one the artifact cannot serve, because there is nowhere in it to put the answer. The policy is
asking for a field that does not exist, and it is right to: a person at that gate cannot rule on
"add the version this project needs" while holding a report that never says what the project
needs. **This is the same shape as the engine's own recorded finding** — three of four analysis
artifacts cannot cite a file, and the record says the cycle that reverses it *starts by changing
the glossary*. It starts there here too.

**And the third run's refusal caught something the inspection had already admitted.** The report's
`suggested_changes` told `web-app/src/lib/db.js` to resolve its SQLite path the way
`tests/e2e/infra/env.ts` injects `DATA_DB` — and the report's own `architecture_summary` says that
file *"the inspection names but does not show"*. **The inspection did its job: it ends by naming
what it left out, exactly so this is visible. The model reasoned about a file the run never read,
and a second model caught it by reading the report against the report.** Two independent
mechanisms, neither of which existed before the file-contents work.

**What the four runs do prove, then.** Six agents ran on real models over a real clone and
produced artifacts a policy read and judged in detail — the discovery reports name real files with
clickable links, the requirements quote a two-stage Dockerfile and a three-way test split, and
every refusal names a specific criterion or a specific missing field rather than saying
"insufficient". **The gate is not a formality and the artifacts are not noise.** What is missing
is one field on one artifact, and the run is stopped until it exists — which is the correct
behaviour and also means **autopilot mode delivers nothing on any work item about a declared
runtime**, the same conclusion the six runs in `ai-sdlc-bestof-fast-selfaware` reached.

**Not done, and not going to be dressed up:** no pull request was opened, no branch was pushed,
and the interactive path — the only mode in which this repository has ever delivered anything —
needs a person at eight gates. Turning the finding above into a field is a change to what
`DiscoveryReport` *is*, which is a glossary decision rather than a test.

---

## Six real runs, and every refusal names what I should have written instead

Runs 5 to 10 continued the section above on the same repository, and they are a different kind of
finding from runs 1 to 4, because by the fifth I had stopped asking for things and started asking
for **one change with a provable acceptance criterion**.

**Runs 5 and 6 were the same request and they were refused for two different reasons, both of
them right.** The work was to add a `npm run typecheck` step to `.github/workflows/ci.yml` and a
unit test that fails if it is removed. The repository has the script, the workflow does not run
it, and the gap is real. Two runs, two refusals, at the requirements gate:

> **Run 5**, on an artifact that contradicted itself: *Requirement 1 fixes the typecheck step in
> the same job and install as `npm test`, while ambiguity 3 declares that exact placement
> undetermined and routes it to a person — the artifact both decides and blocks on the same
> question, so an implementer must either halt or pick a side its own text reserves for a human.*

That is the one I would not have predicted, and it is the sharpest thing this gate has ever said
about this repository. `Requirements` has a list of requirements and a list of ambiguities, and
**nothing checks that the two do not disagree.** An artifact that fixes an answer in one field
and defers the same answer in another is structurally impossible to satisfy, and it reached a
reviewer whole.

> **Run 6**, on a criterion no in-repo change can decide: *the third — "a commit that introduces
> a TypeScript type error under `web-app` produces a failing workflow run" — is not decidable by
> anything this run writes: it needs a hosted Actions run on a pushed commit.*

Also right, and it named the repair: rescope the criterion to something the suite can assert
in-repo, or move it out and call it a post-merge check for a person.

**So the honest count for this deployment is six runs, six refusals, zero deliveries, and every
single refusal was correct.** Two runs ago I wrote that the gate is not a formality. This is the
measurement that says it is not a formality *and* that **autopilot cannot deliver on this
repository as it stands**, because the two things that decide a delivery are a plan and an
implementation, and the plan is exactly what the gate refuses when it contradicts itself.

**What I have not done, and will not pretend otherwise:** no pull request has been opened by this
branch. The one that exists on the upstream ([#9](https://github.com/paligakrzychu/wellbeing-tracker-public/pull/9),
`DELIVERY.md`, +39) was opened on 2026-09-28 by the frozen source this repository was forked from,
two weeks before this branch existed. Counting it as a delivery of mine would be the exact
"decision that cannot be found later is not a record, it is a claim" mistake this repository is
built against.

**And the finding worth keeping is narrower than "autopilot delivers nothing."** It is that the
gate refused correctly in **six cases out of six** without ever refusing for the wrong reason —
never for "insufficient", always naming a specific criterion, a specific missing field, or a
specific pair of colliding statements. A gate that refuses everything also refuses everything.
This one refused everything *and was right every time*, and the difference is the thing that took
twelve runs to establish.

---

## The plan cannot say what the change is, and the gate refused it for exactly that

Run 10 got to **gate six of eight** — further than any run on this branch — and was refused on a
plan that had no defect I had thought of:

> The plan only enumerates paths: it never states the workflow step to be inserted into
> `.github/workflows/ci.yml`, never checks that a `typecheck` script exists in `package.json`
> (and `package.json` is absent from `files_to_change`, so an undefined script would fail CI),
> and its single test asserts positioning after an `npm test` step whose presence in `ci.yml` the
> plan never establishes. Before this runs, it needs the actual YAML step plus confirmation of
> both scripts in the current workflow/package manifest.

**Every clause of that is right, and every clause of it was designed in.** `ImplementationPlan`
has exactly five fields and all five are lists of names:

```text
files_to_change   files_to_add   tests_to_add   dependencies   migrations
```

There is nowhere in the artifact to say *what* the change is. And the planner's prompt is one line
long on this subject — `plan_the_change.py:202`:

> `Plan only. Do not write, edit or suggest the contents of any file.`

So a reviewer at gate six is asked to rule on **five lists of filenames and nothing else**. For a
one-line YAML step that is not a thin plan, it is not a plan: `ci.yml` appears in `files_to_change`
and a reviewer can learn from this artifact that the run intends to touch a workflow, and not one
other thing about it. **The gate before code is written is a gate over a list of paths.**

**And the instruction that forbids it has no test behind it.** §0.4 of this repository's own
rules says that if a prompt has to *forbid* something, a test must *assert* it, and that prompt
begging is not verification. I grepped for the line: it appears once, in the prompt, and nowhere
in `tests/`. So it is not a rule anyone is keeping — it is a sentence, and the gate has just
demonstrated that it wants the opposite of what the sentence says.

**This is the runs 3 and 4 finding again, one stage later and worse.** Those runs were refused
because `DiscoveryReport` has no field for what a repository declares about its runtime, so a
reviewer holding the artifact cannot rule on the question. Here it is `ImplementationPlan` with
no field for what the change is — and gate six is the one immediately before code exists. The
precedent for this shape is recorded already: adding the field starts in
`docs/domain-glossary.md`, not in a test.

**What I did not do.** I did not widen `ImplementationPlan` on the strength of one refusal. It is
a change to what the artifact *is*, it changes what a person approves at a gate, and the planner
prompt forbidding contents may have been protecting something I have not measured yet — the
implementer being *told* what to write is a different prompt from the planner being *allowed* to
say it. That is a decision about the glossary and a cycle of its own, recorded here rather than
taken quietly at the end of a run.
