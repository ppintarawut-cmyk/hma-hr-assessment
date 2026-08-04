import json

from conftest import exam_record, legacy_exam_record, legacy_exam_record_with_email


def test_exam_page_opens_on_landing(open_exam):
    page = open_exam()
    assert page.locator("#p-landing").is_visible()


def test_seeded_records_reach_the_page(open_exam):
    page = open_exam(exam_records=[exam_record()])
    count = page.evaluate(
        "() => JSON.parse(localStorage.getItem('hma_exam_records') || '[]').length")
    assert count == 1


def test_cand_key_prefers_the_new_field(open_exam):
    page = open_exam()
    assert page.evaluate(
        "() => candKey({candidate_key:'a@b.com', email:'zzz@b.com'})") == "a@b.com"


def test_cand_key_lowercases_the_email_fallback(open_exam):
    page = open_exam()
    assert page.evaluate("() => candKey({email:'Somchai@Example.COM'})") == "somchai@example.com"


def test_cand_key_falls_back_to_legacy_exam_record_field(open_exam):
    page = open_exam()
    assert page.evaluate("() => candKey({national_id:'1234567890123'})") == "1234567890123"


def test_cand_key_falls_back_to_legacy_snapshot_field(open_exam):
    page = open_exam()
    assert page.evaluate("() => candKey({nid:'1234567890123'})") == "1234567890123"


def test_cand_key_returns_empty_string_when_nothing_identifies_the_row(open_exam):
    page = open_exam()
    assert page.evaluate("() => candKey({})") == ""


def test_legacy_records_still_group_into_candidates(open_exam):
    page = open_exam(exam_records=[legacy_exam_record()])
    keys = page.evaluate("() => getCandidateProfiles().map(p => p.candidate_key)")
    assert keys == ["1234567890123"]


def test_deleting_a_legacy_candidate_removes_both_the_exam_record_and_the_snapshot(open_exam):
    """F1 regression (PDPA): a real pre-migration candidate is keyed by *email* in
    hma_exam_records (which carries both national_id and email) but keyed by
    *national_id* in hma_result_snapshots (which never carried email at all).
    Deleting by the exam-record key alone must not leave the snapshot — which holds
    the candidate's name, position, experience and per-section scores — behind.
    """
    legacy_rec = legacy_exam_record_with_email()
    legacy_snap = {
        # No candidate_key, no email — the real shape of a pre-migration snapshot.
        "nid": legacy_rec["national_id"],
        "name": legacy_rec["name"],
        "pos": legacy_rec["position"],
        "exp": legacy_rec["experience"],
        "datetime": legacy_rec["datetime"],
        "sessions": [],
    }
    page = open_exam(exam_records=[legacy_rec], result_snapshots=[legacy_snap])
    page.on("dialog", lambda dialog: dialog.accept())

    # Grant delete rights the way the guard checks it (admin login itself is
    # cloud-only and out of reach in this headless test), then render the real
    # "Candidates" table so its actual 🗑 delete button exists in the DOM.
    page.evaluate("() => { currentAdmin = { role: 'superadmin' }; nav('p-candidates'); }")

    # F12: click the rendered 🗑 button itself instead of hand-building an
    # equivalent rowKey object in JS. renderCandidatesPage() (producer) encodes
    # the onclick's rowKey and deleteApplicantData() (consumer) decodes it — if
    # the two ever disagree on the field name, hand-building the object here
    # would still pass while the real button silently deletes nothing (exactly
    # the failure mode the brief called out). Clicking exercises both sides.
    page.locator('#cand-tbody button[title="ลบผู้สมัครนี้"]').click()

    remaining_recs = page.evaluate(
        "() => JSON.parse(localStorage.getItem('hma_exam_records') || '[]').length")
    remaining_snaps = page.evaluate(
        "() => JSON.parse(localStorage.getItem('hma_result_snapshots') || '[]').length")
    assert remaining_recs == 0
    assert remaining_snaps == 0


def _legacy_snapshot_for(legacy_rec, **over):
    """Real shape of a pre-migration result_snapshot: keyed by national ID only —
    no candidate_key, no email at all (see legacy_exam_record_with_email's docstring
    for why the two collections end up keyed differently for the same person)."""
    snap = {
        "nid": legacy_rec["national_id"],
        "name": legacy_rec["name"],
        "pos": legacy_rec["position"],
        "exp": legacy_rec["experience"],
        "datetime": legacy_rec["datetime"],
        "sessions": [],
    }
    snap.update(over)
    return snap


def test_admin_score_dashboard_reaches_a_legacy_candidates_snapshot(open_exam):
    """F9 regression: adminOpenScoreDash's real caller (the "📊 แดชบอร์ดคะแนน" button)
    passes candKey(indivExportData.rows[0]) — an exam-record-derived key, which for a
    pre-migration candidate is their *email*. The snapshot itself is keyed by
    *national ID*. Comparing the two directly finds nothing, so HR sees "ยังไม่มี
    ข้อมูลแดชบอร์ดคะแนน" for every legacy candidate — a regression from before this
    migration, when both sides were national IDs.
    """
    legacy_rec = legacy_exam_record_with_email()
    legacy_snap = _legacy_snapshot_for(legacy_rec)
    page = open_exam(exam_records=[legacy_rec], result_snapshots=[legacy_snap])

    # The exact key the real caller passes: an exam-record-derived candKey.
    exam_key = page.evaluate(
        "() => candKey(JSON.parse(localStorage.getItem('hma_exam_records'))[0])")
    assert exam_key == legacy_rec["email"]

    has_dash = page.evaluate(f"() => adminHasScoreDash({json.dumps(exam_key)})")
    assert has_dash is True

    page.evaluate(f"() => adminOpenScoreDash({json.dumps(exam_key)})")
    reached_name = page.evaluate("() => applicant && applicant.name")
    assert reached_name == legacy_rec["name"]


def test_completing_an_attempt_updates_a_legacy_unsealed_snapshot_instead_of_duplicating_it(open_exam):
    """F10 regression: saveResultSnapshot() matches an existing unsealed snapshot by
    candKey(x) === candKey(snap) — but candKey(snap) is always the email
    (applicantKey), while a pre-migration candidate's still-unsealed snapshot is
    keyed by national ID. Finishing that in-flight attempt now appends a second
    snapshot row instead of updating the first one.
    """
    legacy_rec = legacy_exam_record_with_email()
    legacy_snap = _legacy_snapshot_for(legacy_rec)   # unsealed: no `_sealed` field
    page = open_exam(exam_records=[legacy_rec], result_snapshots=[legacy_snap])

    # Candidate resumes and completes their attempt: applicant carries the same
    # email/national ID as the legacy records, one session finishes, and
    # saveResultSnapshot() runs — the same call doSubmit() makes after a completed
    # session (index.html's setTimeout(saveResultSnapshot, 220)).
    page.evaluate(f"""
        () => {{
            applicant = {{
                name: {json.dumps(legacy_rec["name"])},
                pos: {json.dumps(legacy_rec["position"])},
                nid: {json.dumps(legacy_rec["national_id"])},
                email: {json.dumps(legacy_rec["email"])},
                exp: {legacy_rec["experience"]},
            }};
            sessions = [{{
                test: {{ code:'IQ', name:'IQ', nameTH:'ไอคิว', passing:60, mins:20 }},
                status:'completed', score:80, outcome:'P', raw:8, maxP:10,
                sections:{{}}, percentile:null, remainSecs:100, violations:[],
            }}];
            saveResultSnapshot();
        }}
    """)

    snaps = page.evaluate(
        "() => JSON.parse(localStorage.getItem('hma_result_snapshots') || '[]')")
    assert len(snaps) == 1
