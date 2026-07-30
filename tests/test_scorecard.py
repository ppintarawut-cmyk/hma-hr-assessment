from conftest import candidate

WEIGHTS_5 = ("[{id:'c1',weight:3},{id:'c2',weight:2},{id:'c3',weight:2},"
             "{id:'c4',weight:2},{id:'c5',weight:1}]")


def test_calc_total_applies_weights(open_ats):
    page = open_ats()
    total = page.evaluate(
        "() => calcScorecardTotal({c1:4,c2:5,c3:3,c4:4,c5:3}, " + WEIGHTS_5 + ")")
    # (4*3 + 5*2 + 3*2 + 4*2 + 3*1) / (5*10) = 39/50
    assert total == 78


def test_calc_total_excludes_unrated_from_denominator(open_ats):
    page = open_ats()
    total = page.evaluate(
        "() => calcScorecardTotal({c1:4}, [{id:'c1',weight:3},{id:'c2',weight:2}])")
    # 12/15 = 80 — ถ้านับ c2 เป็น 0 จะได้ 48
    assert total == 80


def test_calc_total_returns_null_when_nothing_rated(open_ats):
    page = open_ats()
    assert page.evaluate(
        "() => calcScorecardTotal({}, [{id:'c1',weight:3}])") is None


def test_fresh_db_seeds_five_criteria(open_ats):
    page = open_ats()
    labels = page.evaluate("() => DB.scorecardCriteria.map(c => c.label)")
    assert len(labels) == 5
    assert labels[0] == "ความรู้ทางเทคนิค / ตรงสายงาน"
    assert page.evaluate("() => DB.scorecardCriteria[0].weight") == 3


def test_existing_db_without_criteria_gets_them(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate()]})
    assert page.evaluate("() => DB.scorecardCriteria.length") == 5
    # ข้อมูลเดิมต้องไม่ถูกแตะ
    assert page.evaluate("() => DB.candidates.length") == 1


def test_new_candidate_starts_with_empty_scorecards(open_ats):
    page = open_ats()
    value = page.evaluate("""() => makeCandidate(
        {}, {score:0, breakdown:[], matched:[], missing:[], missingRequired:[]}, {}
    ).scorecards""")
    assert value == []


from conftest import scorecard


def test_table_shows_dash_when_never_evaluated(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate()]})
    cell = page.locator("#candBody tr td").nth(4)
    assert cell.inner_text().strip() == "—"


def test_table_shows_latest_round_score(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(scorecards=[scorecard(id="a", total=72),
                              scorecard(id="b", total=85)])]})
    cell = page.locator("#candBody tr td").nth(4)
    text = cell.inner_text()
    assert "85" in text            # รอบล่าสุด ไม่ใช่ 72 และไม่ใช่ค่าเฉลี่ย 78.5
    assert "72" not in text
    assert "2" in text             # ตัวกำกับจำนวนรอบ


def test_kanban_card_shows_interview_chip(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(scorecards=[scorecard(total=85)])]})
    page.evaluate("() => setCandView('board')")
    card = page.locator("#candBoard .kanban-card").first
    assert "85" in card.inner_text()


def test_kanban_card_has_no_chip_when_never_evaluated(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate()]})
    page.evaluate("() => setCandView('board')")
    card = page.locator("#candBoard .kanban-card").first
    assert "🗣" not in card.inner_text()


def test_detail_section_collapsed_shows_summary(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(scorecards=[scorecard(total=78)])]})
    page.evaluate("() => showCandDetail('cand1')")
    section = page.locator("#scSection")
    assert "ผลสัมภาษณ์" in section.inner_text()
    assert "78" in section.inner_text()
    # ยังไม่กาง — ต้องยังไม่เห็นปุ่มเพิ่มรอบ
    assert section.locator("text=＋ เพิ่มรอบสัมภาษณ์").count() == 0


def test_detail_section_summary_when_never_evaluated(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate()]})
    page.evaluate("() => showCandDetail('cand1')")
    assert "ยังไม่ได้ประเมิน" in page.locator("#scSection").inner_text()


def test_detail_section_expands_and_lists_rounds(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(scorecards=[scorecard(id="a", round="สัมภาษณ์ HR", total=72),
                              scorecard(id="b", round="สัมภาษณ์หัวหน้างาน", total=85)])]})
    page.evaluate("() => showCandDetail('cand1')")
    page.evaluate("() => toggleScSection()")
    text = page.locator("#scSection").inner_text()
    assert "สัมภาษณ์หัวหน้างาน" in text
    assert "สัมภาษณ์ HR" in text
    # ใหม่ก่อนเก่า
    assert text.index("สัมภาษณ์หัวหน้างาน") < text.index("สัมภาษณ์ HR")


def test_round_breakdown_uses_frozen_labels(open_ats):
    """ลบหัวข้อออกจากเกณฑ์ปัจจุบันแล้ว ใบเก่ายังต้องกางดูชื่อหัวข้อเดิมได้"""
    page = open_ats({"jobs": [], "candidates": [
        candidate(scorecards=[scorecard(id="a")])],
        "scorecardCriteria": [{"id": "zz", "label": "หัวข้อใหม่ล้วน", "weight": 1}]})
    page.evaluate("() => showCandDetail('cand1')")
    page.evaluate("() => toggleScSection()")
    page.evaluate("() => toggleScDetail('a')")
    detail = page.locator("#scd-a").inner_text()
    assert "การสื่อสาร" in detail
    assert "หัวข้อใหม่ล้วน" not in detail


def test_scan_result_detail_has_no_scorecard_section(open_ats):
    """detailHTML ใช้ร่วมกับผลสแกนที่ยังไม่ได้บันทึก — ส่วนนี้ต้องไม่โผล่"""
    page = open_ats()
    page.evaluate("""() => {
        scanResults = [{ id:'s1', name:'ผลสแกน', email:'', phone:'', expYears:0,
            education:'', warnings:[], score:50, breakdown:[], matched:[], missing:[],
            missingRequired:[], resumeText:'', status:'ok', jobId:'', fileName:'a.pdf' }];
        showScanDetail('s1');
    }""")
    assert page.locator("#scSection").count() == 0


def _open_form(page):
    page.evaluate("() => showCandDetail('cand1')")
    page.evaluate("() => { localStorage.setItem('hma_ats_sc_open','1'); refreshScorecardSection(); }")
    page.evaluate("() => openScorecardForm()")


def test_form_live_total_updates_as_you_rate(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate()]})
    _open_form(page)
    page.click(".sc-pill[data-crit='c1'][data-val='4']")
    page.click(".sc-pill[data-crit='c2'][data-val='5']")
    page.click(".sc-pill[data-crit='c3'][data-val='3']")
    page.click(".sc-pill[data-crit='c4'][data-val='4']")
    page.click(".sc-pill[data-crit='c5'][data-val='3']")
    assert page.locator("#scTotal").inner_text().strip() == "78"


def test_save_persists_and_updates_table(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate()]})
    _open_form(page)
    page.fill("#scRound", "สัมภาษณ์หัวหน้างาน")
    page.click(".sc-pill[data-crit='c1'][data-val='4']")
    page.fill("#scNote", "ตอบตรงประเด็น")
    page.evaluate("() => saveScorecard()")
    stored = page.evaluate("() => DB.candidates[0].scorecards")
    assert len(stored) == 1
    assert stored[0]["round"] == "สัมภาษณ์หัวหน้างาน"
    assert stored[0]["total"] == 80          # 12/15
    assert len(stored[0]["weightsUsed"]) == 5
    assert "80" in page.locator("#candBody tr td").nth(4).inner_text()


def test_save_refuses_when_nothing_rated(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate()]})
    _open_form(page)
    page.evaluate("() => saveScorecard()")
    assert page.evaluate("() => DB.candidates[0].scorecards.length") == 0


def test_edit_updates_in_place_without_adding_a_round(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(scorecards=[scorecard(id="a", total=78)])]})
    page.evaluate("() => showCandDetail('cand1')")
    page.evaluate("() => { localStorage.setItem('hma_ats_sc_open','1'); refreshScorecardSection(); }")
    page.evaluate("() => editScorecard('a')")
    page.click(".sc-pill[data-crit='c1'][data-val='1']")
    page.evaluate("() => saveScorecard()")
    cards = page.evaluate("() => DB.candidates[0].scorecards")
    assert len(cards) == 1
    assert cards[0]["id"] == "a"
    assert cards[0]["total"] == 60           # (1*3+5*2+3*2+4*2+3*1)/50 = 30/50


def test_delete_removes_the_round(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(scorecards=[scorecard(id="a"), scorecard(id="b")])]})
    page.on("dialog", lambda d: d.accept())
    page.evaluate("() => showCandDetail('cand1')")
    page.evaluate("() => { localStorage.setItem('hma_ats_sc_open','1'); refreshScorecardSection(); }")
    page.evaluate("() => deleteScorecard('a')")
    ids = page.evaluate("() => DB.candidates[0].scorecards.map(s => s.id)")
    assert ids == ["b"]


def test_edit_form_scores_against_frozen_snapshot_not_live_criteria(open_ats):
    """scFormCriteria() ต้องใช้ weightsUsed ที่ freeze ไว้ตอนบันทึก ไม่ใช่ DB.scorecardCriteria
    ปัจจุบัน — ทดสอบนี้จงใจทำให้สองชุดต่างกันสุดขั้ว (5 หัวข้อ vs 1 หัวข้อ) เพื่อไม่ให้สับสนกัน
    เลขคะแนนที่ discriminate: ใช้ weightsUsed (freeze) -> 1*3+5*2+3*2+4*2+3*1 = 30/50 = 60
    ถ้าโค้ดพังแล้วหันไปใช้ DB.scorecardCriteria (c1 หัวข้อเดียว น้ำหนัก 1) แทน ->
    readScForm() จะได้ {c1:1} เทียบกับน้ำหนัก 1 -> 1/5 = 20 ซึ่งไม่ตรงกับ 60
    """
    page = open_ats({"jobs": [], "candidates": [
        candidate(scorecards=[scorecard(id="a")])],
        "scorecardCriteria": [{"id": "c1", "label": "เหลือหัวข้อเดียว", "weight": 1}]})
    page.evaluate("() => showCandDetail('cand1')")
    page.evaluate("() => { localStorage.setItem('hma_ats_sc_open','1'); refreshScorecardSection(); }")
    page.evaluate("() => editScorecard('a')")
    # ฟอร์มต้องกาง 5 แถว (จาก weightsUsed ที่ freeze) ไม่ใช่ 1 แถว (จากเกณฑ์ปัจจุบัน)
    assert page.locator("#scForm .sc-crit").count() == 5
    page.click(".sc-pill[data-crit='c1'][data-val='1']")
    page.evaluate("() => saveScorecard()")
    cards = page.evaluate("() => DB.candidates[0].scorecards")
    assert len(cards) == 1
    assert cards[0]["id"] == "a"
    assert cards[0]["total"] == 60           # (1*3+5*2+3*2+4*2+3*1)/50 = 30/50


def test_saved_scorecard_survives_reload(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate()]})
    _open_form(page)
    page.click(".sc-pill[data-crit='c1'][data-val='4']")
    page.evaluate("() => saveScorecard()")
    page.reload()
    page.wait_for_function("typeof DB !== 'undefined'")
    assert page.evaluate("() => DB.candidates[0].scorecards.length") == 1
