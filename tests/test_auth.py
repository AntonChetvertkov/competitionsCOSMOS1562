from conftest import post
from models import User, db
from werkzeug.security import check_password_hash
import auth

REG = dict(first_name="Ann", last_name="Lee", email="  Test@X.org ", password="pass12345")


def users(app):
    with app.app_context():
        return db.session.execute(db.select(User)).scalars().all()


def test_register_creates_user_and_logs_in(app, client):
    r = post(client, "/register", **REG)
    assert r.status_code == 302 and r.headers["Location"].endswith("/lms")
    us = users(app)
    assert len(us) == 1
    assert us[0].email == "test@x.org"
    assert us[0].password_hash != "pass12345"
    assert check_password_hash(us[0].password_hash, "pass12345")
    with client.session_transaction() as s:
        assert s["user_id"] == us[0].id


def test_register_safe_next(app, client):
    r = post(client, "/register?next=/organiser", **REG)
    assert r.headers["Location"].endswith("/organiser")


def test_register_rejects_external_next(app, client):
    r = post(client, "/register?next=https://evil.example", **REG)
    assert r.headers["Location"].endswith("/lms")


def test_register_rejects_protocol_relative_next(app, client):
    r = post(client, "/register?next=//evil.example", **REG)
    assert r.headers["Location"].endswith("/lms")


def test_duplicate_email_case_insensitive(app, client):
    post(client, "/register", **{**REG, "email": "test@x.org"})
    c2 = app.test_client()
    r = post(c2, "/register", **{**REG, "email": "Test@X.org"})
    assert r.status_code == 200
    assert len(users(app)) == 1
    with c2.session_transaction() as s:
        assert "user_id" not in s


def test_short_password_refused(app, client):
    post(client, "/register", **{**REG, "password": "short"})
    assert users(app) == []


def test_missing_names_refused(app, client):
    post(client, "/register", **{**REG, "first_name": ""})
    post(client, "/register", **{**REG, "last_name": "  "})
    assert users(app) == []


def test_bad_email_refused(app, client):
    for bad in ("nope", "a@b", ""):
        post(client, "/register", **{**REG, "email": bad})
    assert users(app) == []


def test_admin_email_cannot_register(app, client):
    r = post(client, "/register", **{**REG, "email": auth.ADMIN_EMAIL.upper()})
    assert r.status_code == 200
    assert users(app) == []
    with client.session_transaction() as s:
        assert "user_id" not in s


def _registered(app):
    c = app.test_client()
    post(c, "/register", **{**REG, "email": "test@x.org"})
    return app.test_client()


def test_login_ok(app, client):
    c = _registered(app)
    r = post(c, "/login", email="test@x.org", password="pass12345")
    assert r.status_code == 302 and r.headers["Location"].endswith("/lms")
    with c.session_transaction() as s:
        assert "user_id" in s


def test_login_wrong_password(app, client):
    c = _registered(app)
    r = post(c, "/login", email="test@x.org", password="wrongpass1")
    assert r.status_code == 200
    with c.session_transaction() as s:
        assert "user_id" not in s


def test_login_case_insensitive_email(app, client):
    c = _registered(app)
    r = post(c, "/login", email=" TEST@x.ORG ", password="pass12345")
    assert r.status_code == 302
    with c.session_transaction() as s:
        assert "user_id" in s


def test_logout_post_only_and_clears(app, client):
    post(client, "/register", **REG)
    assert client.get("/logout").status_code == 405
    r = post(client, "/logout")
    assert r.status_code == 302
    with client.session_transaction() as s:
        assert "user_id" not in s


def test_post_without_csrf_is_400(app, client):
    assert client.post("/register", data=REG).status_code == 400
    assert client.post("/login", data={"email": "a@b.c", "password": "x"}).status_code == 400
    with client.session_transaction() as s:
        s["csrf"] = "t"
    assert client.post("/register", data={**REG, "csrf_token": "wrong"}).status_code == 400
    assert users(app) == []


def test_create_admin_cli(app):
    runner = app.test_cli_runner()
    res = runner.invoke(args=["create-admin"], input="pass12345\npass12345\nAnton\nC\n")
    assert res.exit_code == 0, res.output
    with app.app_context():
        u = db.session.execute(db.select(User).where(User.email == auth.ADMIN_EMAIL)).scalar_one()
        assert check_password_hash(u.password_hash, "pass12345")
    c = app.test_client()
    assert post(c, "/login", email=auth.ADMIN_EMAIL, password="pass12345").status_code == 302
    with c.session_transaction() as s:
        assert "user_id" in s

    # Second run: only password + confirmation prompts, resets password.
    res = runner.invoke(args=["create-admin"], input="newpass999\nnewpass999\n")
    assert res.exit_code == 0, res.output
    with app.app_context():
        rows = db.session.execute(db.select(User).where(User.email == auth.ADMIN_EMAIL)).scalars().all()
        assert len(rows) == 1
        assert check_password_hash(rows[0].password_hash, "newpass999")
        assert not check_password_hash(rows[0].password_hash, "pass12345")
