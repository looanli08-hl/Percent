# Percent Roadmap

Last updated: 2026-04-06

## Current State

Percent has passed the "prototype works" stage.

What is already true:

- Core CLI and Web flows exist and are usable.
- Parser coverage is already broad enough for an early product.
- Packaging, registry, dedup migration, and CI regressions from the recent audit have been fixed.
- The main remaining gap is no longer implementation speed. It is product contract clarity and feature integration.

What is not yet true:

- Not all implemented capabilities are surfaced in the primary user journey.
- Product docs, CLI help, and public positioning are not yet fully aligned.
- Trust and observability layers are still thin.
- Evaluation is good enough for internal iteration, but not yet strong enough for external claims.

## Product Direction

Percent is currently two products in one codebase:

1. Consumer-facing AI mirror
   Web UI, import flow, profile view, conversation experience.
2. Developer-facing personality engine
   CLI, `core.md`, `SOUL.md`, APIs, reproducible workflows.

The roadmap below assumes this priority order:

1. Stabilize one public "golden path" first.
2. Expose already-built capabilities before adding more sources.
3. Improve trust, provenance, and evaluation before broad launch.

## Stable vs Beta

This should be made explicit in docs and product copy.

Stable:

- `wechat`
- `youtube`
- `bilibili`
- `core.md`
- `chat`
- `SOUL.md`

Beta:

- `wechat-db`
- `telegram`
- `whatsapp`
- API-driven imports
- advanced evaluation claims

## Execution Principles

- Do not add new parsers until the current surface area is coherent.
- Prefer finishing one full user path over shipping more isolated backend capabilities.
- Every new feature should answer three questions:
  1. Where is it triggered?
  2. Where is it visible?
  3. How is it verified?

## Wave 1: Contract Cleanup

Goal:
Make the product boundary explicit and remove ambiguity between code, docs, and UI.

Scope:

- Define which sources are stable vs beta.
- Align README, CLI help text, and Web copy.
- Ensure every public command matches reality.
- Decide the public installation story for this phase.

Deliverables:

- Root-level `STATUS.md` or keep this `ROADMAP.md` as the single source of truth.
- README and README_CN updated to reflect actual stable/beta support.
- CLI help strings updated for all import-related commands.
- Telegram dependency guidance updated to prefer `percent[telegram]`.
- Short release positioning statement:
  "Percent is a local-first personality modeling engine with a Web mirror and CLI export workflow."

Exit criteria:

- A new user can read the README and correctly understand:
  - how to install
  - which sources are stable
  - which features are beta
  - whether data may be sent to a cloud LLM
- CLI help does not contradict README.

Non-goals:

- No new parser work.
- No redesign of evaluation yet.

## Wave 2: Integrate Existing Intelligence

Goal:
Turn existing backend capabilities into part of the core product experience.

Why this wave matters:

- `fingerprint` already exists in code but is not part of the main workflow.
- `big-five` exists as a CLI command and API endpoint but is not surfaced in the Web UI.
- This is the fastest way to make Percent feel significantly more complete without major new infrastructure.

Scope:

- Generate `fingerprint.json` as part of the analysis pipeline.
- Decide whether `big_five.json` is:
  - auto-generated after each analysis, or
  - generated on-demand from UI/CLI due to LLM cost.
- Add Web UI sections for:
  - behavioral fingerprint
  - Big Five summary
  - profile metadata

Deliverables:

- Pipeline integration for behavioral fingerprint.
- A clear trigger for Big Five generation.
- Web profile sidebar or profile area upgraded from "core.md only" to structured profile view.
- Tests for fingerprint generation and Web/API retrieval.

Exit criteria:

- After one successful import, the user can see:
  - `core.md`
  - fragment stats
  - behavioral fingerprint
  - optionally Big Five
- No hidden backend-only feature remains in this area.

Non-goals:

- No evidence drill-down yet.
- No benchmark redesign yet.

## Wave 3: Provenance and Trust Layer

Goal:
Make Percent explainable enough that users can trust the output.

Scope:

- Add import manifest / analysis history.
- Track:
  - file hash
  - source
  - parser version
  - import time
  - analysis time
  - fragment counts
  - derived artifacts produced
- Add a provenance model for findings and synthesized profile sections.
- Surface evidence in the Web UI.

Deliverables:

- `imports.json` or SQLite-backed import history.
- Provenance fields attached to fragments/findings/profile sections.
- "Why does Percent think this?" affordance in the UI.
- A visible source coverage summary:
  - how many sources imported
  - how much data analyzed
  - which conclusions are weak vs well-supported

Exit criteria:

- For at least one personality conclusion, the user can inspect its supporting evidence.
- Repeated imports are auditable and not opaque.
- Support/debug sessions can answer "what changed after this import?"

Non-goals:

- No full visual redesign.
- No broad launch push before this wave is complete.

## Wave 4: Operational UX

Goal:
Reduce setup friction and failure recovery cost.

Scope:

- Add `percent doctor`.
- Add reset / cleanup flows.
- Improve config and secret handling.
- Clarify local vs cloud model usage.

Deliverables:

- `percent doctor`
  - checks config
  - checks required files
  - checks optional deps
  - checks raw/profile/database state
- `percent reset chat`
- `percent reset profile` or `percent purge`
- Config support for environment variables, and optionally keyring/keychain later.
- Documentation for:
  - cloud LLM mode
  - local model mode
  - optional dependencies

Exit criteria:

- A first-time user can self-diagnose common setup problems.
- A returning user can recover from a bad import or stale state without manual file deletion.
- Secret handling is better documented and less surprising.

Non-goals:

- No external SaaS backend.
- No multi-user accounts.

## Wave 5: Evaluation Upgrade

Goal:
Make quality claims defensible.

Scope:

- Redesign PersonaBench with actual train/eval separation.
- Record evaluation metadata.
- Add breakdowns by source and chunk type.

Deliverables:

- Fixed-seed data split for training vs evaluation.
- Evaluation report containing:
  - sample counts
  - source mix
  - model/provider
  - prompt version
  - score breakdown
- Clear statement of what the benchmark measures and what it does not.

Exit criteria:

- "PersonaBench score" has a precise definition.
- A score can be reproduced later with the same setup.
- README wording about evaluation is modest and accurate.

Non-goals:

- No leaderboard work.
- No external benchmark marketing until this is stable.

## Suggested Order Of Execution

Recommended sequence:

1. Wave 1
2. Wave 2
3. Wave 3
4. Wave 4
5. Wave 5

Reasoning:

- Wave 1 removes ambiguity.
- Wave 2 turns latent backend value into visible product value.
- Wave 3 increases trust.
- Wave 4 reduces operational friction.
- Wave 5 strengthens external credibility after the product path is coherent.

## Immediate Next Tasks

These are the best next concrete tasks to hand to Claude right now.

1. Create stable/beta support matrix and align README, README_CN, CLI help, and Web copy.
2. Integrate behavioral fingerprint into the main analysis pipeline and persist `fingerprint.json`.
3. Surface fingerprint and Big Five in the Web profile view.
4. Add import manifest / analysis history with hash-based provenance.
5. Add `percent doctor` and one reset/cleanup command.

## Recommended Claude Work Split

To avoid file conflicts, do not run all of these in parallel in the same files.

Batch A: contract and docs

- `README.md`
- `README_CN.md`
- `percent/cli.py`
- small Web copy changes only if needed

Batch B: profile enrichment

- `percent/persona/engine.py`
- `percent/persona/fingerprint.py`
- `percent/web.py`
- `percent/static/index.html`
- related tests

Batch C: provenance and operations

- fragment/import storage layer
- new manifest/history structures
- `percent/cli.py`
- `percent/web.py`
- related tests

## Release Gate For Public Push

Before pushing Percent more broadly, the following should all be true:

- One stable import path works end-to-end with minimal user confusion.
- Web profile shows more than raw `core.md`.
- Evidence or provenance exists for at least some conclusions.
- Setup and recovery commands exist.
- README claims match actual behavior.

If these are not true yet, keep positioning as an actively evolving project rather than a polished public product.
