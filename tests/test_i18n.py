import re

from conftest import candidate
from test_ai_detect import AI_SUMMARY

THAI = re.compile(r"[฀-๿]")


def open_en(open_ats, db=None):
    """เปิดหน้าในโหมดอังกฤษ — ตั้ง hma_lang แล้ว reload (localStorage อยู่ข้าม reload)"""
    page = open_ats(db)
    page.evaluate("() => localStorage.setItem('hma_lang', 'en')")
    page.reload()
    page.wait_for_function("typeof DB !== 'undefined'")
    return page


def test_default_is_thai_and_button_offers_english(open_ats):
    page = open_ats()
    assert page.locator(".tab[data-tab=candidates]").inner_text() == "👥 ผู้สมัคร"
    assert page.locator("#langLabel").inner_text() == "EN"
    assert page.evaluate("() => document.documentElement.lang") == "th"


def test_toggle_switches_to_english_and_remembers(open_ats):
    page = open_ats()
    page.click("#langBtn")
    assert page.locator(".tab[data-tab=candidates]").inner_text() == "👥 Candidates"
    assert page.locator("#langLabel").inner_text() == "ไทย"
    assert page.evaluate("() => document.documentElement.lang") == "en"
    # คีย์เดียวกับ hma-testing-system → สลับที่ไหนก็จำค่าเดียวกัน
    assert page.evaluate("() => localStorage.getItem('hma_lang')") == "en"
    page.reload()
    page.wait_for_function("typeof DB !== 'undefined'")
    assert page.locator(".tab[data-tab=jobs]").inner_text() == "💼 Jobs"


def test_switching_back_restores_thai_exactly(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate()]})
    before = page.locator("body").inner_text()
    page.click("#langBtn")
    page.click("#langBtn")
    assert page.locator("body").inner_text() == before


def test_attributes_are_translated(open_ats):
    page = open_en(open_ats)
    assert page.locator("#candSearch").get_attribute("placeholder") == "🔍 Search name, email or skill…"
    assert page.locator("#seedBtn").get_attribute("title") == "Load sample data"


def test_app_chrome_has_no_thai_in_english(open_ats):
    page = open_en(open_ats)
    page.evaluate("() => { window.confirm = () => true; seed(); }")
    for tab in ["scanner", "candidates", "jobs", "dashboard"]:
        page.evaluate(f"() => document.querySelector('.tab[data-tab={tab}]').click()")
        text = page.locator(f"#tab-{tab}").inner_text()
        # ข้อมูลตัวอย่างมีชื่อทักษะไทย (Sales/ขาย) ในแท็บตำแหน่งงาน — นั่นคือข้อมูล ไม่ใช่ UI
        lines = [l for l in text.split("\n") if THAI.search(l) and "/" not in l]
        assert lines == [], (tab, lines)
    tabs = page.locator(".tabs").inner_text()
    assert not THAI.search(tabs)


def test_every_translated_view_has_no_missing_keys(open_ats):
    """เดินทุกหน้าจอ/โมดัลในโหมดอังกฤษ — ข้อความใดที่ผ่าน t() แต่ไม่มีคำแปลจะถูกจดใน I18N_MISSING"""
    page = open_en(open_ats)
    page.evaluate("""() => {
        window.confirm = () => true;
        seed();
        ['scanner', 'candidates', 'jobs', 'dashboard'].forEach(t =>
            document.querySelector('.tab[data-tab=' + t + ']').click());
        setCandView('board'); setCandView('table');
        localStorage.setItem('hma_ats_sc_open', '1');
        DB.candidates.forEach(c => { showCandDetail(c.id); openScorecardForm(); showScoreInfo(c.id); });
        openJobModal(DB.jobs[0]);
        openEmailDraft(DB.candidates[0].id);
        openTplManager(); tplShowEditor(null);
        openCriteriaManager();
        renderStuckNote(); renderRetentionNote();
        window.downloadCSV = () => {};
        exportDashboardCSV(); exportJobsCSV();
    }""")
    page.evaluate("() => exportCSV()")
    assert page.evaluate("() => [...I18N_MISSING]") == []


def test_stored_thai_warnings_and_breakdown_display_in_english(open_ats):
    page = open_en(open_ats, {"jobs": [], "candidates": [candidate(
        warnings=["ไม่พบอีเมลใน resume"],
        education="ปริญญาตรี / Bachelor",
        breakdown=[{"label": "ทักษะ (ถ่วงน้ำหนัก)", "detail": "พบ 3/5 ทักษะ (น้ำหนัก 12/15)", "pts": 48, "max": 60}])]})
    page.evaluate("() => showCandDetail('cand1')")
    body = page.locator("#detailBody").inner_text()
    assert "No email found in the resume" in body
    assert "Bachelor's degree" in body
    assert "Skills (weighted)" in body
    assert "Matched 3/5 skills (weight 12/15)" in body
    # ข้อมูลที่เก็บไว้ไม่ถูกแก้
    assert page.evaluate("() => DB.candidates[0].warnings[0]") == "ไม่พบอีเมลใน resume"


def test_ai_section_and_questions_in_english(open_ats):
    page = open_en(open_ats, {"jobs": [], "candidates": [candidate(resumeText=AI_SUMMARY)]})
    page.evaluate("() => showCandDetail('cand1')")
    body = page.locator("#detailBody").inner_text().lower()   # หัวข้อส่วนแสดงเป็นตัวพิมพ์ใหญ่ด้วย CSS
    assert "ai-writing check" in body
    assert "summary / profile" in body
    assert "suggested interview questions" in body
    assert "which achievement are you most proud of" in body
    page.evaluate("() => insertAiQuestions()")
    assert page.locator("#scNote").input_value().startswith("Questions from AI-flagged sections:\n□ ")


def test_experience_question_pattern_keeps_the_quoted_line(open_ats):
    page = open_en(open_ats)
    q = page.evaluate("""() => tStored('ช่วยเล่างานที่เขียนว่า “Spearheaded X” — ช่วงเวลา บทบาทของคุณเอง และผลลัพธ์ที่วัดได้')""")
    assert q == "Tell me about the work you described as “Spearheaded X” — when it was, your own role, and the measurable result"


def test_new_database_in_english_seeds_english_defaults(open_ats):
    page = open_en(open_ats)
    page.evaluate("() => { localStorage.removeItem('hma_ats_v1'); }")
    page.reload()
    page.wait_for_function("typeof DB !== 'undefined'")
    assert page.evaluate("() => DB.scorecardCriteria[0].label") == "Technical knowledge / relevance"
    assert page.evaluate("() => DB.emailTemplates[0].subject") == "Application received: {position} — {company}"


def test_saved_thai_data_is_not_translated(open_ats):
    """ข้อมูลที่ผู้ใช้บันทึกไว้แล้ว (หัวข้อประเมินภาษาไทย) คงเดิมเมื่อสลับภาษา"""
    page = open_ats({"jobs": [], "candidates": []})
    page.click("#langBtn")
    assert page.evaluate("() => DB.scorecardCriteria[0].label") == "ความรู้ทางเทคนิค / ตรงสายงาน"


def test_open_detail_modal_rerenders_on_toggle(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate(resumeText=AI_SUMMARY)]})
    page.evaluate("() => showCandDetail('cand1')")
    assert "ตรวจจับการใช้ AI" in page.locator("#detailBody").inner_text()
    page.evaluate("() => toggleLang()")
    assert "ai-writing check" in page.locator("#detailBody").inner_text().lower()


def test_toggle_keeps_unsaved_interview_form(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate()]})
    page.evaluate("() => { localStorage.setItem('hma_ats_sc_open','1'); showCandDetail('cand1'); openScorecardForm(); }")
    page.locator("#scNote").fill("ยังไม่บันทึก")
    page.evaluate("() => toggleLang()")
    assert page.locator("#scNote").input_value() == "ยังไม่บันทึก"


def test_english_plurals_follow_the_count(open_ats):
    page = open_en(open_ats)
    assert page.evaluate("() => t('{n} วัน', { n: 1 })") == "1 day"
    assert page.evaluate("() => t('{n} วัน', { n: 3 })") == "3 days"
    assert page.evaluate("() => t('คิดจาก {n} รายที่รับเข้าทำงาน', { n: 1 })") == "Based on 1 hire"
    assert page.evaluate("() => t('วัน')") == "days"          # ไม่มีตัวเลข → รูปพหูพจน์
    # ภาษาไทยไม่เปลี่ยน
    page.evaluate("() => { LANG = 'th'; }")
    assert page.evaluate("() => t('{n} วัน', { n: 1 })") == "1 วัน"
