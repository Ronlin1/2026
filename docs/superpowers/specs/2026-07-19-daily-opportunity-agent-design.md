# Daily Opportunity Agent Design

## Goal

Build a daily GitHub Actions agent that commits one or two credible new opportunities directly to `README.md` in the same checklist style already used by this repository.

## Scope

The first version uses public opportunity RSS/Atom feeds and page text. It does not require Gemini, OpenAI, or any paid search API. If an LLM API key is added later, it can improve deadline extraction and filtering, but the baseline agent must run without one.

## Behavior

- Run once per day from GitHub Actions, plus manual `workflow_dispatch`.
- Read `README.md`.
- Collect opportunity posts from trusted feeds for fellowships, grants, hackathons, scholarships, awards, challenges, residencies, accelerators, internships, conferences, and summits.
- Extract a real 2026 deadline from feed text or the linked page.
- Apply the repository's existing buffer rule by listing a date three days before the detected deadline.
- Add at most two new rows per run.
- Skip duplicate titles or URLs already present in `README.md`.
- Keep the current Markdown row format: `- [ ] Name https://link MON DAY`.
- Create a missing month section using the existing `<details open>` pattern.
- Commit directly to `main` only when `README.md` changes.

## Guardrails

- Do not make empty "activity" commits.
- Do not add undated opportunities in the daily month sections.
- Do not add expired opportunities.
- Do not add rows that duplicate an existing title or link.
- Keep the implementation dependency-free so the scheduled job is simple and reliable.

## Files

- `.github/workflows/daily-opportunities.yml`: scheduled workflow and direct commit step.
- `scripts/update_opportunities.py`: source fetching, candidate filtering, README insertion, and CLI.
- `tests/test_update_opportunities.py`: tests for deadline parsing, duplicate checks, section creation, and insertion.
