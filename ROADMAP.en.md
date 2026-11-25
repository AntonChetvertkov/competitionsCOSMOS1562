# Roadmap — competitions.cosmos1562.space

First customer: the Hampton School STEM Fair — **a single "Project" round**, results decided by expert votes (physics and DT teachers) and visitor votes at the fair. Hampton does not need the test builder.

If we are not ready by ~7–8 December, or the school isn't convinced, the school uses MS Forms and participant names have to be collected by hand.

Who does what: **backend** (Flask, API, database, deploy) — Anton and his classmate; **contest editor** (React island) — Claude.

## Stages

### 0. Today–tomorrow (25–26 November)
- [ ] DNS `competitions` → Cosmos server, nginx + HTTPS, a Flask skeleton responding on the subdomain.
- [ ] Register the Azure app (Microsoft OAuth) and test sign-in with our own school account. If school admin consent is needed, find out now.
- [ ] Agree the contest JSON schema (editor ↔ API contract) so frontend and backend can be built in parallel.

### 1. Friday 27 November — meeting with the organiser
- [ ] Landing page.
- [ ] Working registration form in Flask (saves to the database).
- [ ] List of registrations for the organiser.
- [ ] Pitch: why this beats MS Forms (participants are in the system straight away, weekly uploads, voting at the fair).
- Questions for the meeting: exact registration date; form fields; first upload date and frequency; fair date; who is on the jury; weighting of jury vs visitor votes; parental consent.

### 2. By ~4 December — ready for registration (3-day buffer)
- [ ] Sign-in: Microsoft + fallback email/password sign-in.
- [ ] Project contest editor (Claude): dates, weeks/tasks, join mode, application form fields, results scheme.
- [ ] API to save the contest + contest page + application form built from the organiser's fields (us).
- [ ] Application moderation and CSV export of participants for the organiser.
- [ ] Consent checkbox when creating a contest.
- [ ] 5–6 December: dry run with classmates on the production server.

### 3. 7–8 December — Hampton registration opens
- On call: fix bugs fast, watch the logs.

### 4. Before the first upload date (target: mid-December)
- [ ] "My competitions" (active).
- [ ] Weekly photo/text upload on the dates set in the contest.
- [ ] Comparison with the previous photo (perceptual hash); a reused photo gets flagged.
- [ ] Manual review queue for the organiser (accept/reject).

### 5. Christmas holidays (late December – January)
- [ ] "My results", final block with files.
- [ ] Test builder (Claude — frontend, us — API and auto-grading).
- [ ] Multiple rounds, results schemes.
- [ ] Google, Yandex, VK sign-in; full EN/RU.
- [ ] Admin moderation of organisers (by hand in the DB until then).

### 6. Before fair day
- [ ] Jury voting (scores by criteria).
- [ ] Visitor voting — **minimal friction** (mechanism to decide later, e.g. QR code at the stand + a limit).
- [ ] Results and a results screen.

### Later
Teams, temporary accounts, AI checks of uploads, paid plans and payments, photo auto-deletion.

## Open questions
- Exact dates: registration, first upload, fair day.
- Visitor voting mechanism and protection against vote stuffing.
- Will the school's Microsoft tenant allow a third-party app?
