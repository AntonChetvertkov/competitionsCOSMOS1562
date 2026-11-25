"""Questionnaire builder: organisers create, edit, publish and close questionnaires.

The editor autosaves the whole document as JSON (`contest_document` out,
`apply_document` in). Questions are locked once anyone has answered.
"""
import os
import secrets
from datetime import datetime, timezone

from flask import (Blueprint, current_app, g, jsonify, redirect,
                   render_template, request, send_from_directory, url_for)
from sqlalchemy.exc import IntegrityError

from auth import flash_msg, get_owned_contest, organiser_required
from models import (CHOICE_KINDS, FIELD_KINDS, ApplicationField, Contest,
                    FieldOption, db, utc_now)

bp = Blueprint("builder", __name__)

MAX_TITLE, MAX_DESCRIPTION, MAX_THANKS = 200, 5000, 2000
MAX_QUESTIONS, MAX_OPTIONS = 100, 100
MAX_LABEL, MAX_HELP, MAX_OPTION = 500, 1000, 200
MAX_COVER = 2 * 1024 * 1024


class Invalid(Exception):
    def __init__(self, field):
        self.field = field


def error(key, status=400, **extra):
    return jsonify({"error": key, **extra}), status


def covers_dir():
    return os.path.join(current_app.config["UPLOAD_DIR"], "covers")


# --- document ----------------------------------------------------------------

def iso_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def contest_document(contest):
    join_url = None
    if contest.invite_token and contest.status != "draft":
        join_url = url_for("join.form", token=contest.invite_token, _external=True)
    return {
        "id": contest.id,
        "status": contest.status,
        "title": contest.title,
        "description": contest.description or "",
        "thank_you_text": contest.thank_you_text or "",
        "cover_url": (url_for("builder.cover_file", name=contest.cover_path)
                      if contest.cover_path else None),
        "entry_kind": contest.entry_kind,
        "team_max": contest.team_max,
        "manual_approval": bool(contest.manual_approval),
        "registration_closes_at": iso_utc(contest.registration_closes_at),
        "max_entries": contest.max_entries,
        "questions_locked": contest.questions_locked(),
        "entry_count": contest.entry_count(),
        "join_url": join_url,
        "questions": [
            {"id": f.id, "kind": f.kind, "label": f.label, "help_text": f.help_text or "",
             "is_required": bool(f.is_required), "allows_other": bool(f.allows_other),
             "options": [{"id": o.id, "label": o.label} for o in f.options]}
            for f in contest.fields
        ],
    }


def text_value(data, key, limit):
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise Invalid(key)
    return value.strip()[:limit]


def int_or_none(data, key, low, high):
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Invalid(key)
    return max(low, min(high, int(value)))


def parse_closes(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise Invalid("registration_closes_at")
    raw = value.strip()
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        raise Invalid("registration_closes_at")
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def parse_questions(raw):
    if not isinstance(raw, list) or len(raw) > MAX_QUESTIONS:
        raise Invalid("questions")
    parsed = []
    for q in raw:
        if not isinstance(q, dict) or q.get("kind") not in FIELD_KINDS:
            raise Invalid("questions")
        kind = q["kind"]
        label, help_text = q.get("label", ""), q.get("help_text", "")
        if not isinstance(label, str) or not isinstance(help_text, str):
            raise Invalid("questions")
        options = []
        if kind in CHOICE_KINDS:
            raw_options = q.get("options") or []
            if not isinstance(raw_options, list) or len(raw_options) > MAX_OPTIONS:
                raise Invalid("questions")
            for o in raw_options:
                text = o.get("label") if isinstance(o, dict) else o
                if not isinstance(text, str):
                    raise Invalid("questions")
                options.append(text.strip()[:MAX_OPTION])
        parsed.append({
            "kind": kind, "label": label.strip()[:MAX_LABEL],
            "help_text": help_text.strip()[:MAX_HELP],
            "is_required": bool(q.get("is_required", True)),
            "allows_other": bool(q.get("allows_other")) and kind in CHOICE_KINDS,
            "options": options,
        })
    return parsed


def replace_questions(contest, questions):
    for field in list(contest.fields):
        db.session.delete(field)
    db.session.flush()
    for position, q in enumerate(questions):
        field = ApplicationField(
            contest_id=contest.id, position=position, label=q["label"], kind=q["kind"],
            help_text=q["help_text"], is_required=q["is_required"],
            allows_other=q["allows_other"])
        field.options = [FieldOption(position=i, label=label)
                         for i, label in enumerate(q["options"])]
        db.session.add(field)
    db.session.flush()
    db.session.expire(contest, ["fields"])


def apply_document(contest, data):
    """Validate the whole document, then write it. Raises Invalid before any change."""
    if not isinstance(data, dict):
        raise Invalid("body")
    title = text_value(data, "title", MAX_TITLE)
    description = text_value(data, "description", MAX_DESCRIPTION)
    thanks = text_value(data, "thank_you_text", MAX_THANKS)
    kind = data.get("entry_kind", contest.entry_kind)
    if kind not in ("individual", "team"):
        raise Invalid("entry_kind")
    if contest.questions_locked():
        # Entries already exist: switching individual <-> team would orphan
        # team codes or leave solo entries inside a team contest.
        kind = contest.entry_kind
    team_max = int_or_none(data, "team_max", 1, 100) if kind == "team" else None
    max_entries = int_or_none(data, "max_entries", 1, 100000)
    closes = (parse_closes(data["registration_closes_at"])
              if "registration_closes_at" in data else contest.registration_closes_at)
    manual = data.get("manual_approval", contest.manual_approval)
    if not isinstance(manual, bool):
        raise Invalid("manual_approval")
    questions = None
    if "questions" in data and not contest.questions_locked():
        questions = parse_questions(data["questions"])

    if title:
        contest.title = title
    if description is not None:
        contest.description = description
    if thanks is not None:
        contest.thank_you_text = thanks
    contest.entry_kind = kind
    contest.team_max = team_max
    contest.max_entries = max_entries
    contest.registration_closes_at = closes
    contest.manual_approval = manual
    if questions is not None:
        replace_questions(contest, questions)


# --- pages -------------------------------------------------------------------

@bp.route("/organiser/new", methods=["GET", "POST"])
@organiser_required
def new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title or len(title) > MAX_TITLE:
            flash_msg("b.err.title", "Give the questionnaire a name.")
        else:
            contest = Contest(owner_id=g.user.id, title=title, status="draft",
                              slug=secrets.token_hex(6))
            db.session.add(contest)
            db.session.commit()
            return redirect(url_for("builder.edit", contest_id=contest.id))
    return render_template("builder/new.html")


@bp.get("/organiser/contests/<int:contest_id>/edit")
@organiser_required
def edit(contest_id):
    contest = get_owned_contest(contest_id)
    return render_template("builder/edit.html", contest=contest,
                           initial=contest_document(contest))


@bp.route("/organiser/contests/<int:contest_id>/form", methods=["GET", "PUT"])
@organiser_required
def form_json(contest_id):
    contest = get_owned_contest(contest_id)
    if request.method == "PUT":
        try:
            apply_document(contest, request.get_json(silent=True))
        except Invalid as bad:
            db.session.rollback()
            return error("b.err.invalid", field=bad.field)
        db.session.commit()
    return jsonify(contest_document(contest))


def publish_problem(contest):
    """(error key, question index) for the first thing wrong, else None."""
    if not contest.title.strip():
        return "b.err.title", None
    if not contest.fields:
        return "b.err.no_questions", None
    for i, f in enumerate(contest.fields):
        if not f.label.strip():
            return "b.err.empty_label", i
        if f.kind in CHOICE_KINDS and (
                not f.options or any(not o.label.strip() for o in f.options)):
            return "b.err.options", i
    return None


def assign_token(contest):
    for _ in range(5):
        contest.invite_token = secrets.token_urlsafe(6)
        try:
            with db.session.begin_nested():
                db.session.flush()
            return
        except IntegrityError:
            continue
    raise RuntimeError("could not generate an invite token")


@bp.post("/organiser/contests/<int:contest_id>/publish")
@organiser_required
def publish(contest_id):
    contest = get_owned_contest(contest_id)
    body = request.get_json(silent=True) or {}
    if contest.status == "published":
        return error("b.err.state", question_index=None)
    if contest.consent_confirmed_at is None and body.get("consent") is not True:
        return error("b.err.consent", question_index=None)
    problem = publish_problem(contest)
    if problem:
        return error(problem[0], question_index=problem[1])
    contest.status = "published"
    if contest.consent_confirmed_at is None:
        contest.consent_confirmed_at = utc_now()
    if contest.invite_token is None:
        assign_token(contest)
    db.session.commit()
    return jsonify(contest_document(contest))


@bp.post("/organiser/contests/<int:contest_id>/close")
@organiser_required
def close(contest_id):
    contest = get_owned_contest(contest_id)
    if contest.status != "published":
        return error("b.err.state")
    contest.status = "closed"
    db.session.commit()
    return jsonify(contest_document(contest))


@bp.post("/organiser/contests/<int:contest_id>/link")
@organiser_required
def regenerate_link(contest_id):
    contest = get_owned_contest(contest_id)
    if contest.status == "draft":
        return error("b.err.state")
    assign_token(contest)
    db.session.commit()
    return jsonify(contest_document(contest))


# --- cover -------------------------------------------------------------------

def image_extension(head):
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def remove_cover_file(name):
    if name:
        try:
            os.remove(os.path.join(covers_dir(), os.path.basename(name)))
        except OSError:
            pass


@bp.route("/organiser/contests/<int:contest_id>/cover", methods=["POST", "DELETE"])
@organiser_required
def cover(contest_id):
    contest = get_owned_contest(contest_id)
    if request.method == "DELETE":
        remove_cover_file(contest.cover_path)
        contest.cover_path = None
        db.session.commit()
        return jsonify(contest_document(contest))

    upload = request.files.get("cover")
    if upload is None:
        return error("b.err.cover")
    data = upload.stream.read(MAX_COVER + 1)
    ext = image_extension(data[:16])
    if not data or len(data) > MAX_COVER or ext is None:
        return error("b.err.cover")
    os.makedirs(covers_dir(), exist_ok=True)
    name = f"{secrets.token_hex(12)}.{ext}"
    with open(os.path.join(covers_dir(), name), "wb") as f:
        f.write(data)
    remove_cover_file(contest.cover_path)
    contest.cover_path = name
    db.session.commit()
    return jsonify(contest_document(contest))


@bp.post("/organiser/contests/<int:contest_id>/delete")
@organiser_required
def delete(contest_id):
    contest = get_owned_contest(contest_id)
    if contest.entry_count() > 0:
        flash_msg("b.err.delete",
                  "This questionnaire already has answers and can't be deleted.")
        return redirect(url_for("builder.edit", contest_id=contest.id))
    remove_cover_file(contest.cover_path)
    db.session.delete(contest)
    db.session.commit()
    return redirect(url_for("organiser"))


@bp.get("/uploads/covers/<path:name>")
def cover_file(name):
    return send_from_directory(covers_dir(), name, max_age=86400)
