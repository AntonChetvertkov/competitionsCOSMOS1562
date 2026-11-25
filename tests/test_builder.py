import io
import os
import struct
import zlib

import pytest
from conftest import (login_as, make_contest, make_entry, make_request,
                      make_user, post)
from models import Contest, db

H = {"X-CSRF-Token": "t"}


def png_bytes():
    def chunk(tag, body):
        raw = tag + body
        return struct.pack(">I", len(body)) + raw + struct.pack(">I", zlib.crc32(raw))
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


@pytest.fixture
def org(app, client):
    with app.app_context():
        uid = make_user("org@x.org")
        make_request(uid, "approved")
    login_as(client, uid)
    return uid


@pytest.fixture
def cid(app, org):
    with app.app_context():
        return make_contest(org, "c1", "Contest One")


@pytest.fixture
def uploads(app, tmp_path, monkeypatch):
    monkeypatch.setitem(app.config, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


def form_url(cid):
    return f"/organiser/contests/{cid}/form"


def put(client, cid, doc):
    return client.put(form_url(cid), json=doc, headers=H)


def jpost(client, url, doc=None):
    return client.post(url, json=doc if doc is not None else {}, headers=H)


def q(kind="short_text", label="Name?", **kw):
    return {"kind": kind, "label": label, **kw}


def valid_doc():
    return {"title": "T", "questions": [
        q("short_text", "Name?"),
        q("single", "Pick", options=[{"label": "A"}, {"label": "B"}])]}


# --- new ---------------------------------------------------------------------

def test_new_requires_title_and_creates_draft(app, client, org):
    r = post(client, "/organiser/new", title="   ")
    assert r.status_code in (200, 302)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Contest.id))) == 0
    r = post(client, "/organiser/new", title="  My quiz  ")
    assert r.status_code == 302
    with app.app_context():
        c = db.session.scalars(db.select(Contest)).one()
        assert c.title == "My quiz" and c.status == "draft" and c.owner_id == org
        assert c.slug and c.invite_token is None
        assert r.headers["Location"].endswith(f"/organiser/contests/{c.id}/edit")


def test_new_blocked_for_non_organiser(app, client):
    with app.app_context():
        uid = make_user("plain@x.org")
    login_as(client, uid)
    r = post(client, "/organiser/new", title="X")
    assert r.status_code == 302 and r.headers["Location"].endswith("/organiser")


# --- document ----------------------------------------------------------------

def test_get_document_shape(client, cid):
    d = client.get(form_url(cid)).get_json()
    assert d["id"] == cid and d["status"] == "draft"
    for key in ("title", "description", "thank_you_text", "cover_url", "entry_kind",
                "team_max", "manual_approval", "registration_closes_at", "max_entries",
                "questions_locked", "entry_count", "join_url", "questions"):
        assert key in d
    assert d["join_url"] is None and d["questions"] == [] and d["cover_url"] is None


def test_put_updates_settings_and_questions(client, cid):
    r = put(client, cid, {
        "title": "New", "description": "D", "thank_you_text": "Thanks",
        "entry_kind": "team", "team_max": 4, "manual_approval": True,
        "max_entries": 50, "registration_closes_at": "2026-12-08T17:00:00Z",
        "questions": [
            q("multiple", "Which", help_text="h", is_required=False, allows_other=True,
              options=[{"label": "A"}, {"label": "B"}]),
            q("date", "When"),
        ]})
    assert r.status_code == 200
    d = r.get_json()
    assert d["title"] == "New" and d["entry_kind"] == "team" and d["team_max"] == 4
    assert d["manual_approval"] is True and d["max_entries"] == 50
    assert d["registration_closes_at"] == "2026-12-08T17:00:00Z"
    assert [x["label"] for x in d["questions"]] == ["Which", "When"]
    assert d["questions"][0]["allows_other"] is True
    assert [o["label"] for o in d["questions"][0]["options"]] == ["A", "B"]
    # replace again with fewer questions
    d = put(client, cid, {"questions": [q("number", "N")]}).get_json()
    assert [x["label"] for x in d["questions"]] == ["N"]
    assert client.get(form_url(cid)).get_json() == d


def test_put_offset_datetime_converted_to_utc(client, cid):
    d = put(client, cid, {"registration_closes_at": "2026-12-08T20:00:00+03:00"}).get_json()
    assert d["registration_closes_at"] == "2026-12-08T17:00:00Z"
    d = put(client, cid, {"registration_closes_at": None}).get_json()
    assert d["registration_closes_at"] is None


def test_put_forces_and_clamps(client, cid):
    d = put(client, cid, {
        "title": "x" * 500, "entry_kind": "individual", "team_max": 5,
        "max_entries": 10**9,
        "questions": [q("long_text", "L", allows_other=True, options=[{"label": "z"}])]
    }).get_json()
    assert len(d["title"]) == 200
    assert d["team_max"] is None and d["max_entries"] == 100000
    qq = d["questions"][0]
    assert qq["allows_other"] is False and qq["options"] == []
    d = put(client, cid, {"entry_kind": "team", "team_max": 0}).get_json()
    assert d["team_max"] == 1


def test_put_empty_title_keeps_previous(client, cid):
    d = put(client, cid, {"title": "  "}).get_json()
    assert d["title"] == "Contest One"


@pytest.mark.parametrize("doc,field", [
    ({"entry_kind": "group"}, "entry_kind"),
    ({"title": 5}, "title"),
    ({"max_entries": "x"}, "max_entries"),
    ({"registration_closes_at": "tomorrow"}, "registration_closes_at"),
    ({"questions": [q("bogus")]}, "questions"),
    ({"questions": "no"}, "questions"),
])
def test_put_invalid(client, cid, doc, field):
    r = put(client, cid, doc)
    assert r.status_code == 400
    assert r.get_json() == {"error": "b.err.invalid", "field": field}


def test_put_questions_ignored_when_locked(app, client, cid):
    put(client, cid, {"questions": [q("short_text", "Keep")]})
    with app.app_context():
        make_entry(cid, make_user("p@x.org"))
    d = put(client, cid, {"title": "Renamed", "questions": [q("number", "Other")]}).get_json()
    assert d["questions_locked"] is True and d["entry_count"] == 1
    assert d["title"] == "Renamed"
    assert [x["label"] for x in d["questions"]] == ["Keep"]


def test_put_without_csrf_rejected(client, cid):
    r = client.put(form_url(cid), json={"title": "x"})
    assert r.status_code == 400


# --- publish / close / link ----------------------------------------------------

def publish_url(cid):
    return f"/organiser/contests/{cid}/publish"


def test_publish_errors(app, client, org):
    with app.app_context():
        c = Contest(owner_id=org, slug="fresh2", title="Fresh")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    r = jpost(client, publish_url(cid), {})
    assert r.get_json()["error"] == "b.err.consent"
    r = jpost(client, publish_url(cid), {"consent": True})
    assert r.get_json() == {"error": "b.err.no_questions", "question_index": None}
    put(client, cid, {"questions": [q("short_text", "ok"), q("short_text", "  ")]})
    r = jpost(client, publish_url(cid), {"consent": True})
    assert r.get_json() == {"error": "b.err.empty_label", "question_index": 1}
    put(client, cid, {"questions": [q("short_text", "ok"), q("single", "S")]})
    r = jpost(client, publish_url(cid), {"consent": True})
    assert r.get_json() == {"error": "b.err.options", "question_index": 1}
    put(client, cid, {"questions": [q("dropdown", "S", options=[{"label": "a"}, {"label": ""}])]})
    r = jpost(client, publish_url(cid), {"consent": True})
    assert r.get_json() == {"error": "b.err.options", "question_index": 0}
    with app.app_context():
        c = db.session.get(Contest, cid)
        c.title = " "
        db.session.commit()
    r = jpost(client, publish_url(cid), {"consent": True})
    assert r.get_json()["error"] == "b.err.title"
    with app.app_context():
        assert db.session.get(Contest, cid).status == "draft"


def test_publish_close_reopen_and_link(app, client, org):
    with app.app_context():
        c = Contest(owner_id=org, slug="fresh", title="Fresh")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    put(client, cid, valid_doc())
    d = jpost(client, publish_url(cid), {"consent": True}).get_json()
    assert d["status"] == "published" and d["join_url"]
    with app.app_context():
        c = db.session.get(Contest, cid)
        assert c.invite_token and c.consent_confirmed_at is not None
        old = c.invite_token
        assert d["join_url"].endswith("/join/" + old)

    assert jpost(client, f"/organiser/contests/{cid}/close").get_json()["status"] == "closed"
    assert jpost(client, f"/organiser/contests/{cid}/close").status_code == 400

    # closed -> published again without consent; token is kept
    d = jpost(client, publish_url(cid), {}).get_json()
    assert d["status"] == "published" and d["join_url"].endswith("/join/" + old)

    d = jpost(client, f"/organiser/contests/{cid}/link").get_json()
    assert d["join_url"] and not d["join_url"].endswith("/join/" + old)


def test_close_and_link_need_right_state(client, cid):
    # make_contest creates a draft
    assert jpost(client, f"/organiser/contests/{cid}/close").get_json()["error"] == "b.err.state"
    assert jpost(client, f"/organiser/contests/{cid}/link").status_code == 400


# --- cover ---------------------------------------------------------------------

def cover_url(cid):
    return f"/organiser/contests/{cid}/cover"


def upload(client, cid, data, name="c.png"):
    return client.post(cover_url(cid), headers=H, content_type="multipart/form-data",
                       data={"cover": (io.BytesIO(data), name)})


def test_cover_upload_serve_replace_delete(client, cid, uploads):
    r = upload(client, cid, png_bytes())
    assert r.status_code == 200
    url = r.get_json()["cover_url"]
    files = os.listdir(uploads / "covers")
    assert len(files) == 1 and files[0].endswith(".png") and url.endswith(files[0])
    with client.get(url) as served:
        assert served.status_code == 200 and served.data == png_bytes()
        assert "max-age=86400" in served.headers["Cache-Control"]

    r = upload(client, cid, b"\xff\xd8\xff\xe0" + b"0" * 20, "x.jpeg")
    assert r.status_code == 200
    files = os.listdir(uploads / "covers")
    assert len(files) == 1 and files[0].endswith(".jpg")

    r = client.delete(cover_url(cid), headers=H)
    assert r.status_code == 200 and r.get_json()["cover_url"] is None
    assert os.listdir(uploads / "covers") == []


def test_cover_rejects_fake_and_big(client, cid, uploads):
    assert upload(client, cid, b"just text, not an image").status_code == 400
    assert upload(client, cid, b"").status_code == 400
    big = png_bytes() + b"0" * (2 * 1024 * 1024)
    r = upload(client, cid, big)
    assert r.status_code == 400 and r.get_json()["error"] == "b.err.cover"
    assert not (uploads / "covers").exists() or os.listdir(uploads / "covers") == []


def test_cover_file_missing_404(client, uploads):
    assert client.get("/uploads/covers/nope.png").status_code == 404
    assert client.get("/uploads/covers/../x").status_code == 404


# --- delete ----------------------------------------------------------------------

def test_delete_only_without_entries(app, client, cid, uploads):
    upload(client, cid, png_bytes())
    with app.app_context():
        make_entry(cid, make_user("p@x.org"))
    r = post(client, f"/organiser/contests/{cid}/delete")
    assert r.status_code == 302 and r.headers["Location"].endswith(f"/contests/{cid}/edit")
    with app.app_context():
        assert db.session.get(Contest, cid) is not None
        from models import Entry
        for e in db.session.scalars(db.select(Entry)).all():
            db.session.delete(e)
        db.session.commit()
    assert len(os.listdir(uploads / "covers")) == 1
    r = post(client, f"/organiser/contests/{cid}/delete")
    assert r.status_code == 302 and r.headers["Location"].endswith("/organiser")
    with app.app_context():
        assert db.session.get(Contest, cid) is None
    assert os.listdir(uploads / "covers") == []


# --- ownership -------------------------------------------------------------------

def test_other_organiser_gets_404(app, client, cid):
    with app.app_context():
        other = make_user("other@x.org")
        make_request(other, "approved")
    login_as(client, other)
    assert client.get(form_url(cid)).status_code == 404
    assert put(client, cid, {"title": "hack"}).status_code == 404
    assert jpost(client, publish_url(cid), {"consent": True}).status_code == 404
    assert jpost(client, f"/organiser/contests/{cid}/close").status_code == 404
    assert post(client, f"/organiser/contests/{cid}/delete").status_code == 404
    assert client.get(f"/organiser/contests/{cid}/edit").status_code == 404


# --- dashboard ---------------------------------------------------------------------

def test_dashboard_row_actions(app, client, org):
    with app.app_context():
        a = Contest(owner_id=org, slug="a", title="DraftOne")
        b = Contest(owner_id=org, slug="b", title="LiveOne", status="published",
                    invite_token="tok123")
        db.session.add_all([a, b])
        db.session.commit()
    body = client.get("/organiser").get_data(as_text=True)
    assert "cstatus.draft" in body and "cstatus.published" in body
    assert "/join/tok123" in body
    assert body.count('data-copy="') == 1


def test_entry_kind_frozen_once_entries_exist(app, client):
    """Switching individual <-> team after people answered would break their entries."""
    import json as _json
    from models import Contest, Entry, db as _db
    from conftest import login_as, make_request, make_user
    with app.app_context():
        uid = make_user("kindlock@x.org")
        make_request(uid, "approved")
        c = Contest(owner_id=uid, slug="kindlock", title="T", entry_kind="team")
        _db.session.add(c); _db.session.flush()
        _db.session.add(Entry(contest_id=c.id)); _db.session.commit()
        cid = c.id
    login_as(client, uid)
    with client.session_transaction() as s:
        s["csrf"] = "t"
    doc = client.get(f"/organiser/contests/{cid}/form").get_json()
    doc["entry_kind"] = "individual"
    r = client.put(f"/organiser/contests/{cid}/form", data=_json.dumps(doc),
                   headers={"Content-Type": "application/json", "X-CSRF-Token": "t"})
    assert r.status_code == 200 and r.get_json()["entry_kind"] == "team"
