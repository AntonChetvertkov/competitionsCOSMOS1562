import os
import secrets
from datetime import timedelta

from dotenv import load_dotenv
from flask import Flask, abort, g, redirect, render_template, request, url_for
from flask_migrate import Migrate
from sqlalchemy import event, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import selectinload

import auth
from auth import admin_required, flash_msg, is_admin, login_required
from models import Contest, Entry, EntryMember, OrganiserRequest, User, db, utc_now

load_dotenv()

app = Flask(__name__)

DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DIR, "dbs", "competitions.db")
# DATABASE_URL lets tests point at a throwaway file instead of dbs/competitions.db.
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///" + DB_PATH)
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Sessions are signed with SECRET_KEY. On the server it must be set in .env,
# otherwise every restart would sign everyone out.
secret = os.environ.get("SECRET_KEY")
if not secret:
    app.logger.warning("SECRET_KEY is not set in .env; using a temporary one.")
    secret = secrets.token_hex(32)
app.config["SECRET_KEY"] = secret
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE") == "1"

# Uploaded files (questionnaire covers) live outside static/ and outside git.
app.config["UPLOAD_DIR"] = os.environ.get("UPLOAD_DIR", os.path.join(DIR, "uploads"))
app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024   # whole request; covers are capped at 2 MB

db.init_app(app)
migrate = Migrate(app, db, render_as_batch=True)
auth.init_app(app)

# Questionnaire areas, each in its own module.
import builder, join, responses  # noqa: E402
app.register_blueprint(builder.bp)
app.register_blueprint(join.bp)
app.register_blueprint(responses.bp)


@event.listens_for(Engine, "connect")
def sqlite_settings(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


# --- public pages ------------------------------------------------------------

@app.get("/")
def landing():
    return render_template("landing.html")


def stub(page, title, text):
    return render_template("stub.html", page=page, title=title, text=text)


@app.get("/privacy")
def privacy():
    return stub("privacy", "Privacy",
                "How we store and delete participants' data will be described here.")


@app.get("/contact")
def contact():
    return stub("contact", "Contact",
                "A way to reach the team will be here.")


# --- participant -------------------------------------------------------------

@app.get("/me")
def participant_old_url():
    # The dashboard used to live here; keep old links working.
    return redirect(url_for("participant"), code=301)


@app.get("/lms")
@login_required
def participant():
    entries = db.session.execute(
        db.select(Entry)
        .join(EntryMember)
        .where(EntryMember.user_id == g.user.id)
        .options(selectinload(Entry.contest))
        .order_by(Entry.created_at.desc())
    ).scalars().all()
    return render_template("dashboard/participant.html", entries=entries)


# --- organiser ---------------------------------------------------------------

@app.route("/organiser", methods=["GET", "POST"])
@login_required
def organiser():
    user = g.user
    can_organise = user.is_organiser or is_admin()

    if request.method == "POST" and not can_organise:
        latest = user.latest_organiser_request
        if latest and latest.status == "pending":
            return redirect(url_for("organiser"))
        organisation = request.form.get("organisation", "").strip()
        message = request.form.get("message", "").strip()
        if not organisation:
            flash_msg("err.org", "Enter the school, club or organisation you run competitions for.")
        else:
            db.session.add(OrganiserRequest(user=user, organisation=organisation[:200],
                                            message=message[:2000]))
            db.session.commit()
            return redirect(url_for("organiser"))

    contests = []
    if can_organise:
        counts = (db.select(Entry.contest_id, func.count(Entry.id).label("n"))
                  .group_by(Entry.contest_id).subquery())
        rows = db.session.execute(
            db.select(Contest, func.coalesce(counts.c.n, 0))
            .outerjoin(counts, counts.c.contest_id == Contest.id)
            .where(Contest.owner_id == user.id)
            .order_by(Contest.created_at.desc())
        ).all()
        contests = [{"contest": c, "entries": n} for c, n in rows]

    return render_template("dashboard/organiser.html", can_organise=can_organise,
                           request_=user.latest_organiser_request, contests=contests)




# --- admin -------------------------------------------------------------------

@app.get("/admin")
@admin_required
def admin():
    pending = db.session.execute(
        db.select(OrganiserRequest).where(OrganiserRequest.status == "pending")
        .options(selectinload(OrganiserRequest.user))
        .order_by(OrganiserRequest.created_at)
    ).scalars().all()
    decided = db.session.execute(
        db.select(OrganiserRequest).where(OrganiserRequest.status != "pending")
        .options(selectinload(OrganiserRequest.user))
        .order_by(OrganiserRequest.reviewed_at.desc()).limit(20)
    ).scalars().all()
    stats = {
        "users": db.session.scalar(db.select(func.count(User.id))),
        "contests": db.session.scalar(db.select(func.count(Contest.id))),
        "entries": db.session.scalar(db.select(func.count(Entry.id))),
    }
    return render_template("dashboard/admin.html", pending=pending, decided=decided, stats=stats)


@app.post("/admin/requests/<int:request_id>")
@admin_required
def admin_decide(request_id):
    req = db.get_or_404(OrganiserRequest, request_id)
    decision = request.form.get("decision")
    if decision not in ("approved", "rejected") or req.status != "pending":
        abort(400)
    req.status = decision
    req.reviewed_by = g.user.id
    req.reviewed_at = utc_now()
    db.session.commit()
    return redirect(url_for("admin"))


@app.errorhandler(403)
def forbidden(_):
    return stub("forbidden", "No access",
                "This page is only for the site administrator."), 403


if __name__ == "__main__":
    app.run(debug=True, port=5078)
