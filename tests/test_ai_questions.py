from conftest import candidate
from test_ai_detect import AI_SUMMARY, HUMAN


def questions(page, text):
    return page.evaluate("t => aiInterviewQuestions(detectAIWriting(t))", text)


def test_human_resume_gets_no_questions(open_ats):
    assert questions(open_ats(), HUMAN) == []


def test_ai_summary_maps_phrases_to_themed_questions(open_ats):
    qs = questions(open_ats(), AI_SUMMARY)
    texts = [q["q"] for q in qs]
    assert 1 <= len(qs) <= 6
    assert len(set(texts)) == len(texts)                      # ไม่มีคำถามซ้ำ
    assert all(q["section"] == "summary" for q in qs)         # ถามเฉพาะส่วนที่พบสัญญาณ
    assert any("ผลงานชิ้นไหนที่คุณภูมิใจ" in t for t in texts)   # results-driven / proven track record
    assert any("กระบวนการไหนที่คุณปรับ" in t for t in texts)     # streamline / elevate
    # แต่ละคำถามบอกที่มา (บรรทัดใน resume)
    assert all(q["basis"] for q in qs)


def test_flagged_experience_line_gets_question_quoting_it(open_ats):
    text = HUMAN.replace(
        "- Kept customer records in Salesforce and followed up every month",
        "- Spearheaded a results-driven initiative leveraging Salesforce to streamline follow-ups")
    qs = questions(open_ats(), text)
    exp = [q for q in qs if q["section"] == "experience"]
    assert len(exp) == 1
    assert "Spearheaded a results-driven initiative" in exp[0]["q"]
    assert exp[0]["q"].startswith("ช่วยเล่างานที่เขียนว่า")


def test_chatbot_leftover_gets_one_neutral_preparation_question(open_ats):
    text = HUMAN + "\n\nHere is a polished version of your resume. Feel free to adjust it for [Company Name]."
    qs = questions(open_ats(), text)
    prep = [q for q in qs if "เตรียมอย่างไร" in q["q"]]
    assert len(prep) == 1
    assert "โกง" not in prep[0]["q"]


def test_long_line_is_truncated_in_quote(open_ats):
    page = open_ats()
    quoted = page.evaluate("() => aiQuote('- ' + 'x'.repeat(200))")
    assert len(quoted) <= 80 and quoted.endswith("…")
    assert not quoted.startswith("-")


def test_question_count_is_capped(open_ats):
    lines = "\n".join(
        f"- Spearheaded project {i} with a results-driven, proven track record to streamline work"
        for i in range(12))
    text = "Somchai\nsomchai@example.com\n\nEXPERIENCE\n2018 - Present  Engineer\n" + lines
    assert len(questions(open_ats(), text)) == 6


def test_detail_modal_lists_questions_with_checkboxes(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate(resumeText=AI_SUMMARY)]})
    page.evaluate("() => showCandDetail('cand1')")
    body = page.locator("#detailBody")
    assert "คำถามสัมภาษณ์แนะนำ" in body.inner_text()
    picks = body.locator("#aiQuestions .aiq-pick")
    assert picks.count() >= 2
    assert all(picks.nth(i).is_checked() for i in range(picks.count()))


def test_no_question_block_for_human_resume(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate(resumeText=HUMAN)]})
    page.evaluate("() => showCandDetail('cand1')")
    assert page.locator("#aiQuestions").count() == 0


def test_insert_puts_only_checked_questions_into_scorecard_note(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate(resumeText=AI_SUMMARY)]})
    page.evaluate("() => { localStorage.setItem('hma_ats_sc_open','0'); showCandDetail('cand1'); }")
    picks = page.locator("#aiQuestions .aiq-pick")
    first_q = page.evaluate("() => aiInterviewQuestions(detectAIWriting(currentDetail.resumeText))[0].q")
    second_q = page.evaluate("() => aiInterviewQuestions(detectAIWriting(currentDetail.resumeText))[1].q")
    picks.nth(1).uncheck()
    page.evaluate("() => insertAiQuestions()")
    note = page.locator("#scNote").input_value()           # ฟอร์มต้องถูกเปิดให้เอง
    assert "□ " + first_q in note
    assert second_q not in note


def test_insert_keeps_ratings_already_entered(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate(resumeText=AI_SUMMARY)]})
    page.evaluate("() => { localStorage.setItem('hma_ats_sc_open','1'); showCandDetail('cand1'); openScorecardForm(); }")
    page.locator('#scForm .sc-pill[data-crit="c1"][data-val="4"]').click()
    page.locator("#scNote").fill("ตอบคล่อง")
    page.evaluate("() => insertAiQuestions()")
    note = page.locator("#scNote").input_value()
    assert note.startswith("ตอบคล่อง\n\nคำถามจากส่วนที่พบสัญญาณ AI:")
    assert page.locator('#scForm .sc-pill.on[data-crit="c1"]').get_attribute("data-val") == "4"


def test_inserted_questions_are_saved_with_the_scorecard(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate(resumeText=AI_SUMMARY)]})
    page.evaluate("() => { showCandDetail('cand1'); insertAiQuestions(); }")
    page.locator('#scForm .sc-pill[data-crit="c1"][data-val="4"]').click()
    page.evaluate("() => saveScorecard()")
    saved = page.evaluate("() => JSON.parse(localStorage.getItem('hma_ats_v1')).candidates[0].scorecards[0].note")
    assert saved.startswith("คำถามจากส่วนที่พบสัญญาณ AI:\n□ ")


def test_scan_result_offers_copy_but_not_insert(open_ats):
    page = open_ats()
    page.evaluate("""t => {
        scanResults = [{ id:'s1', name:'ผลสแกน', email:'', phone:'', expYears:0,
            education:'', warnings:[], score:50, breakdown:[], matched:[], missing:[],
            missingRequired:[], resumeText:t, status:'ok', jobId:'', fileName:'a.pdf' }];
        showScanDetail('s1');
    }""", AI_SUMMARY)
    body = page.locator("#detailBody")
    assert body.locator("#aiQuestions .aiq-pick").count() >= 1
    assert "ใส่คำถามที่เลือกลงฟอร์มสัมภาษณ์" not in body.inner_text()
    assert "คัดลอกคำถาม" in body.inner_text()
