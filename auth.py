"""Accounts: email + password sign-up, sign-in, sign-out, and the helpers
every page uses (current user, login_required, admin check, CSRF).

Admin works like Cosmos1562: one fixed address, exact match. Unlike
Cosmos, emails here are typed in, not confirmed by Google or Yandex, so
the admin address is reserved: the sign-up form refuses it, and the
admin account is made from the terminal with `flask create-admin`.
"""
import secrets
from functools import wraps
from urllib.parse import urlparse

import click
from flask import (Blueprint, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from models import User, db

ADMIN_EMAIL = "achetvertkovanton@yandex.com"
MIN_PASSWORD = 8

bp = Blueprint("auth", __name__)


# --- helpers ---------------------------------------------------------------

def normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


def is_admin() -> bool:
    user = g.get("user")
    return bool(user and user.email == ADMIN_EMAIL)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not is_admin():
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def safe_next(target: str | None, fallback: str) -> str:
    """Only follow `next` back into this site, never to another host."""
    if not target:
        return fallback
    parts = urlparse(target)
    if parts.scheme or parts.netloc or not target.startswith("/") or target.startswith("//"):
        return fallback
    return target


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def organiser_required(view):
    """Approved organisers and the admin."""
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not (g.user.is_organiser or is_admin()):
            return redirect(url_for("organiser"))
        return view(*args, **kwargs)
    return wrapped


def get_owned_contest(contest_id: int):
    """The contest if the current user owns it (or is admin), else 404.
    404 rather than 403 so other people's contest ids aren't confirmed."""
    from models import Contest
    contest = db.session.get(Contest, contest_id)
    if contest is None or not (contest.owner_id == g.user.id or is_admin()):
        abort(404)
    return contest


def flash_msg(key: str, english: str, category: str = "error"):
    # Templates render the key as data-i18n, so the message switches language too.
    flash({"key": key, "text": english}, category)


def init_app(app):
    app.register_blueprint(bp)
    app.jinja_env.globals["csrf_token"] = csrf_token
    app.jinja_env.globals["is_admin"] = is_admin

    @app.before_request
    def load_user():
        user_id = session.get("user_id")
        g.user = db.session.get(User, user_id) if user_id else None
        if user_id and g.user is None:
            session.pop("user_id", None)

    @app.before_request
    def check_csrf():
        # Forms send the token as a field; fetch() calls (the builder's
        # autosave) send it in the X-CSRF-Token header.
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
            if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
                abort(400)

    @app.cli.command("create-admin")
    def create_admin():
        """Create the admin account, or reset its password."""
        password = click.prompt("Admin password (8+ characters)", hide_input=True,
                                confirmation_prompt=True)
        if len(password) < MIN_PASSWORD:
            raise click.ClickException("Password is too short.")
        user = db.session.execute(
            db.select(User).where(User.email == ADMIN_EMAIL)).scalar_one_or_none()
        if user is None:
            first = click.prompt("First name")
            last = click.prompt("Last name")
            user = User(email=ADMIN_EMAIL, first_name=first, last_name=last)
            db.session.add(user)
        user.password_hash = generate_password_hash(password)
        db.session.commit()
        click.echo(f"Admin account ready: {ADMIN_EMAIL}")


def start_session(user: User):
    session.clear()
    session["user_id"] = user.id
    session.permanent = True


# --- pages -----------------------------------------------------------------

@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(safe_next(request.args.get("next"), url_for("participant")))
    form = {"first_name": "", "last_name": "", "email": ""}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in form}
        form["email"] = normalize_email(form["email"])
        password = request.form.get("password", "")

        if not form["first_name"] or not form["last_name"]:
            flash_msg("err.name", "Enter your first and last name.")
        elif "@" not in form["email"] or "." not in form["email"].split("@")[-1]:
            flash_msg("err.email", "Enter a valid email address.")
        elif form["email"] == ADMIN_EMAIL:
            flash_msg("err.taken", "An account with this email already exists. Sign in instead.")
        elif len(password) < MIN_PASSWORD:
            flash_msg("err.short", "Use a password of at least 8 characters.")
        else:
            user = User(email=form["email"], first_name=form["first_name"],
                        last_name=form["last_name"],
                        password_hash=generate_password_hash(password))
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash_msg("err.taken", "An account with this email already exists. Sign in instead.")
            else:
                start_session(user)
                return redirect(safe_next(request.args.get("next"), url_for("participant")))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(safe_next(request.args.get("next"), url_for("participant")))
    email = ""
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        password = request.form.get("password", "")
        user = db.session.execute(
            db.select(User).where(User.email == email)).scalar_one_or_none()
        if user and user.password_hash and check_password_hash(user.password_hash, password):
            start_session(user)
            return redirect(safe_next(request.args.get("next"), url_for("participant")))
        flash_msg("err.login", "Wrong email or password.")
    return render_template("auth/login.html", email=email)


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))
