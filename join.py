"""Participants: fill in a questionnaire from its invite link, edit answers, join teams."""
import math
import re
import secrets
from datetime import datetime

from flask import Blueprint, g, redirect, render_template, request, url_for
from sqlalchemy.orm import selectinload

from auth import flash_msg, get_owned_contest, login_required
from models import (AnswerChoice, ApplicationAnswer, Contest, Entry, EntryMember, db)

bp = Blueprint("join", __name__)

OTHER = "__other__"
SHORT_MAX = 300
LONG_MAX = 5000
TEAM_NAME_MAX = 100
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

ERR_REQUIRED = ("j.err.required", "This question needs an answer.")
ERR_TOO_LONG = ("j.err.toolong", "This answer is too long.")
ERR_NUMBER = ("j.err.number", "Enter a number, for example 12 or 3.5.")
ERR_DATE = ("j.err.date", "Enter a valid date.")
ERR_CHOICE = ("j.err.choice", "Choose one of the listed answers.")
ERR_OTHER = ("j.err.other", "Write your answer next to Other.")
ERR_TEAM = ("j.err.team_name", "Give your team a name (up to 100 characters).")


# --- helpers -------------------------------------------------------------------

def _missing():
    return render_template(
        "stub.html", page="join_missing", title="Questionnaire not found",
        text="This link doesn't work. Ask the organiser for a new one."), 404


def _my_membership(contest):
    """The current user's EntryMember in this contest, or None."""
    return db.session.execute(
        db.select(EntryMember).join(Entry, Entry.id == EntryMember.entry_id)
        .where(Entry.contest_id == contest.id, EntryMember.user_id == g.user.id)
    ).scalar_one_or_none()


def _closed_reason(contest):
    if contest.status != "published":
        return "closed"
    if contest.closes_passed():
        return "deadline"
    return "full"


def _canonical_number(raw):
    try:
        f = float(raw.replace(",", "."))
    except ValueError:
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    if f == int(f) and abs(f) < 1e15:
        return str(int(f))
    return repr(f)


def _values_from_form(contest, form):
    vals = {}
    for f in contest.fields:
        key = f"q{f.id}"
        vals[f.id] = {
            "text": form.get(key, ""),
            "option": form.get(key, ""),
            "multi": form.getlist(key),
            "other": form.get(key + "_other", ""),
        }
    return vals


def _values_from_entry(contest, entry):
    vals = {}
    by_field = {a.field_id: a for a in entry.answers}
    for f in contest.fields:
        a = by_field.get(f.id)
        v = {"text": "", "option": "", "multi": [], "other": ""}
        if a is not None:
            if f.kind in ("single", "dropdown"):
                if a.option_id is not None:
                    v["option"] = str(a.option_id)
                else:
                    v["option"] = OTHER
                    v["other"] = a.value_text or ""
            elif f.kind == "multiple":
                v["multi"] = [str(c.option_id) for c in a.choices]
                if a.value_text:
                    v["multi"].append(OTHER)
                    v["other"] = a.value_text
            else:
                v["text"] = a.value_text or ""
        vals[f.id] = v
    return vals


def _validate(contest, form):
    """Returns (plan, errors). plan: list of (field, value_text, option_id, [option_ids])."""
    plan, errors = [], {}
    for f in contest.fields:
        key = f"q{f.id}"
        valid_ids = {str(o.id): o.id for o in f.options}
        text, option_id, choice_ids = None, None, []

        if f.kind in ("short_text", "long_text", "number", "date"):
            raw = (form.get(key) or "").strip()
            if not raw:
                if f.is_required:
                    errors[f.id] = ERR_REQUIRED
                continue
            if f.kind == "short_text":
                if len(raw) > SHORT_MAX:
                    errors[f.id] = ERR_TOO_LONG
                    continue
                text = raw
            elif f.kind == "long_text":
                if len(raw) > LONG_MAX:
                    errors[f.id] = ERR_TOO_LONG
                    continue
                text = raw
            elif f.kind == "number":
                text = _canonical_number(raw)
                if text is None:
                    errors[f.id] = ERR_NUMBER
                    continue
            else:
                try:
                    if not DATE_RE.match(raw):
                        raise ValueError
                    datetime.strptime(raw, "%Y-%m-%d")
                except ValueError:
                    errors[f.id] = ERR_DATE
                    continue
                text = raw

        elif f.kind in ("single", "dropdown"):
            raw = (form.get(key) or "").strip()
            if not raw:
                if f.is_required:
                    errors[f.id] = ERR_REQUIRED
                continue
            if raw == OTHER and f.allows_other:
                other = (form.get(key + "_other") or "").strip()
                if not other:
                    errors[f.id] = ERR_OTHER
                    continue
                if len(other) > SHORT_MAX:
                    errors[f.id] = ERR_TOO_LONG
                    continue
                text = other
            elif raw in valid_ids:
                option_id = valid_ids[raw]
            else:
                errors[f.id] = ERR_CHOICE
                continue

        elif f.kind == "multiple":
            raws = [r.strip() for r in form.getlist(key) if r.strip()]
            bad = False
            other_ticked = False
            for r in raws:
                if r == OTHER and f.allows_other:
                    other_ticked = True
                elif r in valid_ids:
                    if valid_ids[r] not in choice_ids:
                        choice_ids.append(valid_ids[r])
                else:
                    bad = True
            if bad:
                errors[f.id] = ERR_CHOICE
                continue
            if other_ticked:
                other = (form.get(key + "_other") or "").strip()
                if not other:
                    errors[f.id] = ERR_OTHER
                    continue
                if len(other) > SHORT_MAX:
                    errors[f.id] = ERR_TOO_LONG
                    continue
                text = other
            if not choice_ids and text is None:
                if f.is_required:
                    errors[f.id] = ERR_REQUIRED
                continue

        plan.append((f, text, option_id, choice_ids))
    return plan, errors


def _replace_answers(entry, plan):
    for a in list(entry.answers):
        db.session.delete(a)
    db.session.flush()
    db.session.expire(entry, ["answers"])
    for f, text, option_id, choice_ids in plan:
        db.session.add(ApplicationAnswer(
            entry_id=entry.id, field_id=f.id, value_text=text, option_id=option_id,
            choices=[AnswerChoice(option_id=oid) for oid in choice_ids]))


def _new_join_code():
    while True:
        code = secrets.token_urlsafe(6)
        if db.session.scalar(db.select(Entry.id).where(Entry.join_code == code)) is None:
            return code


def _render_form(contest, **kw):
    ctx = dict(contest=contest, mode="new", vals={}, errors={}, team_error=None,
               team_name="", entry=None, preview=False, is_captain=False, answers={},
               can_leave=False)
    ctx.update(kw)
    return render_template("join/form.html", **ctx)


def _check_submission(contest, form):
    plan, errors = _validate(contest, form)
    team_name = (form.get("team_name") or "").strip()
    team_error = None
    if contest.entry_kind == "team" and not (1 <= len(team_name) <= TEAM_NAME_MAX):
        team_error = ERR_TEAM
    return plan, errors, team_name, team_error


# --- the questionnaire ---------------------------------------------------------

@bp.route("/join/<token>", methods=["GET", "POST"])
@login_required
def form(token):
    contest = db.session.execute(
        db.select(Contest).where(Contest.invite_token == token)).scalar_one_or_none()
    if contest is None or contest.status == "draft":
        return _missing()

    member = _my_membership(contest)

    if member is not None:
        entry = member.entry
        if request.method == "GET" and request.args.get("sent") == "1":
            return render_template("join/thanks.html", contest=contest, entry=entry,
                                   is_captain=member.is_captain)
        editable = member.is_captain and contest.accepts_edits()
        if not editable:
            if request.method == "POST":
                return redirect(url_for("join.form", token=token))
            return _render_form(
                contest, mode="readonly", entry=entry, is_captain=member.is_captain,
                can_leave=(not member.is_captain and contest.accepts_edits()),
                answers={a.field_id: a for a in entry.answers})
        if request.method == "POST":
            plan, errors, team_name, team_error = _check_submission(contest, request.form)
            if errors or team_error:
                return _render_form(
                    contest, mode="edit", entry=entry, is_captain=True, errors=errors,
                    team_error=team_error, team_name=team_name,
                    vals=_values_from_form(contest, request.form))
            if contest.entry_kind == "team":
                entry.team_name = team_name
            _replace_answers(entry, plan)
            db.session.commit()
            return redirect(url_for("join.form", token=token, sent=1))
        return _render_form(contest, mode="edit", entry=entry, is_captain=True,
                            team_name=entry.team_name or "",
                            vals=_values_from_entry(contest, entry))

    # No entry yet.
    if not contest.accepts_new_entries():
        return render_template("join/closed.html", contest=contest,
                               reason=_closed_reason(contest)), 403

    if request.method == "POST":
        plan, errors, team_name, team_error = _check_submission(contest, request.form)
        if errors or team_error:
            return _render_form(
                contest, errors=errors, team_error=team_error, team_name=team_name,
                is_captain=True, vals=_values_from_form(contest, request.form))
        entry = Entry(contest_id=contest.id,
                      status="pending" if contest.manual_approval else "approved")
        if contest.entry_kind == "team":
            entry.team_name = team_name
            entry.join_code = _new_join_code()
        db.session.add(entry)
        db.session.flush()
        db.session.add(EntryMember(entry_id=entry.id, user_id=g.user.id, is_captain=True))
        _replace_answers(entry, plan)
        db.session.commit()
        return redirect(url_for("join.form", token=token, sent=1))

    return _render_form(contest, is_captain=True)


@bp.get("/organiser/contests/<int:contest_id>/preview")
@login_required
def preview(contest_id):
    contest = get_owned_contest(contest_id)
    return _render_form(contest, preview=True, is_captain=True)


# --- teams ---------------------------------------------------------------------

def _team_entry(code):
    return db.session.execute(
        db.select(Entry).where(Entry.join_code == code)
        .options(selectinload(Entry.members))).scalar_one_or_none()


@bp.route("/team/<code>", methods=["GET", "POST"])
@login_required
def team(code):
    entry = _team_entry(code)
    if entry is None:
        return _missing()
    contest = entry.contest
    mine = _my_membership(contest)
    in_this_team = mine is not None and mine.entry_id == entry.id

    if request.method == "POST":
        if in_this_team:
            return redirect(url_for("participant"))
        if not contest.accepts_edits():
            flash_msg("j.err.closed", "Entries for this competition are closed.")
        elif mine is not None:
            flash_msg("j.err.already", "You already have an entry in this competition.")
        elif contest.team_max is not None and len(entry.members) >= contest.team_max:
            flash_msg("j.err.team_full", "This team is full.")
        else:
            db.session.add(EntryMember(entry_id=entry.id, user_id=g.user.id, is_captain=False))
            db.session.commit()
            return redirect(url_for("participant"))
        return redirect(url_for("join.team", code=code))

    return render_template("join/team.html", contest=contest, entry=entry,
                           in_this_team=in_this_team,
                           has_other=(mine is not None and not in_this_team),
                           members=len(entry.members), can_join=contest.accepts_edits())


@bp.post("/team/<code>/leave")
@login_required
def leave(code):
    entry = _team_entry(code)
    if entry is None:
        return _missing()
    member = next((m for m in entry.members if m.user_id == g.user.id), None)
    if member is None:
        return redirect(url_for("participant"))
    if member.is_captain:
        flash_msg("j.err.captain", "The team captain can't leave the team.")
    elif not entry.contest.accepts_edits():
        flash_msg("j.err.closed", "Entries for this competition are closed.")
    else:
        db.session.delete(member)
        db.session.commit()
    return redirect(url_for("participant"))
