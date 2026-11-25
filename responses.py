"""Organisers: see a questionnaire's answers, approve or reject entries, export CSV."""
import csv
import io

from flask import Blueprint, Response, abort, g, redirect, render_template, request, url_for
from sqlalchemy.orm import selectinload

from auth import get_owned_contest, organiser_required
from models import ApplicationAnswer, Entry, EntryMember, db, utc_now

bp = Blueprint("responses", __name__)

FILTERS = ("all", "pending", "approved", "rejected")


def _load_entries(contest):
    return db.session.execute(
        db.select(Entry).where(Entry.contest_id == contest.id)
        .options(
            selectinload(Entry.members).selectinload(EntryMember.user),
            selectinload(Entry.answers).selectinload(ApplicationAnswer.choices),
            selectinload(Entry.answers).selectinload(ApplicationAnswer.option),
            selectinload(Entry.answers).selectinload(ApplicationAnswer.field),
        )
        .order_by(Entry.created_at.desc(), Entry.id.desc())
    ).scalars().all()


def _people(entry):
    members = sorted(entry.members, key=lambda m: (not m.is_captain, m.joined_at, m.user_id))
    return [m.user for m in members]


def _answers_by_field(entry):
    return {a.field_id: a.display() for a in entry.answers}


@bp.get("/organiser/contests/<int:contest_id>/responses")
@organiser_required
def index(contest_id):
    contest = get_owned_contest(contest_id)
    current = request.args.get("status", "all")
    if current not in FILTERS:
        current = "all"
    entries = _load_entries(contest)
    counts = {s: sum(1 for e in entries if e.status == s) for s in FILTERS[1:]}
    counts["all"] = len(entries)
    shown = entries if current == "all" else [e for e in entries if e.status == current]
    rows = [{"entry": e, "people": _people(e), "answers": _answers_by_field(e)} for e in shown]
    return render_template("responses/index.html", contest=contest, rows=rows,
                           counts=counts, current=current, filters=FILTERS)


@bp.post("/organiser/contests/<int:contest_id>/responses/<int:entry_id>")
@organiser_required
def decide(contest_id, entry_id):
    contest = get_owned_contest(contest_id)
    entry = db.session.get(Entry, entry_id)
    if entry is None or entry.contest_id != contest.id:
        abort(404)
    decision = request.form.get("decision")
    if decision not in ("approved", "rejected"):
        abort(400)
    entry.status = decision
    entry.decided_by = g.user.id
    entry.decided_at = utc_now()
    db.session.commit()
    back = request.form.get("status", "all")
    if back not in FILTERS:
        back = "all"
    return redirect(url_for("responses.index", contest_id=contest.id, status=back))


def _safe_cell(value):
    value = "" if value is None else str(value)
    if value and value[0] in "=+-@\t\r":
        return "'" + value
    return value


@bp.get("/organiser/contests/<int:contest_id>/responses.csv")
@organiser_required
def csv_export(contest_id):
    contest = get_owned_contest(contest_id)
    team = contest.entry_kind == "team"
    header = ["Entry ID", "Status", "Submitted (UTC)"]
    if team:
        header.append("Team")
    header += ["Members", "Emails"] + [f.label for f in contest.fields]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([_safe_cell(h) for h in header])
    for e in reversed(_load_entries(contest)):
        people = _people(e)
        by_field = _answers_by_field(e)
        row = [e.id, e.status, e.created_at.strftime("%Y-%m-%dT%H:%M:%S")]
        if team:
            row.append(e.team_name or "")
        row += ["; ".join(p.full_name for p in people),
                "; ".join(p.email or "" for p in people)]
        row += [by_field.get(f.id, "") for f in contest.fields]
        w.writerow([_safe_cell(c) for c in row])
    body = "﻿" + buf.getvalue()
    resp = Response(body, mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = f'attachment; filename="{contest.slug}-answers.csv"'
    return resp
