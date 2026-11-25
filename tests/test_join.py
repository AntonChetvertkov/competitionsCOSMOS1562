from datetime import datetime, timedelta, timezone

from conftest import login_as, make_contest, make_user, post
from models import (ApplicationAnswer, ApplicationField, Contest, Entry,
                    EntryMember, FieldOption, db)

TOKEN = "tok123"


def build(owner, fields=(), status="published", **contest_kw):
    """fields: (kind, label, required, allows_other, [option labels]). Returns ids."""
    cid = make_contest(owner)
    c = db.session.get(Contest, cid)
    c.status = status
    c.invite_token = TOKEN
    for k, v in contest_kw.items():
        setattr(c, k, v)
    ids = []
    for i, (kind, label, req, other, opts) in enumerate(fields):
        f = ApplicationField(contest_id=cid, position=i, label=label, kind=kind,
                             is_required=req, allows_other=other)
        for j, o in enumerate(opts):
            f.options.append(FieldOption(position=j, label=o))
        db.session.add(f)
        db.session.flush()
        ids.append((f.id, [o.id for o in f.options]))
    db.session.commit()
    return cid, ids


def setup(app, fields=(), **kw):
    with app.app_context():
        owner = make_user("owner@x.org")
        me = make_user("me@x.org")
        cid, ids = build(owner, fields, **kw)
    return owner, me, cid, ids


def answers_of(app, cid, uid=None):
    with app.app_context():
        e = db.session.execute(db.select(Entry).where(Entry.contest_id == cid)).scalars().first()
        if e is None:
            return None
        return {a.field_id: a for a in e.answers}, e


def submit(client, **data):
    return post(client, f"/join/{TOKEN}", **data)


def test_anonymous_redirected(app, client):
    setup(app)
    r = client.get(f"/join/{TOKEN}")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_unknown_and_draft_404(app, client):
    owner, me, cid, _ = setup(app, status="draft")
    login_as(client, me)
    assert client.get(f"/join/{TOKEN}").status_code == 404
    assert client.get("/join/nope").status_code == 404


def test_short_long_number_date(app, client):
    owner, me, cid, ids = setup(app, [
        ("short_text", "Name", True, False, []),
        ("long_text", "About", False, False, []),
        ("number", "Age", True, False, []),
        ("number", "Score", False, False, []),
        ("date", "Born", True, False, []),
    ])
    login_as(client, me)
    assert client.get(f"/join/{TOKEN}").status_code == 200
    q = [i for i, _ in ids]
    r = submit(client, **{f"q{q[0]}": "  Zed  ", f"q{q[2]}": "12.0", f"q{q[3]}": "12.50",
                          f"q{q[4]}": "2010-05-04"})
    assert r.status_code == 302 and "sent=1" in r.headers["Location"]
    got, e = answers_of(app, cid)
    with app.app_context():
        pass
    assert got[q[0]].value_text == "Zed"
    assert q[1] not in got                       # optional, left empty
    assert got[q[2]].value_text == "12"
    assert got[q[3]].value_text == "12.5"
    assert got[q[4]].value_text == "2010-05-04"
    assert e.status == "approved"
    body = client.get(r.headers["Location"]).get_data(as_text=True)
    assert "Thanks, your answers are in." in body


def test_bad_number_and_date_rejected(app, client):
    owner, me, cid, ids = setup(app, [
        ("number", "Age", True, False, []), ("date", "Born", True, False, [])])
    login_as(client, me)
    for bad_n, bad_d in (("abc", "2010-05-04"), ("5", "2010-13-45"), ("nan", "2010-05-04"),
                         ("5", "04.05.2010")):
        r = submit(client, **{f"q{ids[0][0]}": bad_n, f"q{ids[1][0]}": bad_d})
        assert r.status_code == 200 and "q-err" in r.get_data(as_text=True)
    assert answers_of(app, cid) is None


def test_required_missing_nothing_saved_and_values_kept(app, client):
    owner, me, cid, ids = setup(app, [
        ("short_text", "A", True, False, []), ("short_text", "B", True, False, [])])
    login_as(client, me)
    r = submit(client, **{f"q{ids[1][0]}": "keepme"})
    body = r.get_data(as_text=True)
    assert r.status_code == 200 and "q-err" in body and "keepme" in body
    assert answers_of(app, cid) is None


def test_single_dropdown_other(app, client):
    owner, me, cid, ids = setup(app, [
        ("single", "S", True, True, ["a", "b"]),
        ("dropdown", "D", True, True, ["x", "y"]),
        ("single", "S2", False, False, ["p", "q"]),
    ])
    login_as(client, me)
    (s, so), (d, do), (s2, s2o) = ids
    r = submit(client, **{f"q{s}": so[1], f"q{d}": "__other__", f"q{d}_other": " custom ",
                          f"q{s2}": s2o[0]})
    assert r.status_code == 302
    got, _ = answers_of(app, cid)
    with app.app_context():
        assert db.session.get(ApplicationAnswer, (got[s].entry_id, s)).option_id == so[1]
        assert got[s].value_text is None
        assert got[d].option_id is None and got[d].value_text == "custom"
        assert got[s2].option_id == s2o[0]


def test_other_needs_text_and_foreign_option_rejected(app, client):
    owner, me, cid, ids = setup(app, [
        ("single", "S", True, True, ["a"]), ("single", "T", True, False, ["b"])])
    login_as(client, me)
    (s, so), (t, to) = ids
    r = submit(client, **{f"q{s}": "__other__", f"q{s}_other": "  ", f"q{t}": to[0]})
    assert "q-err" in r.get_data(as_text=True)
    r = submit(client, **{f"q{s}": to[0], f"q{t}": to[0]})        # option of another field
    assert "q-err" in r.get_data(as_text=True)
    r = submit(client, **{f"q{s}": so[0], f"q{t}": "__other__", f"q{t}_other": "z"})  # other not allowed
    assert "q-err" in r.get_data(as_text=True)
    assert answers_of(app, cid) is None


def test_multiple_with_other(app, client):
    owner, me, cid, ids = setup(app, [("multiple", "M", True, True, ["a", "b", "c"])])
    login_as(client, me)
    (m, mo), = ids
    r = submit(client, **{f"q{m}": [mo[0], mo[2], "__other__"], f"q{m}_other": "more"})
    assert r.status_code == 302
    got, _ = answers_of(app, cid)
    with app.app_context():
        a = db.session.get(ApplicationAnswer, (got[m].entry_id, m))
        assert sorted(c.option_id for c in a.choices) == [mo[0], mo[2]]
        assert a.value_text == "more" and a.option_id is None
        assert a.display() == "a; c; more"


def test_multiple_required_and_bad_option(app, client):
    owner, me, cid, ids = setup(app, [("multiple", "M", True, False, ["a"])])
    login_as(client, me)
    (m, mo), = ids
    assert "q-err" in submit(client).get_data(as_text=True)
    assert "q-err" in submit(client, **{f"q{m}": "99999"}).get_data(as_text=True)
    assert answers_of(app, cid) is None


def test_manual_approval_pending(app, client):
    owner, me, cid, ids = setup(app, manual_approval=True)
    login_as(client, me)
    r = submit(client)
    assert r.status_code == 302
    _, e = answers_of(app, cid)
    assert e.status == "pending"
    assert "will review" in client.get(f"/join/{TOKEN}?sent=1").get_data(as_text=True)


def test_second_submit_edits_and_keeps_status(app, client):
    owner, me, cid, ids = setup(app, [
        ("short_text", "A", True, False, []),
        ("multiple", "M", False, False, ["a", "b"])], manual_approval=True)
    login_as(client, me)
    (a, _), (m, mo) = ids
    submit(client, **{f"q{a}": "one", f"q{m}": mo[0]})
    with app.app_context():
        e = db.session.execute(db.select(Entry)).scalars().one()
        e.status = "approved"
        db.session.commit()
    page = client.get(f"/join/{TOKEN}").get_data(as_text=True)
    assert 'value="one"' in page
    submit(client, **{f"q{a}": "two", f"q{m}": mo[1]})
    got, e = answers_of(app, cid)
    with app.app_context():
        assert db.session.execute(db.select(db.func.count(Entry.id))).scalar() == 1
        assert got[a].value_text == "two"
        assert [c.option_id for c in db.session.get(
            ApplicationAnswer, (e.id, m)).choices] == [mo[1]]
    assert e.status == "approved"


def test_after_deadline_readonly_no_edit(app, client):
    owner, me, cid, ids = setup(app, [("short_text", "A", True, False, [])])
    login_as(client, me)
    submit(client, **{f"q{ids[0][0]}": "orig"})
    with app.app_context():
        db.session.get(Contest, cid).registration_closes_at = (
            datetime.now(timezone.utc) - timedelta(days=1))
        db.session.commit()
    page = client.get(f"/join/{TOKEN}").get_data(as_text=True)
    assert "orig" in page and "<form class=\"form join-form\"" not in page
    submit(client, **{f"q{ids[0][0]}": "changed"})
    got, _ = answers_of(app, cid)
    assert got[ids[0][0]].value_text == "orig"


def test_closed_contest_blocks_new(app, client):
    owner, me, cid, _ = setup(app, status="closed")
    login_as(client, me)
    assert client.get(f"/join/{TOKEN}").status_code == 403
    submit(client)
    assert answers_of(app, cid) is None


def test_deadline_blocks_new(app, client):
    owner, me, cid, _ = setup(
        app, registration_closes_at=datetime.now(timezone.utc) - timedelta(hours=1))
    login_as(client, me)
    r = submit(client)
    assert r.status_code == 403 and "deadline" in r.get_data(as_text=True)
    assert answers_of(app, cid) is None


def test_full_blocks_new_entry(app, client):
    owner, me, cid, _ = setup(app, max_entries=1)
    with app.app_context():
        other = make_user("o2@x.org")
        e = Entry(contest_id=cid)
        db.session.add(e)
        db.session.flush()
        db.session.add(EntryMember(entry_id=e.id, user_id=other, is_captain=True))
        db.session.commit()
    login_as(client, me)
    r = submit(client)
    assert r.status_code == 403
    with app.app_context():
        assert db.session.execute(db.select(db.func.count(Entry.id))).scalar() == 1


def test_team_captain_and_join(app, client):
    owner, me, cid, ids = setup(app, entry_kind="team", team_max=2)
    with app.app_context():
        mate = make_user("mate@x.org")
        third = make_user("third@x.org")
    login_as(client, me)
    r = submit(client)
    assert "q-err" in r.get_data(as_text=True)               # no team name
    assert answers_of(app, cid) is None
    r = submit(client, team_name="Rockets")
    assert r.status_code == 302
    _, e = answers_of(app, cid)
    code = e.join_code
    assert e.team_name == "Rockets" and code
    thanks = client.get(r.headers["Location"]).get_data(as_text=True)
    assert code in thanks and f"/team/{code}" in thanks
    with app.app_context():
        m = db.session.execute(db.select(EntryMember)).scalars().one()
        assert m.is_captain

    assert "Rockets" in login_get(client, mate, f"/team/{code}")
    r = post(client, f"/team/{code}")
    assert r.status_code == 302 and r.headers["Location"].endswith("/lms")
    with app.app_context():
        assert db.session.execute(db.select(db.func.count(EntryMember.user_id))).scalar() == 2
    # already in this team: just redirect
    assert post(client, f"/team/{code}").status_code == 302
    # team full
    login_as(client, third)
    r = post(client, f"/team/{code}")
    with app.app_context():
        assert db.session.execute(db.select(db.func.count(EntryMember.user_id))).scalar() == 2
    assert "full" in client.get(f"/team/{code}").get_data(as_text=True)


def login_get(client, uid, url):
    login_as(client, uid)
    return client.get(url).get_data(as_text=True)


def test_team_join_refused_when_in_other_entry_or_closed(app, client):
    owner, me, cid, ids = setup(app, entry_kind="team")
    with app.app_context():
        mate = make_user("mate@x.org")
        e = Entry(contest_id=cid, team_name="T", join_code="CODE1", status="approved")
        db.session.add(e)
        db.session.flush()
        db.session.add(EntryMember(entry_id=e.id, user_id=owner, is_captain=True))
        e1_id = e.id
        e2 = Entry(contest_id=cid, team_name="U", join_code="CODE2", status="approved")
        db.session.add(e2)
        db.session.flush()
        db.session.add(EntryMember(entry_id=e2.id, user_id=mate, is_captain=True))
        db.session.commit()
    login_as(client, mate)
    post(client, "/team/CODE1")                      # mate already captain of CODE2
    with app.app_context():
        assert db.session.execute(
            db.select(db.func.count(EntryMember.user_id)).where(EntryMember.entry_id == e1_id)
        ).scalar() == 1
    login_as(client, me)
    with app.app_context():
        db.session.get(Contest, cid).status = "closed"
        db.session.commit()
    post(client, "/team/CODE1")
    with app.app_context():
        assert db.session.execute(db.select(db.func.count(EntryMember.user_id))).scalar() == 2
    assert client.get("/team/NOPE").status_code == 404


def test_leave_member_ok_captain_refused(app, client):
    owner, me, cid, ids = setup(app, entry_kind="team")
    with app.app_context():
        e = Entry(contest_id=cid, team_name="T", join_code="CODE1", status="approved")
        db.session.add(e)
        db.session.flush()
        db.session.add(EntryMember(entry_id=e.id, user_id=owner, is_captain=True))
        db.session.add(EntryMember(entry_id=e.id, user_id=me))
        db.session.commit()
    # captain refused
    login_as(client, owner)
    post(client, "/team/CODE1/leave")
    with app.app_context():
        assert db.session.execute(db.select(db.func.count(EntryMember.user_id))).scalar() == 2
    # member sees read-only form with Leave, and can leave
    login_as(client, me)
    page = client.get(f"/join/{TOKEN}").get_data(as_text=True)
    assert "/team/CODE1/leave" in page
    r = post(client, "/team/CODE1/leave")
    assert r.status_code == 302
    with app.app_context():
        assert db.session.execute(db.select(db.func.count(EntryMember.user_id))).scalar() == 1


def test_lms_shows_team_and_links(app, client):
    owner, me, cid, ids = setup(app, entry_kind="team")
    login_as(client, me)
    submit(client, team_name="Rockets")
    body = client.get("/lms").get_data(as_text=True)
    assert "Rockets" in body and f"/join/{TOKEN}" in body and "Edit answers" in body


def test_preview_owner_only_and_draft(app, client):
    owner, me, cid, ids = setup(app, [("short_text", "A", True, False, [])], status="draft")
    login_as(client, me)
    assert client.get(f"/organiser/contests/{cid}/preview").status_code == 404
    login_as(client, owner)
    r = client.get(f"/organiser/contests/{cid}/preview")
    body = r.get_data(as_text=True)
    assert r.status_code == 200 and "Preview:" in body and "disabled" in body
    assert 'action="/join' not in body


def test_preview_anonymous_redirects(app, client):
    owner, me, cid, _ = setup(app)
    assert client.get(f"/organiser/contests/{cid}/preview").status_code == 302
