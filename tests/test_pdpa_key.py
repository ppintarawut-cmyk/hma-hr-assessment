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
    # cloud-only and out of reach in this headless test).
    page.evaluate("() => { currentAdmin = { role: 'superadmin' }; }")

    # Drive the exact delete path the "Candidates" page row builds — read the
    # candidate off getCandidateView() (what the row renderer iterates) and build
    # the same rowKey the 🗑 button's onclick encodes.
    page.evaluate("""
        () => {
            const p = getCandidateView()[0];
            const rowKey = JSON.stringify({
                fn: (p.name || '').split(' ')[0],
                ln: (p.name || '').split(' ').slice(1).join(' '),
                candKey: candKey(p),
            });
            deleteApplicantData(encodeURIComponent(rowKey));
        }
    """)

    remaining_recs = page.evaluate(
        "() => JSON.parse(localStorage.getItem('hma_exam_records') || '[]').length")
    remaining_snaps = page.evaluate(
        "() => JSON.parse(localStorage.getItem('hma_result_snapshots') || '[]').length")
    assert remaining_recs == 0
    assert remaining_snaps == 0
