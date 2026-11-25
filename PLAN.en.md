# Competitions Platform — competitions.cosmos1562.space

## Context
An open SaaS platform for running competitions. First pilot: the Hampton School STEM Fair (UK, students); projects start in early December 2026. Standalone Flask project on a subdomain, not linked to Cosmos1562 yet (shares its server). Backend is written by us (two classmates); Claude writes the test-builder frontend and helps with specs and review.

## Decisions
| Topic | Decision |
|---|---|
| Stack | Flask + Jinja for dashboards, forms, uploads; a React island (Vite) only for the test builder; SQLite |
| Sign-in | OAuth: Microsoft, Google, Yandex, VK + email/password + sign-up. Organisers can generate temporary accounts for a specific competition |
| Roles | Participant (everyone), Organiser (after admin approval), Admin |
| Languages | EN + RU |
| Competition | A chain of rounds; each round is a "Project" or a "Test"; advancement by pass mark or top-N |
| Joining | Organiser picks: open / application (organiser-defined form + moderation) / link-only (hidden from catalogue). Individual and team competitions |
| Project | Organiser chooses: overall description and/or weekly tasks, plus extra tasks. Weekly upload: photo and/or text; final block asks for files/work |
| Upload check | 1) compare with previous photo (perceptual hash, catches reuse) → 2) AI relevance check → 3) if unsure → manual review queue. **MVP: no AI** — hash + manual queue |
| Project results | Organiser picks: activity gate + jury on final / points total / completion certificate |
| Test | Blocks: single/multiple choice, short answer (number/word), essay (manual review, AI later), matching/ordering |
| Money | Free tier with limits + paid organiser plan (YooKassa or similar) — later |
| Data | Cosmos server; organiser confirms parental/student consent when creating a competition; photos auto-deleted N days after the end |
| AI (later) | One adapter interface: vision API first, local model (Ollama + Qwen-VL) later |

## Phases
**Phase 1 — for the Hampton start (early December):**
- Landing, sign-in (Google + Microsoft at minimum; Yandex/VK via authlib like Cosmos `main.py`), password, temporary accounts.
- Admin approves organisers (can be done by hand in the DB at first).
- Organiser: create a competition with one "Project" round, weekly tasks, join mode + application form, application moderation.
- Participant: public catalogue, "My competitions" (active), weekly upload (photo/text).
- Hash comparison with the previous photo; manual review queue for the organiser (accept/reject).
- Consent checkbox when creating a competition.
- **Test builder** (all 4 block types) — required by December. Claude: React island (editor + participant player). Us: API to save tests, receive answers, auto-grading, essays into the same manual review queue.
- First agree the test JSON schema (frontend↔backend contract), e.g.
  `{blocks:[{id, type:"choice"|"short"|"essay"|"match"|"order", prompt, points, options?, multi?, answers?, pairs?, items?}]}`; participant answers are `{block_id: value}`. Correct answers are never sent to the player.

**Phase 2 — while the competition runs:** "My results", results schemes, final block with files, teams, multiple rounds, full EN/RU.

**Phase 3:** AI adapter, plans and payments, photo auto-deletion.

## Data model sketch
users, oauth_identities, organizer_requests, contests (join_mode, visibility, scoring_scheme, consent_confirmed), rounds (contest_id, order, type, pass_rule), tasks (round_id, week, prompt, is_extra), teams + team_members, applications (form_answers JSON, status), participations, submissions (task_id, kind photo/text/file, path, phash, status pending/approved/rejected, reviewer_id), tests / test_attempts.

## Testing
- pytest with the Flask test client: sign-in, create competition, application → approval, upload, reused photo → flagged, manual review, test save + auto-grading.
- Dry run of a whole competition with temporary accounts before handing it to Hampton.
