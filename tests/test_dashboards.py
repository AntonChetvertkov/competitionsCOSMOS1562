from conftest import (login_as, make_contest, make_entry, make_request,
                      make_user, post)
from models import OrganiserRequest, db


def test_anonymous_redirected_to_login(client):
    for url in ("/lms", "/organiser", "/admin"):
        r = client.get(url)
        assert r.status_code == 302
        loc = r.headers["Location"]
        assert "/login" in loc and "next=" in loc and url.lstrip("/") in loc


def test_me_shows_only_own_entries(app, client):
    with app.app_context():
        me = make_user("me@x.org")
        other = make_user("o@x.org")
        owner = make_user("own@x.org")
        c1 = make_contest(owner, "mine", "ZebraContestMine")
        c2 = make_contest(owner, "theirs", "GiraffeContestTheirs")
        make_entry(c1, me)
        make_entry(c2, other)
    login_as(client, me)
    r = client.get("/lms")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "ZebraContestMine" in body
    assert "GiraffeContestTheirs" not in body


def _requests(app, uid):
    with app.app_context():
        return db.session.execute(
            db.select(OrganiserRequest).where(OrganiserRequest.user_id == uid)
        ).scalars().all()


def test_organiser_request_flow(app, client):
    with app.app_context():
        uid = make_user()
    login_as(client, uid)
    r = post(client, "/organiser", organisation="Hampton School", message="hi")
    assert r.status_code == 302
    reqs = _requests(app, uid)
    assert len(reqs) == 1 and reqs[0].status == "pending"
    assert reqs[0].organisation == "Hampton School"
    post(client, "/organiser", organisation="Another")
    assert len(_requests(app, uid)) == 1


def test_empty_organisation_refused(app, client):
    with app.app_context():
        uid = make_user()
    login_as(client, uid)
    post(client, "/organiser", organisation="   ")
    assert _requests(app, uid) == []


def test_organiser_new_gating(app, client):
    with app.app_context():
        uid = make_user()
    login_as(client, uid)
    r = client.get("/organiser/new")
    assert r.status_code == 302 and r.headers["Location"].endswith("/organiser")
    with app.app_context():
        make_request(uid, "approved")
    assert client.get("/organiser/new").status_code == 200


def test_organiser_lists_only_own_contests(app, client):
    with app.app_context():
        uid = make_user()
        other = make_user("o@x.org")
        make_request(uid, "approved")
        make_contest(uid, "a", "OwnedByMeXyz")
        make_contest(other, "b", "OwnedByOtherQrs")
    login_as(client, uid)
    r = client.get("/organiser")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "OwnedByMeXyz" in body
    assert "OwnedByOtherQrs" not in body


def test_old_me_url_redirects_to_lms(client):
    r = client.get("/me")
    assert r.status_code == 301 and r.headers["Location"].endswith("/lms")
