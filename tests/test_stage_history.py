import datetime

from conftest import candidate


def ago(days):
    """ISO timestamp N วันก่อนเวลาจริง — UI คิดวันจาก Date.now() จึงต้องอิงเวลาปัจจุบัน"""
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days, hours=1)
    return t.isoformat().replace("+00:00", "Z")


def hist(*steps):
    return [{"stage": s, "at": ago(d)} for s, d in steps]


def test_new_candidate_starts_history_at_added_date(open_ats):
    page = open_ats()
    c = page.evaluate("""() => makeCandidate({}, {score:0, breakdown:[], matched:[], missing:[], missingRequired:[]}, {})""")
    assert c["stageHistory"] == [{"stage": "Applied", "at": c["addedAt"]}]


def test_set_stage_appends_dated_entry(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(stage="Applied", stageHistory=hist(("Applied", 5)))]})
    page.evaluate("() => setStage('cand1', 'Screening')")
    h = page.evaluate("() => DB.candidates[0].stageHistory")
    assert [e["stage"] for e in h] == ["Applied", "Screening"]
    assert h[1]["at"] and "inferred" not in h[1]
    # ต้องบันทึกลง localStorage ด้วย
    saved = page.evaluate("() => JSON.parse(localStorage.getItem('hma_ats_v1')).candidates[0].stageHistory")
    assert len(saved) == 2


def test_selecting_same_stage_adds_nothing(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(stage="Interview", stageHistory=hist(("Applied", 5), ("Interview", 2)))]})
    page.evaluate("() => setStage('cand1', 'Interview')")
    assert page.evaluate("() => DB.candidates[0].stageHistory.length") == 2


def test_old_record_history_uses_only_known_dates(open_ats):
    """record ก่อนมีฟีเจอร์: รู้แค่วันที่เพิ่ม — วันที่เข้า Interview ต้องเป็น null ไม่ใช่เดา"""
    page = open_ats({"jobs": [], "candidates": [candidate(stage="Interview")]})
    h = page.evaluate("() => historyOf(DB.candidates[0])")
    assert h == [
        {"stage": "Applied", "at": "2026-07-01T00:00:00.000Z", "inferred": True},
        {"stage": "Interview", "at": None, "inferred": True},
    ]
    assert page.evaluate("() => daysInStage(DB.candidates[0])") is None
    assert page.evaluate("() => isStuck(DB.candidates[0])") is False


def test_old_record_moved_keeps_inferred_part_then_real_entry(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate(stage="Interview")]})
    page.evaluate("() => setStage('cand1', 'Offer')")
    h = page.evaluate("() => DB.candidates[0].stageHistory")
    assert [e["stage"] for e in h] == ["Applied", "Interview", "Offer"]
    assert h[1]["inferred"] is True and "inferred" not in h[2]
    # ไม่รู้ว่าเข้า Interview เมื่อไหร่ → ห้ามนับเวลาที่อยู่ Interview
    assert "Interview" not in page.evaluate("() => pipelineStats(DB.candidates).avgDays")


def test_old_rejected_record_is_not_counted_as_drop_off_from_applied(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(stage="Rejected", closedAt="2026-07-20T00:00:00.000Z")]})
    stats = page.evaluate("() => pipelineStats(DB.candidates)")
    assert stats["dropFrom"] == {}


def test_old_hired_record_counts_toward_days_to_hire(open_ats):
    """closedAt ถูกตั้งตอนเข้า Hired จริง จึงใช้คำนวณวันจนรับเข้าทำงานได้"""
    page = open_ats({"jobs": [], "candidates": [
        candidate(stage="Hired", closedAt="2026-07-21T00:00:00.000Z")]})
    stats = page.evaluate("() => pipelineStats(DB.candidates)")
    assert stats["avgDaysToHire"] == 20
    assert stats["hireN"] == 1


def test_pipeline_stats_from_recorded_history(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(id="a", stage="Hired",
                  stageHistory=hist(("Applied", 30), ("Screening", 26), ("Interview", 20), ("Offer", 10), ("Hired", 6))),
        candidate(id="b", stage="Rejected",
                  stageHistory=hist(("Applied", 12), ("Screening", 10), ("Rejected", 4))),
        candidate(id="c", stage="Interview",
                  stageHistory=hist(("Applied", 9), ("Interview", 3))),
    ]})
    s = page.evaluate("() => pipelineStats(DB.candidates)")
    assert s["avgDays"]["Applied"] == {"avg": 4, "n": 3}         # (4 + 2 + 6) / 3
    assert s["avgDays"]["Screening"] == {"avg": 6, "n": 2}       # (6 + 6) / 2
    assert s["avgDays"]["Interview"] == {"avg": 10, "n": 1}      # c ยังอยู่ Interview → ไม่นับ
    assert s["dropFrom"] == {"Screening": 1}
    assert s["avgDaysToHire"] == 24
    assert s["hireN"] == 1


def test_stuck_only_for_open_cases_over_threshold(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(id="old", name="ค้างนาน", stage="Interview", stageHistory=hist(("Applied", 30), ("Interview", 20))),
        candidate(id="new", name="เพิ่งย้าย", stage="Interview", stageHistory=hist(("Applied", 30), ("Interview", 10))),
        candidate(id="done", name="ปิดแล้ว", stage="Hired", stageHistory=hist(("Applied", 60), ("Hired", 40))),
    ]})
    assert page.evaluate("() => stuckCandidates().map(c => c.id)") == ["old"]


def test_stuck_note_and_sort(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(id="new", name="เพิ่งย้าย", stage="Screening", stageHistory=hist(("Applied", 5), ("Screening", 1))),
        candidate(id="old", name="ค้างนาน", stage="Interview", stageHistory=hist(("Applied", 30), ("Interview", 20))),
    ]})
    page.evaluate("() => { document.querySelector('[data-tab=candidates]').click(); setCandView('table'); }")
    note = page.locator("#stuckNote")
    assert note.is_visible()
    assert "ค้างนาน" in note.inner_text() and "เพิ่งย้าย" not in note.inner_text()
    note.locator("button").click()
    assert page.evaluate("() => document.getElementById('candSort').value") == "stuck"
    assert "ค้างนาน" in page.locator("#candBody tr").first.inner_text()
    assert "⏳ 20 วัน" in page.locator("#candBody tr").first.inner_text()


def test_kanban_card_shows_stuck_chip(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(stage="Interview", stageHistory=hist(("Applied", 30), ("Interview", 20)))]})
    page.evaluate("() => setCandView('board')")
    assert "⏳ 20 วัน" in page.locator("#candBoard .kanban-card").first.inner_text()


def test_detail_modal_shows_timeline(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate(stage="Interview")]})
    page.evaluate("() => setStage('cand1', 'Offer')")
    page.evaluate("() => showCandDetail('cand1')")
    text = page.locator("#detailBody").inner_text()
    assert "ประวัติสถานะ" in text
    assert "ไม่ทราบวันที่" in text            # Interview ของ record เก่า
    assert "ปัจจุบัน · 0 วันแล้ว" in text


def test_scan_result_detail_has_no_timeline(open_ats):
    page = open_ats()
    page.evaluate("""() => {
        scanResults = [{ id:'s1', name:'ผลสแกน', email:'', phone:'', expYears:0,
            education:'', warnings:[], score:50, breakdown:[], matched:[], missing:[],
            missingRequired:[], resumeText:'', status:'ok', jobId:'', fileName:'a.pdf' }];
        showScanDetail('s1');
    }""")
    assert "ประวัติสถานะ" not in page.locator("#detailBody").inner_text()


def test_csv_includes_days_in_stage(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(id="a", name="ค้าง", stage="Interview", stageHistory=hist(("Applied", 30), ("Interview", 20))),
        candidate(id="b", name="ปิด", stage="Hired", stageHistory=hist(("Applied", 30), ("Hired", 20)))]})
    rows = page.evaluate("""() => {
        const out = [];
        const orig = window.downloadCSV;
        window.downloadCSV = r => out.push(r);
        return Promise.resolve(exportCSV()).then(() => { window.downloadCSV = orig; return out[0]; });
    }""")
    i = rows[0].index("Days in Stage")
    assert rows[0][i - 1] == "Stage"
    body = {r[0]: r for r in rows[1:]}
    assert body["ค้าง"][i] == 20
    assert body["ปิด"][i] == ""               # ปิดเคสแล้ว ไม่นับวันค้าง


def test_history_survives_backup_restore(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(stage="Interview", stageHistory=hist(("Applied", 30), ("Interview", 20)))]})
    page.evaluate("""() => {
        const data = JSON.parse(backupPayload());
        DB.candidates = []; saveDB();
        window.confirm = () => true;
        applyRestore(data);
    }""")
    assert page.evaluate("() => DB.candidates[0].stageHistory.length") == 2
    assert page.evaluate("() => daysInStage(DB.candidates[0])") == 20


def test_sample_data_fills_dashboard(open_ats):
    page = open_ats()
    page.evaluate("() => { window.confirm = () => true; seed(); }")
    s = page.evaluate("() => pipelineStats(DB.candidates)")
    assert s["avgDaysToHire"] == 22                   # Ploy: 30 → 8 วันก่อน
    assert s["dropFrom"] == {"Screening": 1}           # Kittipong
    assert [c["name"] for c in page.evaluate("() => stuckCandidates()")] == ["Nattaya Srisuk"]
    kpis = page.locator("#kpiGrid").inner_text()
    assert "22 วัน" in kpis
