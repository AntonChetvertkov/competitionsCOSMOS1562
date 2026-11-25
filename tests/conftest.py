import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Must happen before `import app`: it reads DATABASE_URL at import time.
_tmp = tempfile.mkdtemp(prefix="comp_tests_")
_db_file = Path(_tmp, "test.db").as_posix()
os.environ["DATABASE_URL"] = "sqlite:///" + _db_file

import pytest  # noqa: E402

import app as app_module  # noqa: E402
import auth  # noqa: E402
from models import Contest, Entry, EntryMember, OrganiserRequest, User, db  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
assert _db_file in app_module.app.config["SQLALCHEMY_DATABASE_URI"]


@pytest.fixture
def app():
    a = app_module.app
    with a.app_context():
        db.drop_all()
        db.create_all()
    yield a
    with a.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def post(client, url, **data):
    """POST with a valid CSRF token."""
    with client.session_transaction() as s:
        s["csrf"] = "t"
    return client.post(url, data={"csrf_token": "t", **data})


def login_as(client, user_id):
    with client.session_transaction() as s:
        s["user_id"] = user_id
        s["csrf"] = "t"


def make_user(email="u@x.org", first="Ann", last="Lee", password="pass12345"):
    u = User(email=email, first_name=first, last_name=last,
             password_hash=generate_password_hash(password))
    db.session.add(u)
    db.session.commit()
    return u.id


def make_admin():
    return make_user(email=auth.ADMIN_EMAIL, first="Anton", last="C")


def make_contest(owner_id, slug="c1", title="Contest One"):
    c = Contest(owner_id=owner_id, slug=slug, title=title, join_mode="open",
                scoring_scheme="points",
                consent_confirmed_at=datetime.now(timezone.utc))
    db.session.add(c)
    db.session.commit()
    return c.id


def make_entry(contest_id, user_id):
    e = Entry(contest_id=contest_id)
    db.session.add(e)
    db.session.flush()
    db.session.add(EntryMember(entry_id=e.id, user_id=user_id))
    db.session.commit()
    return e.id


def make_request(user_id, status="pending", organisation="School"):
    r = OrganiserRequest(user_id=user_id, organisation=organisation, status=status)
    db.session.add(r)
    db.session.commit()
    return r.id
