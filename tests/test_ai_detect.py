from conftest import candidate

# resume ที่คนเขียนเอง — ภาษาเรียบ ๆ ไม่มีสำนวน AI
HUMAN = """Nattaya Srisuk
Email: nattaya.s@example.com
Tel: 081-234-5678

EXPERIENCE
2021 - Present  Senior Sales Executive, ABC Motors
- Sold trucks to fleet customers in the eastern region, about 30 units per year
- Kept customer records in Salesforce and followed up every month
- Prepared quotations in Microsoft Excel

EDUCATION
B.Eng Industrial Engineering, Chulalongkorn University
TOEIC 850"""

# สรุปประวัติเขียนด้วย AI · ส่วนประสบการณ์/การศึกษาเขียนเอง
AI_SUMMARY = """Warunee Chaiyo
warunee.c@example.com

PROFESSIONAL SUMMARY
Results-driven HR professional with a proven track record of fostering an inclusive workplace.
Passionate about leveraging data-driven insights to streamline recruitment and elevate the employee experience.
Adept at navigating the complexities of labor law while driving innovation in a fast-paced environment.

EXPERIENCE
2023 - Present  Recruitment Officer, DEF Logistics
- Screened applications and booked about 40 interviews per month
- Prepared payroll and social security documents

EDUCATION
B.A. Psychology, Kasetsart University"""


def detect(page, text):
    return page.evaluate("t => detectAIWriting(t)", text)


def section(result, key):
    return next(s for s in result["sections"] if s["key"] == key)


def test_human_resume_scores_low_with_no_flagged_lines(open_ats):
    d = detect(open_ats(), HUMAN)
    assert d["level"] == "low"
    assert d["lines"] == []


def test_ai_summary_is_attributed_to_summary_section_only(open_ats):
    d = detect(open_ats(), AI_SUMMARY)
    assert d["level"] == "high"
    assert section(d, "summary")["level"] == "high"
    # ส่วนที่คนเขียนเองต้องไม่ถูกเหมารวม
    assert section(d, "experience")["level"] == "low"
    assert section(d, "education")["level"] == "low"
    assert {l["section"] for l in d["lines"]} == {"summary"}


def test_flagged_line_lists_the_matching_terms(open_ats):
    d = detect(open_ats(), AI_SUMMARY)
    first = next(l for l in d["lines"] if l["text"].startswith("Results-driven"))
    assert "results-driven" in first["terms"]
    assert "proven track record" in first["terms"]


def test_chatgpt_citation_artifact_flags_that_line(open_ats):
    text = HUMAN.replace(
        "- Prepared quotations in Microsoft Excel",
        "- Prepared quotations in Microsoft Excel :contentReference[oaicite:2]{index=2}")
    d = detect(open_ats(), text)
    assert d["level"] == "high"
    line = d["lines"][0]
    assert line["section"] == "experience"
    assert any("citation" in r["label"] for r in line["reasons"])


def test_unfilled_placeholder_and_chatbot_preamble_are_flagged(open_ats):
    text = HUMAN + "\n\nHere is a polished version of your resume. Feel free to adjust it for [Company Name]."
    d = detect(open_ats(), text)
    labels = {r["label"] for l in d["lines"] for r in l["reasons"]}
    assert "ข้อความค้างจากแชตบอต" in labels
    assert "placeholder ที่ยังไม่ได้แทนค่า" in labels


def test_thai_ai_phrases_are_detected(open_ats):
    text = """สมหญิง ใจดี
somying@example.com

วัตถุประสงค์
ด้วยความมุ่งมั่นที่จะยกระดับงานบุคคลให้ตอบโจทย์องค์กรอย่างยั่งยืน พร้อมรับความท้าทายใหม่และเติบโตไปพร้อมกับองค์กร
มีทักษะที่หลากหลายและพร้อมเรียนรู้สิ่งใหม่ เพื่อขับเคลื่อนองค์กรสู่ความเป็นเลิศ

ประสบการณ์ทำงาน
2565 - ปัจจุบัน เจ้าหน้าที่สรรหา บริษัท เอบีซี จำกัด
- คัดใบสมัครและโทรนัดสัมภาษณ์ เดือนละประมาณ 30 คน"""
    d = detect(open_ats(), text)
    assert section(d, "summary")["level"] == "high"
    assert section(d, "experience")["level"] == "low"


def test_single_buzzword_alone_does_not_raise_level(open_ats):
    text = HUMAN.replace("followed up every month", "followed up every month to foster long-term relationships")
    d = detect(open_ats(), text)
    assert d["level"] == "low"


def test_short_text_is_not_assessed(open_ats):
    d = detect(open_ats(), "Somchai\nsomchai@example.com\nSales 3 years")
    assert d["level"] == "na"
    assert d["score"] is None


def test_new_candidate_stores_compact_summary(open_ats):
    page = open_ats()
    ai = page.evaluate("""t => makeCandidate(parseResume(t),
        {score:0, breakdown:[], matched:[], missing:[], missingRequired:[]}, {}).ai""", AI_SUMMARY)
    assert ai["level"] == "high"
    assert ai["parts"] == ["summary"]
    assert "lines" not in ai          # ไม่เก็บข้อความซ้ำลง localStorage


def test_ai_check_does_not_change_match_score(open_ats):
    page = open_ats()
    scores = page.evaluate("""t => {
        const job = {skills:[{name:'Recruitment',weight:3,required:false}], minExp:1, eduKeywords:''};
        const parsed = parseResume(t);
        const before = scoreCandidate(parsed, job).score;
        const c = makeCandidate(parsed, scoreCandidate(parsed, job), {});
        return [before, c.score, c.ai.level];
    }""", AI_SUMMARY)
    assert scores[0] == scores[1]
    assert scores[2] == "high"


def test_old_record_without_ai_field_is_computed_for_table(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate(resumeText=AI_SUMMARY)]})
    headers = page.locator("#candTable thead th").all_inner_texts()
    col = [h.strip() for h in headers].index("สัญญาณ AI")
    cell = page.locator("#candBody tr td").nth(col)
    assert "สูง" in cell.inner_text()
    assert "สรุปประวัติ" in cell.locator(".badge").get_attribute("title")


def test_outdated_summary_version_is_recomputed(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(resumeText=AI_SUMMARY, ai={"v": 0, "score": 0, "level": "low", "parts": []})]})
    assert page.evaluate("() => aiOf(DB.candidates[0]).level") == "high"


def test_detail_modal_shows_sections_and_highlights(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate(resumeText=AI_SUMMARY)]})
    page.evaluate("() => showCandDetail('cand1')")
    body = page.locator("#detailBody")
    assert "ตรวจจับการใช้ AI" in body.inner_text()
    assert "สรุปประวัติ / Profile" in body.inner_text()
    marks = body.locator("mark.ai").all_inner_texts()
    assert "Results-driven" in marks


def test_highlight_escapes_resume_html(open_ats):
    page = open_ats()
    html = page.evaluate("""() => aiHighlightLine('<img src=x onerror=alert(1)> results-driven', ['results-driven'])""")
    assert "<img" not in html
    assert '<mark class="ai">results-driven</mark>' in html


def test_sort_by_ai_signal(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(id="h", name="คนเขียนเอง", resumeText=HUMAN),
        candidate(id="a", name="ใช้ AI", resumeText=AI_SUMMARY)]})
    page.evaluate("() => { document.getElementById('candSort').value = 'ai'; renderCandidates(); }")
    first = page.locator("#candBody tr").first.inner_text()
    assert "ใช้ AI" in first


def test_csv_includes_ai_columns_before_exam_columns(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(id="a", name="ใช้ AI", resumeText=AI_SUMMARY),
        candidate(id="s", name="สั้น", resumeText="")]})
    rows = page.evaluate("""() => {
        const out = [];
        const orig = window.downloadCSV;
        window.downloadCSV = r => out.push(r);
        return Promise.resolve(exportCSV()).then(() => { window.downloadCSV = orig; return out[0]; });
    }""")
    head = rows[0]
    i = head.index("AI Signal")
    assert head[i + 1] == "AI Level" and head[i + 2] == "AI Sections"
    body = {r[0]: r for r in rows[1:]}
    assert body["ใช้ AI"][i + 1] == "สูง"
    assert "สรุปประวัติ" in body["ใช้ AI"][i + 2]
    assert body["สั้น"][i] == ""                 # ประเมินไม่ได้ → ว่าง ไม่ใช่ 0
    assert body["สั้น"][i + 1] == "ประเมินไม่ได้"


def test_automotive_terms_are_not_mistaken_for_ai_phrases(open_ats):
    page = open_ats()
    lines = [
        "- Assembled wire harness for truck cabins and checked connectors",
        "- ซ่อมระบบขับเคลื่อนและเพลาของรถบรรทุก",
        "- ตรวจสภาพรถก่อนส่งมอบให้ลูกค้า",
    ]
    for line in lines:
        assert page.evaluate("t => aiScanLine(t).reasons", line) == [], line
