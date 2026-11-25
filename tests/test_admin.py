from conftest import login_as, make_admin, make_request, make_user, post
from models import OrganiserRequest, User, db


def test_admin_page_access(app, client):
    with app.app_context():
        u = make_user()
        a = make_admin()
    login_as(client, u)
    assert client.get("/admin").status_code == 403
    login_as(client, a)
    assert client.get("/admin").status_code == 200


def _setup(app, status="pending"):
    with app.app_context():
        u = make_user()
        a = make_admin()
        rid = make_request(u, status)
    return u, a, rid


def _get(app, rid):
    with app.app_context():
        r = db.session.get(OrganiserRequest, rid)
        u = db.session.get(User, r.user_id)
        return r.status, r.reviewed_by, r.reviewed_at, u.is_organiser


def test_approve(app, client):
    u, a, rid = _setup(app)
    login_as(client, a)
    r = post(client, f"/admin/requests/{rid}", decision="approved")
    assert r.status_code == 302 and r.headers["Location"].endswith("/admin")
    status, by, at, is_org = _get(app, rid)
    assert status == "approved" and by == a and at is not None and is_org is True


def test_reject(app, client):
    u, a, rid = _setup(app)
    login_as(client, a)
    assert post(client, f"/admin/requests/{rid}", decision="rejected").status_code == 302
    status, by, at, is_org = _get(app, rid)
    assert status == "rejected" and by == a and at is not None and is_org is False


def test_already_decided_400(app, client):
    u, a, rid = _setup(app, "approved")
    login_as(client, a)
    assert post(client, f"/admin/requests/{rid}", decision="rejected").status_code == 400
    assert _get(app, rid)[0] == "approved"


def test_bad_decision_400(app, client):
    u, a, rid = _setup(app)
    login_as(client, a)
    assert post(client, f"/admin/requests/{rid}", decision="maybe").status_code == 400
    assert post(client, f"/admin/requests/{rid}").status_code == 400
    assert _get(app, rid)[0] == "pending"


def test_non_admin_post_403(app, client):
    u, a, rid = _setup(app)
    login_as(client, u)
    assert post(client, f"/admin/requests/{rid}", decision="approved").status_code == 403
    assert _get(app, rid)[0] == "pending"


def test_unknown_request_404(app, client):
    u, a, rid = _setup(app)
    login_as(client, a)
    assert post(client, "/admin/requests/9999", decision="approved").status_code == 404
