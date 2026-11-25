from datetime import datetime, timezone

import pytest

from conftest import login_as, make_contest, make_entry, make_request, make_user, post
from models import (AnswerChoice, ApplicationAnswer, ApplicationField, Contest,
                    Entry, EntryMember, FieldOption, db)


@pytest.fixture(autouse=True)
def ctx(app):
    with app.app_context():
        yield


def organiser(email="org@x.org", first="Olga", last="Org"):
    uid = make_user(email=email, first=first, last=last)
    make_request(uid, status="approved")
    return uid


def build(owner_id, slug="c1", team=False):
    cid = make_contest(owner_id, slug=slug)
    if team:
        db.session.get(Contest, cid).entry_kind = "team"
    pet = ApplicationField(contest_id=cid, position=1, label="Favourite pet", kind="single")
    langs = ApplicationField(contest_id=cid, position=2, label="Languages", kind="multiple",
                             allows_other=True)
    about = ApplicationField(contest_id=cid, position=3, label="About you", kind="long_text")
    opt = ApplicationField(contest_id=cid, position=4, label="Optional note",
                           kind="short_text", is_required=False)
    db.session.add_all([pet, langs, about, opt])
    db.session.flush()
    cat = FieldOption(field_id=pet.id, position=1, label="Cat")
    py = FieldOption(field_id=langs.id, position=1, label="Python")
    js = FieldOption(field_id=langs.id, position=2, label="JS")
    db.session.add_all([cat, py, js])
    db.session.commit()
    return cid, {"pet": pet.id, "langs": langs.id, "about": about.id, "opt": opt.id,
                 "cat": cat.id, "py": py.id, "js": js.id}


def add_entry(cid, f, first="Bob", last="Smith", about="I like robots", team_name=None):
    uid = make_user(email=f"{first.lower()}{last.lower()}@x.org", first=first, last=last)
    eid = make_entry(cid, uid)
    if team_name:
        db.session.get(Entry, eid).team_name = team_name
        db.session.get(EntryMember, (eid, uid)).is_captain = True
    db.session.add(ApplicationAnswer(entry_id=eid, field_id=f["pet"], option_id=f["cat"]))
    db.session.add(ApplicationAnswer(entry_id=eid, field_id=f["langs"], value_text="Rust"))
    db.session.flush()
    db.session.add_all([AnswerChoice(entry_id=eid, field_id=f["langs"], option_id=f["py"]),
                        AnswerChoice(entry_id=eid, field_id=f["langs"], option_id=f["js"])])
    db.session.add(ApplicationAnswer(entry_id=eid, field_id=f["about"], value_text=about))
    db.session.commit()
    return eid


def url(cid, suffix=""):
    return f"/organiser/contests/{cid}/responses{suffix}"


def test_owner_sees_answers(client):
    oid = organiser()
    cid, f = build(oid)
    add_entry(cid, f)
    login_as(client, oid)
    r = client.get(url(cid))
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    for s in ("Bob Smith", "bobsmith@x.org", "Cat", "Python; JS; Rust", "I like robots",
              "Favourite pet", "Optional note", "Contest One"):
        assert s in html


def test_empty_state(client):
    oid = organiser()
    cid, _ = build(oid)
    login_as(client, oid)
    assert "No answers yet" in client.get(url(cid)).get_data(as_text=True)


def test_other_organiser_404(client):
    oid = organiser()
    cid, _ = build(oid)
    other = organiser(email="o2@x.org")
    login_as(client, other)
    assert client.get(url(cid)).status_code == 404
    assert client.get(url(cid, ".csv")).status_code == 404


def test_anonymous_redirects(client):
    oid = organiser()
    cid, _ = build(oid)
    r = client.get(url(cid))
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_status_filter(client):
    oid = organiser()
    cid, f = build(oid)
    e1 = add_entry(cid, f, first="Pat", last="Pending")
    e2 = add_entry(cid, f, first="Alan", last="Approved")
    db.session.get(Entry, e2).status = "approved"
    db.session.commit()
    login_as(client, oid)
    html = client.get(url(cid) + "?status=approved").get_data(as_text=True)
    assert "Alan Approved" in html and "Pat Pending" not in html
    html = client.get(url(cid) + "?status=pending").get_data(as_text=True)
    assert "Pat Pending" in html and "Alan Approved" not in html
    html = client.get(url(cid) + "?status=bogus").get_data(as_text=True)
    assert "Pat Pending" in html and "Alan Approved" in html


def test_decide_and_reverse(client):
    oid = organiser()
    cid, f = build(oid)
    eid = add_entry(cid, f)
    login_as(client, oid)
    r = post(client, url(cid, f"/{eid}"), decision="approved", status="pending")
    assert r.status_code == 302
    assert r.headers["Location"].endswith(f"{url(cid)}?status=pending")
    e = db.session.get(Entry, eid)
    assert e.status == "approved" and e.decided_by == oid and e.decided_at is not None
    post(client, url(cid, f"/{eid}"), decision="rejected")
    db.session.expire_all()
    assert db.session.get(Entry, eid).status == "rejected"


def test_decide_bad_input(client):
    oid = organiser()
    cid, f = build(oid)
    eid = add_entry(cid, f)
    cid2, f2 = build(oid, slug="c2")
    eid2 = add_entry(cid2, f2, first="Zed", last="Other")
    login_as(client, oid)
    assert post(client, url(cid, f"/{eid}"), decision="pending").status_code == 400
    assert post(client, url(cid, f"/{eid2}"), decision="approved").status_code == 404
    r = post(client, url(cid, f"/{eid}"), decision="approved", status="evil")
    assert r.headers["Location"].endswith("status=all")


def test_csv_individual(client):
    oid = organiser()
    cid, f = build(oid)
    add_entry(cid, f)
    login_as(client, oid)
    r = client.get(url(cid, ".csv"))
    assert r.status_code == 200
    assert 'filename="c1-answers.csv"' in r.headers["Content-Disposition"]
    assert r.data.startswith(b"\xef\xbb\xbf")
    lines = r.data.decode("utf-8-sig").splitlines()
    assert lines[0] == ("Entry ID,Status,Submitted (UTC),Members,Emails,"
                        "Favourite pet,Languages,About you,Optional note")
    assert "Bob Smith" in lines[1] and "Python; JS; Rust" in lines[1]
    assert lines[1].endswith(",")  # unanswered optional question is empty


def test_csv_team_column(client):
    oid = organiser()
    cid, f = build(oid, team=True)
    add_entry(cid, f, team_name="Robo Team")
    login_as(client, oid)
    lines = client.get(url(cid, ".csv")).data.decode("utf-8-sig").splitlines()
    assert lines[0].startswith("Entry ID,Status,Submitted (UTC),Team,Members,Emails")
    assert "Robo Team" in lines[1]


def test_csv_formula_injection(client):
    oid = organiser()
    cid, f = build(oid)
    add_entry(cid, f, about="=1+1")
    login_as(client, oid)
    text = client.get(url(cid, ".csv")).data.decode("utf-8-sig")
    assert "'=1+1" in text
    assert ",=1+1" not in text
