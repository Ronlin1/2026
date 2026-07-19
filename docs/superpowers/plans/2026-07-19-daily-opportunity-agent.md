# Daily Opportunity Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a daily GitHub Actions agent that commits up to five verified opportunities directly to the README.

**Architecture:** A dependency-free Python script owns source collection, deadline parsing, duplicate detection, and README mutation. A GitHub Actions workflow runs the script daily and commits only when `README.md` changed.

**Tech Stack:** Python 3.11 standard library, `unittest`, GitHub Actions, Git.

## Global Constraints

- Commit directly to `main`.
- Add at most five opportunities per daily run.
- Only add opportunities whose real deadline is after the daily run date.
- Follow the existing README checklist format: `- [ ] Name https://link MON DAY`.
- Skip duplicates and expired opportunities.
- Do not require OpenAI, Gemini, or any other LLM API key for v1.

---

### Task 1: Test README Mutation Rules

**Files:**
- Create: `tests/test_update_opportunities.py`

**Interfaces:**
- Consumes: `Opportunity`, `extract_deadline_date`, `format_opportunity_line`, and `insert_opportunities` from `scripts.update_opportunities`.
- Produces: Executable tests for the updater behavior.

- [x] Write failing tests for deadline parsing, existing month insertion, missing month creation, and duplicate detection.
- [x] Run `python -m unittest discover -s tests -v` and confirm failure because the updater module is not implemented yet.

### Task 2: Implement Updater Script

**Files:**
- Create: `scripts/update_opportunities.py`

**Interfaces:**
- Produces: CLI command `python scripts/update_opportunities.py --max-items 2`.
- Produces: `Opportunity(title: str, url: str, deadline: date, source: str)`.
- Produces: `insert_opportunities(readme: str, opportunities: list[Opportunity], today: date, buffer_days: int) -> tuple[str, list[Opportunity]]`.

- [ ] Implement deadline parsing with common opportunity deadline phrases.
- [ ] Implement duplicate detection using normalized URLs and titles.
- [ ] Implement month section insertion using the README's current details pattern.
- [ ] Implement feed and page fetching using `urllib.request`.
- [ ] Run `python -m unittest discover -s tests -v` and confirm all tests pass.

### Task 3: Add Daily Workflow

**Files:**
- Create: `.github/workflows/daily-opportunities.yml`

**Interfaces:**
- Consumes: `scripts/update_opportunities.py`.
- Produces: A daily scheduled workflow with manual dispatch.

- [ ] Configure cron for `37 5 * * *` UTC.
- [ ] Grant `contents: write`.
- [ ] Run the updater with `MAX_ITEMS` defaulting to `5`.
- [ ] Commit and push only when `README.md` changes.

### Task 4: Verify and Publish

**Files:**
- Modify: all files from previous tasks.

**Interfaces:**
- Consumes: tests and workflow.
- Produces: pushed direct commit on `main`.

- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Run `python scripts/update_opportunities.py --dry-run --max-items 2`.
- [ ] Run `git diff --check`.
- [ ] Commit changes.
- [ ] Push `main` to `origin`.
