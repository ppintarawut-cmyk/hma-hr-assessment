# Trusted Assessment URL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ทำให้ผู้สมัครกล้ากดลิงก์แบบทดสอบ โดยย้ายหน้าผู้สมัครไป `assessment.hinomotorsasia.com` เพิ่มแผงยืนยันตัวตนที่ตรวจสอบกลับไปหาคนจริงได้ และเลิกเก็บเลขบัตรประชาชนที่ HR ไม่ได้ใช้

**Architecture:** งานโค้ดทั้งหมด (Task 1–7) ทำใน repo ปัจจุบันซึ่งมีชุดทดสอบอยู่แล้ว จากนั้น Task 8 จึงย้ายไฟล์ฝั่งผู้สมัครออกไป repo ใหม่ทีเดียว — จงใจไม่ให้มีช่วงที่ `index.html` ถูกคัดลอกไว้สองที่ เพราะนั่นคือรูปแบบเดียวกับ `hma-testing-system.html` ที่เคยทำให้รหัสผ่านรั่วผ่าน Pages มาแล้ว key ภายในเปลี่ยนจากเลขบัตรเป็นอีเมลตัวพิมพ์เล็ก ซึ่งเป็น identity ที่ ATS ใช้จับคู่ผลสอบอยู่แล้ว

**Tech Stack:** HTML/CSS/JS ไฟล์เดียว ไม่มี build step ไม่มี dependency · Firebase Firestore (compat SDK ผ่าน CDN) · pytest + patchright (Playwright) สำหรับทดสอบ · GitHub Pages

## Global Constraints

- ไฟล์เดียว ไม่มี build step ไม่มี dependency ใหม่ — ห้ามเพิ่ม npm/bundler
- `hma-ats.html` ห้ามแตะแม้แต่บรรทัดเดียวในแผนนี้
- ATS ต้องทำงานเหมือนเดิมทุกอย่าง: URL เดิม localStorage เดิม ไม่ต้อง migrate
- ลิงก์เก่า `https://ppintarawut-cmyk.github.io/hma-hr-assessment/` ต้องยังพาผู้สมัครไปถึงข้อสอบได้
- ข้อความทุกจุดต้องแก้ทั้ง `th` และ `en` ในตาราง i18n
- ชื่อ field ใหม่ในทั้งสอง collection คือ `candidate_key` เหมือนกัน (`exam_records` เดิมใช้ `national_id`, `result_snapshots` เดิมใช้ `nid`)
- key คืออีเมล **ตัวพิมพ์เล็กเสมอ** — `(email || '').toLowerCase()`
- ห้ามสร้าง GitHub org หรือชื่อใด ๆ ที่ขึ้นต้นด้วย `hino-` (ระบบยังไม่ได้รับอนุมัติเป็นทางการ)
- domain เป้าหมาย: `assessment.hinomotorsasia.com`
- ห้าม cutover domain จนกว่า `HR_CONTACT` จะเป็นข้อมูลจริงครบทั้งสามค่า

---

### Task 1: Test fixture สำหรับหน้าระบบสอบ

ชุดทดสอบที่มีอยู่เปิดได้แต่ `hma-ats.html` ทุก task ถัดไปต้องทดสอบ `index.html` จึงต้องมี fixture ก่อน

**Files:**
- Modify: `tests/conftest.py` (เพิ่มท้ายไฟล์)
- Test: `tests/test_pdpa_key.py` (สร้างใหม่)

**Interfaces:**
- Produces: fixture `open_exam(exam_records=None, result_snapshots=None) -> Page` และ helper `exam_record(**over) -> dict` — Task 2–6 ใช้ทั้งคู่

- [ ] **Step 1: เพิ่ม fixture ท้าย `tests/conftest.py`**

```python
@pytest.fixture
def open_exam(browser, server):
    """เปิด index.html (ระบบสอบ) โดย seed localStorage ก่อนสคริปต์ของหน้าจะรัน"""
    contexts = []

    def _open(exam_records=None, result_snapshots=None):
        ctx = browser.new_context()
        contexts.append(ctx)
        for key, value in (("hma_exam_records", exam_records),
                           ("hma_result_snapshots", result_snapshots)):
            if value is None:
                continue
            payload = json.dumps(json.dumps(value))
            # เงื่อนไข if เหมือน open_ats — add_init_script ยิงซ้ำทุก navigation
            # ถ้า setItem ตรง ๆ การ reload จะล้างสิ่งที่หน้าเว็บเพิ่งเขียนไป
            ctx.add_init_script(
                f"if (!localStorage.getItem('{key}')) localStorage.setItem('{key}', {payload})")
        page = ctx.new_page()
        # เหตุผลเดียวกับ open_ats: patchright ใช้ isolated world เป็นค่าเริ่มต้น
        # ซึ่งมองไม่เห็น function ที่ประกาศไว้ใน <script> ของหน้า
        _orig_evaluate = page.evaluate
        page.evaluate = lambda expr, arg=None: _orig_evaluate(expr, arg, isolated_context=False)
        page.goto(f"{server}/index.html")
        page.wait_for_function("typeof submitReg !== 'undefined'")
        return page

    yield _open
    for ctx in contexts:
        ctx.close()


def exam_record(**over):
    """record ผลสอบขั้นต่ำที่ผ่าน guard ของ renderer ทุกตัว (รูปแบบใหม่)"""
    base = {
        "datetime": "3/8/2569 10:00:00", "_ts": 1785000000000,
        "candidate_key": "somchai@example.com",
        "name": "สมชาย ทดสอบ", "email": "somchai@example.com",
        "phone": "0812345678", "age": 28, "experience": 3,
        "position": "ช่างเทคนิค", "attempt": 1, "attempt_label": "ครั้งที่ 1",
        "_complete": True,
    }
    base.update(over)
    return base


def legacy_exam_record(**over):
    """record รูปแบบเก่าที่ยังใช้เลขบัตรเป็น key — ใช้ทดสอบ read-compat"""
    base = exam_record()
    base.pop("candidate_key")
    base["national_id"] = "1234567890123"
    base.update(over)
    return base
```

- [ ] **Step 2: สร้าง `tests/test_pdpa_key.py` ด้วยเทสต์พิสูจน์ว่า fixture ใช้ได้**

```python
from conftest import exam_record


def test_exam_page_opens_on_landing(open_exam):
    page = open_exam()
    assert page.locator("#p-landing").is_visible()


def test_seeded_records_reach_the_page(open_exam):
    page = open_exam(exam_records=[exam_record()])
    count = page.evaluate(
        "() => JSON.parse(localStorage.getItem('hma_exam_records') || '[]').length")
    assert count == 1
```

- [ ] **Step 3: รันเทสต์**

Run: `python -m pytest tests/test_pdpa_key.py -v`
Expected: PASS ทั้ง 2 ตัว

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_pdpa_key.py
git commit -m "Add test fixture for the candidate exam page"
```

---

### Task 2: เปลี่ยน key ภายในเป็นอีเมลตัวพิมพ์เล็ก

**Files:**
- Modify: `index.html` (~20 จุด — ดู Step 3)
- Test: `tests/test_pdpa_key.py`

**Interfaces:**
- Consumes: `open_exam`, `exam_record`, `legacy_exam_record` จาก Task 1
- Produces: `candKey(r) -> string` — Task 3–6 ใช้ · field `candidate_key` ใน `hma_exam_records` และ `hma_result_snapshots`

- [ ] **Step 1: เขียนเทสต์ที่ต้องแดง — เพิ่มท้าย `tests/test_pdpa_key.py`**

```python
from conftest import exam_record, legacy_exam_record


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
```

- [ ] **Step 2: รันเทสต์เพื่อยืนยันว่าแดง**

Run: `python -m pytest tests/test_pdpa_key.py -v -k cand_key`
Expected: FAIL — `ReferenceError: candKey is not defined`

- [ ] **Step 3: เพิ่ม helper แล้วแทนที่ทุกจุดที่อ่าน identity**

เพิ่ม `candKey` ไว้เหนือ `getCandidateProfiles` (บรรทัดใกล้ `index.html:2510`):

```js
// ── Candidate identity ──────────────────────────────────────────────
// key คืออีเมลตัวพิมพ์เล็ก ซึ่งเป็น identity เดียวกับที่ ATS ใช้จับคู่ผลสอบ
// (hma-ats.html:1135) record ที่บันทึกก่อน 2026-08 ใช้เลขบัตรเป็น key
// (exam_records.national_id / result_snapshots.nid) จึง fallback ให้แถวเก่า
// ยังแสดงผลได้หลังเปลี่ยน — ห้ามลบ fallback จนกว่า migration บน Firestore จะจบ
function candKey(r){
  return (r && (r.candidate_key || (r.email || '').toLowerCase()
                || r.national_id || r.nid)) || '';
}
```

แทนที่ทุกจุดตามรูปแบบด้านล่าง หาจุดทั้งหมดด้วย:

```bash
grep -n -E "national_id|\bnid\b|byNid|nidSet" index.html
```

รูปแบบที่ 1 — **จุดที่เขียน record** (`buildExamRecord`, `index.html:3505`):

```js
// เดิม
    national_id:  applicant.nid,
// ใหม่
    candidate_key: (applicant.email || '').toLowerCase(),
```

รูปแบบที่ 2 — **จุดที่จับคู่ record เดิม** (`saveExamData`, `index.html:3543` และ `:3546`):

```js
// เดิม
    const prevFull = existing.filter(r =>
      r.national_id === rec.national_id && r._complete
    );
    const pendingIdx = existing.findIndex(r =>
      r.national_id === rec.national_id && !r._complete
    );
// ใหม่
    const recKey = candKey(rec);
    const prevFull = existing.filter(r => candKey(r) === recKey && r._complete);
    const pendingIdx = existing.findIndex(r => candKey(r) === recKey && !r._complete);
```

รูปแบบที่ 3 — **จุดที่จัดกลุ่ม** (`index.html:2416`, `:2519`, `:2672`) เปลี่ยนตัวแปรกลุ่มให้อ่านผ่าน `candKey`:

```js
// เดิม (index.html:2519)
      const nid = rec.national_id;
// ใหม่
      const nid = candKey(rec);
```

```js
// เดิม (index.html:2672-2673)
    const nid = rec.national_id || '—';
    if (!byNid[nid]) byNid[nid] = { national_id:nid, attempts:0, _ts:0, datetime:'' };
// ใหม่
    const nid = candKey(rec) || '—';
    if (!byNid[nid]) byNid[nid] = { candidate_key:nid, attempts:0, _ts:0, datetime:'' };
```

รูปแบบที่ 4 — **live profile** (`index.html:2559`, `:2581`):

```js
// เดิม
      national_id: applicant.nid,
// ใหม่
      candidate_key: (applicant.email || '').toLowerCase(),
```

```js
// เดิม
    const existIdx = all.findIndex(p => p.national_id === liveProfile.national_id);
// ใหม่
    const existIdx = all.findIndex(p => candKey(p) === candKey(liveProfile));
```

รูปแบบที่ 5 — **จุดที่ลบ** (`index.html:2834-2837`, `:3580`, `:3584`, `:3588`, `:3591`, `:3598`):

```js
// เดิม (index.html:2834-2835)
  try { const s = JSON.parse(localStorage.getItem('hma_exam_records')||'[]');   localStorage.setItem('hma_exam_records',   JSON.stringify(s.filter(r => !nidSet.has(r.national_id)))); } catch(e){}
  try { const s = JSON.parse(localStorage.getItem('hma_result_snapshots')||'[]'); localStorage.setItem('hma_result_snapshots', JSON.stringify(s.filter(x => !nidSet.has(x.nid)))); } catch(e){}
// ใหม่
  try { const s = JSON.parse(localStorage.getItem('hma_exam_records')||'[]');   localStorage.setItem('hma_exam_records',   JSON.stringify(s.filter(r => !nidSet.has(candKey(r))))); } catch(e){}
  try { const s = JSON.parse(localStorage.getItem('hma_result_snapshots')||'[]'); localStorage.setItem('hma_result_snapshots', JSON.stringify(s.filter(x => !nidSet.has(candKey(x))))); } catch(e){}
```

```js
// เดิม (index.html:2837)
  if (applicant && nidSet.has(applicant.nid)){ applicant = null; sessions = []; curSess = null; clearPersistedSession(); }
// ใหม่
  if (applicant && nidSet.has((applicant.email||'').toLowerCase())){ applicant = null; sessions = []; curSess = null; clearPersistedSession(); }
```

`deleteApplicantData(encodedKey)` (`index.html:3569`) รับ object ที่ถูกสร้างไว้ที่ `index.html:2622`
ต้องแก้ **ทั้งคู่พร้อมกัน** ไม่งั้นปุ่มลบจะเงียบและลบอะไรไม่ได้เลย

ฝั่งสร้าง (`index.html:2622`):

```js
// เดิม
      const rowKey = JSON.stringify({ fn:(p.name||'').split(' ')[0], ln:(p.name||'').split(' ').slice(1).join(' '), nid:p.national_id });
// ใหม่
      const rowKey = JSON.stringify({ fn:(p.name||'').split(' ')[0], ln:(p.name||'').split(' ').slice(1).join(' '), candKey:candKey(p) });
```

ฝั่งใช้ (`index.html:3575`, `:3580`, `:3584`, `:3588`, `:3591`, `:3598`):

```js
// เดิม
  if (!confirm(`⚠️ ลบข้อมูลทั้งหมดของ "${name}" (${key.nid})?\n\nการกระทำนี้ไม่สามารถย้อนกลับได้`)) return;
    localStorage.setItem('hma_exam_records', JSON.stringify(stored.filter(r => r.national_id !== key.nid)));
    localStorage.setItem('hma_result_snapshots', JSON.stringify(snaps.filter(s => s.nid !== key.nid)));
  cloudDeleteCandidate(key.nid);
  if (applicant && applicant.nid === key.nid) {
  candSelected.delete(key.nid);
// ใหม่
  if (!confirm(`⚠️ ลบข้อมูลทั้งหมดของ "${name}" (${key.candKey})?\n\nการกระทำนี้ไม่สามารถย้อนกลับได้`)) return;
    localStorage.setItem('hma_exam_records', JSON.stringify(stored.filter(r => candKey(r) !== key.candKey)));
    localStorage.setItem('hma_result_snapshots', JSON.stringify(snaps.filter(s => candKey(s) !== key.candKey)));
  cloudDeleteCandidate(key.candKey);
  if (applicant && (applicant.email||'').toLowerCase() === key.candKey) {
  candSelected.delete(key.candKey);
```

รูปแบบที่ 6 — **merge key ของ cloud sync** (`index.html:5507-5508`):

```js
// เดิม
function _recKey(r){ return (r.national_id||'') + '|' + (r.attempt||1) + '|' + (r.datetime||''); }
function _snapKey(s){ return (s.nid||'') + '|' + (s.datetime||''); }
// ใหม่
function _recKey(r){ return candKey(r) + '|' + (r.attempt||1) + '|' + (r.datetime||''); }
function _snapKey(s){ return candKey(s) + '|' + (s.datetime||''); }
```

รูปแบบที่ 7 — **cloud push** (`index.html:5524-5540`):

```js
// เดิม
  const nid = applicant && applicant.nid;
  if (!nid) return;
  ...
    const recs  = JSON.parse(localStorage.getItem('hma_exam_records')   || '[]').filter(r => r.national_id === nid);
    const snaps = JSON.parse(localStorage.getItem('hma_result_snapshots')|| '[]').filter(s => s.nid === nid);
// ใหม่ (แก้ทั้งใน try และใน catch — มีสองชุดเหมือนกัน)
  const nid = applicant && (applicant.email || '').toLowerCase();
  if (!nid) return;
  ...
    const recs  = JSON.parse(localStorage.getItem('hma_exam_records')   || '[]').filter(r => candKey(r) === nid);
    const snaps = JSON.parse(localStorage.getItem('hma_result_snapshots')|| '[]').filter(s => candKey(s) === nid);
```

รูปแบบที่ 8 — **snapshot write** (`index.html:5448`) และทุกที่ที่เขียน `nid:` ลง object ให้เปลี่ยนชื่อ field เป็น `candidate_key` แล้วเทียบด้วย `candKey`:

```js
// เดิม
    const i = all.findIndex(x => x.nid === snap.nid && !x._sealed);
// ใหม่
    const i = all.findIndex(x => candKey(x) === candKey(snap) && !x._sealed);
```

รูปแบบที่ 9 — **ช่องค้นหาในตารางผู้สมัคร** (`index.html:2703`) เดิมค้นเลขบัตรแต่ค้นอีเมลไม่ได้:

```js
// เดิม
  if (q) list = list.filter(p => `${p.name||''} ${p.position||''} ${p.national_id||''}`.toLowerCase().includes(q));
// ใหม่
  if (q) list = list.filter(p => `${p.name||''} ${p.position||''} ${p.email||''}`.toLowerCase().includes(q));
```

รูปแบบที่ 10 — **จุดที่อ่าน identity จาก profile object** (`p` ที่ผ่าน `getCandidateProfiles`
หรือ `getCandidateView` มาแล้ว) ทั้งหมดต้องเปลี่ยนเป็น `candKey(p)`
อยู่ที่ `index.html:2429`, `:2431`, `:2604`, `:2654`, `:2741`, `:2773`, `:2816`, `:2848`,
`:3018`, `:3636`:

```js
// เดิม (index.html:2429-2431)
          id:       `stored_${rec.national_id}_${code}_${rec.attempt||1}`,
          nid:      rec.national_id,
// ใหม่
          id:       `stored_${candKey(rec)}_${code}_${rec.attempt||1}`,
          candidate_key: candKey(rec),
```

```js
// เดิม (index.html:2604) — ใช้ตัวอักษรแรกเลือกสีอวาตาร์ ใช้อีเมลแทนได้เลย
    const ci    = ((p.name||'').charCodeAt(0) + (p.national_id||'').charCodeAt(0)) % 5;
// ใหม่
    const ci    = ((p.name||'').charCodeAt(0) + (candKey(p)||' ').charCodeAt(0)) % 5;
```

```js
// เดิม (index.html:2773, :2816, :2848) — ชุดเลือกผู้สมัคร
  if (selAll){ const nids = pageRows.map(p=>p.national_id); ... }
  ...forEach(p => cb.checked ? candSelected.add(p.national_id) : candSelected.delete(p.national_id));
  const list = getCandidateList().filter(p => candSelected.has(p.national_id));
// ใหม่
  if (selAll){ const nids = pageRows.map(p=>candKey(p)); ... }
  ...forEach(p => cb.checked ? candSelected.add(candKey(p)) : candSelected.delete(candKey(p)));
  const list = getCandidateList().filter(p => candSelected.has(candKey(p)));
```

- [ ] **Step 4: รันเทสต์ทั้งชุด**

Run: `python -m pytest tests/ -v`
Expected: PASS ทั้งหมด รวมเทสต์ ATS เดิมที่ต้องไม่กระทบ

- [ ] **Step 5: ยืนยันว่าไม่เหลือ `national_id` ในเส้นทางเขียนข้อมูล**

Run: `grep -n "national_id\|\bnid\b" index.html`
Expected: เหลือเฉพาะใน `candKey()` (fallback) เท่านั้น — ถ้าเจอที่อื่นแปลว่าตกจุด ให้กลับไป Step 3

- [ ] **Step 6: Commit**

```bash
git add index.html tests/test_pdpa_key.py
git commit -m "Key candidate records on the lowercased email instead of the national ID"
```

---

### Task 3: ขั้นยืนยันอีเมลก่อนเริ่มสอบ

อีเมลกลายเป็น key แล้ว การพิมพ์ผิดจะทำให้ผลสอบจับคู่กับใบสมัครใน ATS ไม่ได้ และไม่มีใครรู้ตัว

**Files:**
- Modify: `index.html` (`submitReg`, `index.html:1743`)
- Test: `tests/test_pdpa_key.py`

**Interfaces:**
- Consumes: `candKey` จาก Task 2
- Produces: element `#confirm-email-box`, `#confirm-email-value`, `#confirm-email-yes`, `#confirm-email-edit`

- [ ] **Step 1: เขียนเทสต์ที่ต้องแดง — เพิ่มท้าย `tests/test_pdpa_key.py`**

```python
def _fill_registration(page, email="Somchai@Example.com"):
    page.evaluate("() => nav('p-register')")
    page.fill("#r-nid", "1234567890123")
    page.fill("#r-fn", "สมชาย")
    page.fill("#r-ln", "ทดสอบ")
    page.fill("#r-age", "28")
    page.select_option("#reg-pos", index=1)
    page.fill("#r-email", email)
    page.check("#pdpa-consent")


def test_submitting_registration_asks_to_confirm_the_email(open_exam):
    page = open_exam()
    _fill_registration(page)
    page.click("#reg-btn")
    page.wait_for_selector("#confirm-email-box", state="visible")
    assert page.inner_text("#confirm-email-value").strip() == "Somchai@Example.com"


def test_confirming_the_email_starts_the_exam(open_exam):
    page = open_exam()
    _fill_registration(page)
    page.click("#reg-btn")
    page.click("#confirm-email-yes")
    page.wait_for_selector("#p-dash.active")
    assert page.evaluate("() => candKey({email: applicant.email})") == "somchai@example.com"


def test_editing_from_the_confirm_box_returns_to_the_form(open_exam):
    page = open_exam()
    _fill_registration(page)
    page.click("#reg-btn")
    page.click("#confirm-email-edit")
    page.wait_for_selector("#confirm-email-box", state="hidden")
    page.fill("#r-email", "other@example.com")
    page.click("#reg-btn")
    page.click("#confirm-email-yes")
    page.wait_for_selector("#p-dash.active")
    assert page.evaluate("() => applicant.email") == "other@example.com"
```

- [ ] **Step 2: รันเทสต์เพื่อยืนยันว่าแดง**

Run: `python -m pytest tests/test_pdpa_key.py -v -k confirm`
Expected: FAIL — timeout รอ `#confirm-email-box`

- [ ] **Step 3: เพิ่มกล่องยืนยันใน markup ของ `#p-register` ใต้ปุ่มลงทะเบียน**

```html
<div id="confirm-email-box" style="display:none;margin-top:14px;background:var(--gray-50);border:1.5px solid var(--teal);border-radius:var(--radius);padding:16px">
  <div data-i18n="confirm_email_lead" style="font-size:13px;color:var(--gray-700);margin-bottom:8px">
    ผลการทดสอบจะถูกส่งไปที่อีเมลนี้ กรุณาตรวจสอบให้ถูกต้อง
  </div>
  <div id="confirm-email-value" style="font-size:18px;font-weight:700;color:var(--gray-900);word-break:break-all;margin-bottom:14px"></div>
  <div style="display:flex;gap:10px;flex-wrap:wrap">
    <button id="confirm-email-yes" class="btn" data-i18n="confirm_email_yes" onclick="confirmEmailAndStart()">ถูกต้อง เริ่มทดสอบ →</button>
    <button id="confirm-email-edit" class="btn btn-secondary" data-i18n="confirm_email_edit" onclick="cancelEmailConfirm()">แก้ไขอีเมล</button>
  </div>
</div>
```

- [ ] **Step 4: แยก `submitReg` ออกเป็นสองขั้น**

เปลี่ยนท้าย `submitReg` (`index.html:1775-1791`) จากที่ `setTimeout` แล้วสร้าง `applicant` ทันที เป็นเก็บค่าไว้แล้วโชว์กล่องยืนยัน:

```js
let pendingReg = null;   // ค่าจากฟอร์มที่รอผู้สมัครยืนยันอีเมล

// ── แทนที่บล็อก setTimeout เดิมทั้งก้อน ──
  pendingReg = {
    name: `${fn} ${ln}`,
    pos, postype: posId, email, phone,
    age: Number(document.getElementById('r-age').value) || 0,
    exp: Number(document.getElementById('r-exp')?.value) || 0,
    preset,
  };
  document.getElementById('confirm-email-value').textContent = email;
  document.getElementById('confirm-email-box').style.display = 'block';
  document.getElementById('confirm-email-box').scrollIntoView({behavior:'smooth', block:'nearest'});
}

function cancelEmailConfirm(){
  pendingReg = null;
  document.getElementById('confirm-email-box').style.display = 'none';
  document.getElementById('r-email').focus();
}

function confirmEmailAndStart(){
  if (!pendingReg) return;
  const btn = document.getElementById('confirm-email-yes');
  btn.innerHTML = '<span class="spin"></span> กำลังลงทะเบียน...';
  btn.disabled = true;

  const preset = pendingReg.preset;
  applicant = {
    name: pendingReg.name, pos: pendingReg.pos, postype: pendingReg.postype,
    email: pendingReg.email, phone: pendingReg.phone,
    age: pendingReg.age, exp: pendingReg.exp,
  };
  const codes  = preset ? preset.tests : TESTS.map(t => t.code);
  const chosen = TESTS.filter(t => codes.includes(t.code));
  sessions = (chosen.length ? chosen : TESTS).map(t => {
    const n = (ALL_QUESTIONS[t.code]||[]).length || 10;
    return { test:t, status:'not_started', score:null, outcome:null, answers:new Array(n).fill(null) };
  });
  pendingReg = null;
  document.getElementById('confirm-email-box').style.display = 'none';
  btn.innerHTML = 'ถูกต้อง เริ่มทดสอบ →';
  btn.disabled = false;
  nav('p-dash');
}
```

- [ ] **Step 5: เพิ่มข้อความ i18n สามรายการ ถัดจาก `reg_btn` (`index.html:1392`)**

```js
  confirm_email_lead: { th:'ผลการทดสอบจะถูกส่งไปที่อีเมลนี้ กรุณาตรวจสอบให้ถูกต้อง', en:'Your results will be sent to this address. Please check that it is correct.' },
  confirm_email_yes:  { th:'ถูกต้อง เริ่มทดสอบ →', en:'Correct — start the test →' },
  confirm_email_edit: { th:'แก้ไขอีเมล',           en:'Edit email' },
```

- [ ] **Step 6: รันเทสต์**

Run: `python -m pytest tests/ -v`
Expected: PASS ทั้งหมด

- [ ] **Step 7: Commit**

```bash
git add index.html tests/test_pdpa_key.py
git commit -m "Ask candidates to confirm their email before the exam starts"
```

---

### Task 4: เลิกเก็บเลขบัตรประชาชน และแก้ consent ให้ตรงกับข้อมูลที่เก็บจริง

รวมเป็น task เดียวโดยตั้งใจ — ถ้าแยก จะมีช่วงที่ข้อความ consent ไม่ตรงกับข้อมูลที่ระบบเก็บจริง

**Files:**
- Modify: `index.html` (form `:705`, validation `:1732` `:1755`, i18n `:1390-1391`, ตาราง `:2630`)
- Create: `privacy.html`
- Test: `tests/test_pdpa_key.py`

**Interfaces:**
- Consumes: `_fill_registration` จาก Task 3 (ต้องแก้ให้เลิกกรอก `#r-nid`)

- [ ] **Step 1: เขียนเทสต์ที่ต้องแดง — เพิ่มท้าย `tests/test_pdpa_key.py`**

```python
COLLECTED_TH = ["ชื่อ-นามสกุล", "อีเมล", "เบอร์โทรศัพท์", "อายุ",
                "ประสบการณ์", "ตำแหน่งที่สมัคร", "ผลการทดสอบ"]


def test_registration_form_has_no_national_id_field(open_exam):
    page = open_exam()
    page.evaluate("() => nav('p-register')")
    assert page.locator("#r-nid").count() == 0


def test_consent_text_no_longer_mentions_the_national_id(open_exam):
    page = open_exam()
    for lang in ("th", "en"):
        text = page.evaluate(f"() => I18N.pdpa_consent.{lang}")
        assert "เลขประจำตัวประชาชน" not in text
        assert "national ID" not in text


COLLECTED_EN = ["full name", "email", "phone number", "age",
                "work experience", "position", "test results"]


def test_consent_text_lists_every_field_the_form_collects(open_exam):
    page = open_exam()
    text = page.evaluate("() => I18N.pdpa_consent.th")
    for field in COLLECTED_TH:
        assert field in text, f"consent ไม่ได้ประกาศว่าเก็บ {field}"


def test_english_consent_text_lists_the_same_fields(open_exam):
    page = open_exam()
    text = page.evaluate("() => I18N.pdpa_consent.en").lower()
    for field in COLLECTED_EN:
        assert field in text, f"English consent is missing {field}"


def test_pdpa_notice_links_to_the_privacy_page(open_exam):
    page = open_exam()
    page.evaluate("() => nav('p-register')")
    href = page.get_attribute("#p-register a[href='privacy.html']", "href")
    assert href == "privacy.html"


def test_privacy_page_loads_and_lists_the_collected_fields(open_exam, server):
    page = open_exam()
    page.goto(f"{server}/privacy.html")
    body = page.inner_text("body")
    for field in COLLECTED_TH:
        assert field in body


def test_candidate_table_shows_the_email_not_a_national_id(open_exam):
    page = open_exam(exam_records=[exam_record()])
    page.evaluate("() => { renderCandidates(); }")
    assert "somchai@example.com" in page.inner_text("#a-cand-tbody")
    assert "1234567890123" not in page.inner_text("#a-cand-tbody")
```

- [ ] **Step 2: รันเทสต์เพื่อยืนยันว่าแดง**

Run: `python -m pytest tests/test_pdpa_key.py -v -k "national_id or consent or privacy"`
Expected: FAIL ทุกตัว

- [ ] **Step 3: ลบ field เลขบัตรออกจากฟอร์ม (`index.html:704-708`)**

```html
<!-- ลบทั้งบล็อกนี้ -->
      <div class="field">
        <label><span data-i18n="f_nid">เลขบัตรประจำตัวประชาชน</span> <span style="color:var(--red)">*</span></label>
        <input id="r-nid" type="text" maxlength="13" placeholder="1234567890123">
        <div class="err-msg" id="e-nid" style="display:none"></div>
      </div>
```

- [ ] **Step 4: ลบ validation และ reference ที่ค้าง**

```js
// index.html:1732 — เอา 'e-nid' ออก
  ['e-fn','e-ln','e-age','e-pos','e-email','e-pdpa'].forEach(id => {
// index.html:1736 — เอา 'r-nid' ออก
  ['r-fn','r-ln','r-age','reg-pos','r-email'].forEach(id => {
// index.html:1744 — ลบบรรทัดนี้ทั้งบรรทัด
  const nid   = document.getElementById('r-nid').value.trim();
// index.html:1755 — ลบบรรทัดนี้ทั้งบรรทัด
  if (!/^\d{13}$/.test(nid)) { showErr('e-nid','เลขบัตรต้องเป็นตัวเลข 13 หลัก'); ok=false; }
```

ลบ i18n key `f_nid` ด้วย และค้นให้แน่ใจว่าไม่เหลือ reference: `grep -n "r-nid\|e-nid\|f_nid" index.html` ต้องไม่คืนอะไรเลย

- [ ] **Step 5: แก้ i18n สองรายการ (`index.html:1390-1391`)**

```js
  pdpa_info:     { th:'ข้อมูลของท่านเก็บรักษาตาม <a href="privacy.html" target="_blank" style="color:var(--teal);text-decoration:underline">นโยบายความเป็นส่วนตัว</a> และใช้เพื่อประกอบการพิจารณาสมัครงานเท่านั้น', en:'Your data is handled under our <a href="privacy.html" target="_blank" style="color:var(--teal);text-decoration:underline">privacy notice</a> and used solely for recruitment consideration.' },
  pdpa_consent:  { th:'ข้าพเจ้ายินยอมให้ HMA (Hino Motors Asia) เก็บรวบรวมและใช้ข้อมูลส่วนบุคคล ได้แก่ ชื่อ-นามสกุล อีเมล เบอร์โทรศัพท์ อายุ ประสบการณ์ทำงาน ตำแหน่งที่สมัคร และผลการทดสอบ เพื่อวัตถุประสงค์ในการคัดเลือกบุคลากร ตามพระราชบัญญัติคุ้มครองข้อมูลส่วนบุคคล (PDPA) พ.ศ. 2562 โดยเก็บไว้ไม่เกิน 2 ปี', en:'I consent to HMA (Hino Motors Asia) collecting and using my personal data — full name, email, phone number, age, work experience, position applied for and test results — for recruitment purposes, in accordance with the Personal Data Protection Act (PDPA) B.E. 2562, retained for no longer than 2 years.' },
```

`pdpa_info` ใช้ `data-i18n` อยู่ (`index.html:748`) ซึ่ง set `textContent` — ต้องเปลี่ยนเป็น `data-i18n-html` เพื่อให้ลิงก์ทำงาน:

```html
<span data-i18n-html="pdpa_info">
```

แก้ข้อความ inline ใน markup (`index.html:748` และ `:755-758`) ให้ตรงกับ i18n ด้วย เพราะเป็นค่าเริ่มต้นก่อน i18n จะทำงาน

- [ ] **Step 6: เปลี่ยนคอลัมน์ใต้ชื่อในตารางผู้สมัคร (`index.html:2630`)**

```js
// เดิม
            <div style="font-size:11px;color:var(--gray-400)">${esc(p.national_id || '—')}</div>
// ใหม่
            <div style="font-size:11px;color:var(--gray-400)">${esc(p.email || '—')}</div>
```

- [ ] **Step 7: สร้าง `privacy.html`**

```html
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>นโยบายความเป็นส่วนตัว — HMA Testing System</title>
<style>
  :root{--teal:#0f9b78;--gray-900:#1a1d1f;--gray-700:#41474d;--gray-400:#8a9199;--gray-200:#e4e7eb;--gray-50:#f7f8f9;}
  *{box-sizing:border-box}
  body{margin:0;font-family:'Noto Sans Thai',system-ui,-apple-system,sans-serif;color:var(--gray-900);line-height:1.75;background:#fff}
  .wrap{max-width:720px;margin:0 auto;padding:32px 20px 64px}
  h1{font-size:24px;margin:0 0 4px}
  h2{font-size:16px;margin:32px 0 8px;color:var(--teal)}
  .updated{color:var(--gray-400);font-size:13px;margin-bottom:28px}
  ul{padding-left:20px}
  li{margin-bottom:4px}
  .box{background:var(--gray-50);border:1px solid var(--gray-200);border-radius:10px;padding:16px 18px;margin-top:8px}
  a{color:var(--teal)}
  .back{display:inline-block;margin-bottom:20px;font-size:13px}
</style>
</head>
<body>
<div class="wrap">
  <a class="back" href="index.html">← กลับหน้าแบบทดสอบ</a>
  <h1>นโยบายความเป็นส่วนตัว</h1>
  <div class="updated">ระบบแบบทดสอบผู้สมัครงาน — ปรับปรุงล่าสุด 3 สิงหาคม 2569</div>

  <h2>ผู้ควบคุมข้อมูลส่วนบุคคล</h2>
  <p>บริษัท ฮีโน่ มอเตอร์ส เอเซีย จำกัด (Hino Motors Asia Ltd. — HMA) ฝ่ายทรัพยากรบุคคล</p>
  <div class="box" id="hr-contact"></div>

  <h2>ข้อมูลที่เราเก็บ</h2>
  <ul>
    <li>ชื่อ-นามสกุล</li>
    <li>อีเมล</li>
    <li>เบอร์โทรศัพท์</li>
    <li>อายุ</li>
    <li>ประสบการณ์ทำงาน (จำนวนปี)</li>
    <li>ตำแหน่งที่สมัคร</li>
    <li>คำตอบและผลการทดสอบ</li>
  </ul>
  <p>เราไม่เก็บเลขประจำตัวประชาชน สำเนาบัตรประชาชน หรือข้อมูลทางการเงินใด ๆ
     และจะไม่ขอรหัสผ่านจากท่านไม่ว่ากรณีใด</p>

  <h2>วัตถุประสงค์และฐานทางกฎหมาย</h2>
  <p>ใช้เพื่อประกอบการพิจารณาคัดเลือกบุคลากรเท่านั้น โดยอาศัย<strong>ความยินยอม</strong>ของท่าน
     ที่ให้ไว้ก่อนเริ่มทำแบบทดสอบ ตามพระราชบัญญัติคุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562</p>

  <h2>ที่จัดเก็บ</h2>
  <p>ข้อมูลถูกจัดเก็บบน Google Firestore และในเครื่องของผู้ใช้งานระบบ
     เข้าถึงได้เฉพาะเจ้าหน้าที่ฝ่ายทรัพยากรบุคคลที่ได้รับสิทธิ์</p>

  <h2>ระยะเวลาเก็บรักษา</h2>
  <p>ไม่เกิน 2 ปีนับจากวันที่ท่านทำแบบทดสอบ</p>

  <h2>สิทธิของท่าน</h2>
  <ul>
    <li>ขอเข้าถึงและขอสำเนาข้อมูลของท่าน</li>
    <li>ขอแก้ไขข้อมูลที่ไม่ถูกต้อง</li>
    <li>ขอให้ลบข้อมูล</li>
    <li>ถอนความยินยอมเมื่อใดก็ได้</li>
    <li>ร้องเรียนต่อสำนักงานคณะกรรมการคุ้มครองข้อมูลส่วนบุคคล</li>
  </ul>
  <p>ใช้สิทธิได้โดยติดต่อผู้รับผิดชอบตามข้อมูลด้านบน</p>
</div>
<script>
// ต้องตรงกับ HR_CONTACT ใน index.html — ดู Task 5
const HR_CONTACT = {
  name:  'ยังไม่ระบุ — ต้องใส่ก่อน cutover',
  email: 'ยังไม่ระบุ@hinomotorsasia.com',
  phone: 'ยังไม่ระบุ',
};
document.getElementById('hr-contact').innerHTML =
  `<div><strong>ผู้รับผิดชอบ:</strong> ${HR_CONTACT.name}</div>` +
  `<div><strong>อีเมล:</strong> <a href="mailto:${HR_CONTACT.email}">${HR_CONTACT.email}</a></div>` +
  `<div><strong>โทรศัพท์:</strong> ${HR_CONTACT.phone}</div>`;
</script>
</body>
</html>
```

- [ ] **Step 8: แก้ `_fill_registration` ใน `tests/test_pdpa_key.py` ให้เลิกกรอกเลขบัตร**

```python
def _fill_registration(page, email="Somchai@Example.com"):
    page.evaluate("() => nav('p-register')")
    page.fill("#r-fn", "สมชาย")
    page.fill("#r-ln", "ทดสอบ")
    page.fill("#r-age", "28")
    page.select_option("#reg-pos", index=1)
    page.fill("#r-email", email)
    page.check("#pdpa-consent")
```

- [ ] **Step 9: รันเทสต์ทั้งชุด**

Run: `python -m pytest tests/ -v`
Expected: PASS ทั้งหมด

- [ ] **Step 10: Commit**

```bash
git add index.html privacy.html tests/test_pdpa_key.py
git commit -m "Stop collecting the national ID and make the consent text match reality"
```

---

### Task 5: แผงยืนยันตัวตนบนหน้าแรก

**Files:**
- Modify: `index.html` (`#p-landing` markup + i18n)
- Modify: `privacy.html` (ให้ `HR_CONTACT` มาจากแหล่งเดียวกัน)
- Test: `tests/test_pdpa_key.py`

**Interfaces:**
- Produces: `HR_CONTACT` object และ element `#trust-panel`, `#hr-contact-warning`

- [ ] **Step 1: เขียนเทสต์ที่ต้องแดง — เพิ่มท้าย `tests/test_pdpa_key.py`**

```python
def test_trust_panel_is_visible_before_any_form(open_exam):
    page = open_exam()
    assert page.locator("#trust-panel").is_visible()
    panel = page.inner_text("#trust-panel")
    assert "Hino Motors Asia" in panel
    assert "privacy.html" in page.inner_html("#trust-panel")


def test_trust_panel_warns_while_the_hr_contact_is_a_placeholder(open_exam):
    page = open_exam()
    # ค่าเริ่มต้นยังเป็น placeholder — ต้องเตือนให้เห็นชัด ห้าม cutover
    assert page.locator("#hr-contact-warning").is_visible()


def test_warning_disappears_once_real_contact_details_are_set(open_exam):
    page = open_exam()
    page.evaluate("""() => {
        HR_CONTACT.name  = 'ภัทราวุธ ย.';
        HR_CONTACT.email = 'pattarawut_y@hinomotorsasia.com';
        HR_CONTACT.phone = '02-000-0000';
        renderTrustPanel();
    }""")
    assert page.locator("#hr-contact-warning").count() == 0
    assert "pattarawut_y@hinomotorsasia.com" in page.inner_text("#trust-panel")
```

- [ ] **Step 2: รันเทสต์เพื่อยืนยันว่าแดง**

Run: `python -m pytest tests/test_pdpa_key.py -v -k trust`
Expected: FAIL — ไม่พบ `#trust-panel`

- [ ] **Step 3: เพิ่ม markup ใน `#p-landing` ใต้เส้นคั่น (หลัง `index.html:711` ซึ่งเป็น div เส้น gradient)**

```html
    <div id="trust-panel" style="max-width:380px;width:100%;margin-bottom:22px;font-size:12px;line-height:1.75;color:var(--gray-700);background:var(--gray-50);border:1px solid var(--gray-200);border-radius:var(--radius);padding:14px 16px"></div>
```

- [ ] **Step 4: เพิ่ม `HR_CONTACT` และ `renderTrustPanel()` ใน `<script>` ของ `index.html`**

```js
// ── ผู้รับผิดชอบระบบ ────────────────────────────────────────────────
// ค่าเหล่านี้ต้องเป็นข้อมูลจริงทั้งสามค่าก่อน cutover domain
// ตราบใดที่ยังขึ้นต้นด้วย 'ยังไม่ระบุ' หน้าแรกจะขึ้นแถบเตือนสีแดง
// ต้องแก้ให้ตรงกันทั้งที่นี่และใน privacy.html
const HR_CONTACT = {
  name:  'ยังไม่ระบุ — ต้องใส่ก่อน cutover',
  email: 'ยังไม่ระบุ@hinomotorsasia.com',
  phone: 'ยังไม่ระบุ',
};

function hrContactIsPlaceholder(){
  return Object.values(HR_CONTACT).some(v => String(v).startsWith('ยังไม่ระบุ'));
}

function renderTrustPanel(){
  const el = document.getElementById('trust-panel');
  if (!el) return;
  const warn = hrContactIsPlaceholder()
    ? `<div id="hr-contact-warning" style="background:#fcebeb;border:1px solid #e84060;color:#791f1f;border-radius:6px;padding:8px 10px;margin-bottom:10px;font-weight:600">
         ⚠️ ยังไม่ได้ใส่ข้อมูลผู้รับผิดชอบจริง — ห้ามส่งลิงก์นี้ให้ผู้สมัคร
       </div>`
    : '';
  el.innerHTML = warn + `
    <div style="font-weight:700;color:var(--gray-900);margin-bottom:4px">แบบทดสอบนี้เป็นของ Hino Motors Asia Ltd.</div>
    <div>ใช้ประกอบการพิจารณาใบสมัครงานเท่านั้น ข้อมูลของท่านเก็บไว้ไม่เกิน 2 ปี</div>
    <div style="margin-top:8px">
      <div><strong>ผู้รับผิดชอบ:</strong> ${esc(HR_CONTACT.name)}</div>
      <div><strong>อีเมล:</strong> <a href="mailto:${esc(HR_CONTACT.email)}" style="color:var(--teal)">${esc(HR_CONTACT.email)}</a></div>
      <div><strong>โทร:</strong> ${esc(HR_CONTACT.phone)}</div>
    </div>
    <div style="margin-top:8px;color:var(--gray-400)">
      ไม่แน่ใจว่าลิงก์นี้ของจริง? โทรหาเบอร์ข้างต้นเพื่อยืนยันก่อนกรอกข้อมูล —
      เราจะไม่ขอรหัสผ่านหรือข้อมูลทางการเงินจากท่าน
    </div>
    <div style="margin-top:8px"><a href="privacy.html" target="_blank" style="color:var(--teal)">อ่านนโยบายความเป็นส่วนตัว →</a></div>`;
}
renderTrustPanel();
```

เรียก `renderTrustPanel()` ที่ท้ายสคริปต์ ตำแหน่งเดียวกับที่มี `document.querySelector('#p-register .alert-info').style.display='flex';` (`index.html:3120`)

- [ ] **Step 5: ให้ `privacy.html` เตือนแบบเดียวกัน — แก้สคริปต์ท้ายไฟล์**

```js
document.getElementById('hr-contact').innerHTML =
  (Object.values(HR_CONTACT).some(v => String(v).startsWith('ยังไม่ระบุ'))
    ? '<div id="hr-contact-warning" style="background:#fcebeb;border:1px solid #e84060;color:#791f1f;border-radius:6px;padding:8px 10px;margin-bottom:10px;font-weight:600">⚠️ ยังไม่ได้ใส่ข้อมูลผู้รับผิดชอบจริง</div>'
    : '') +
  `<div><strong>ผู้รับผิดชอบ:</strong> ${HR_CONTACT.name}</div>` +
  `<div><strong>อีเมล:</strong> <a href="mailto:${HR_CONTACT.email}">${HR_CONTACT.email}</a></div>` +
  `<div><strong>โทรศัพท์:</strong> ${HR_CONTACT.phone}</div>`;
```

- [ ] **Step 6: รันเทสต์**

Run: `python -m pytest tests/ -v`
Expected: PASS ทั้งหมด

- [ ] **Step 7: Commit**

```bash
git add index.html privacy.html tests/test_pdpa_key.py
git commit -m "Add a verification panel so candidates can check the link is genuine"
```

---

### Task 6: เครื่องมือ migrate ข้อมูลเก่าบน Firestore

**Files:**
- Create: `tools/migrate-candidate-key.html`

**Interfaces:**
- Consumes: field `candidate_key` ที่ Task 2 กำหนด
- Produces: ไม่มี — เป็นเครื่องมือรันครั้งเดียว

เครื่องมือนี้ทำงานได้ต่อเมื่อ login ด้วยบัญชี superadmin (Firestore rules บังคับอยู่แล้ว) และต้องรันแบบ **dry-run ก่อนเสมอ**

- [ ] **Step 1: สร้าง `tools/migrate-candidate-key.html`**

```html
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>Migrate candidate_key — รันครั้งเดียว</title>
<style>
  body{font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;line-height:1.7}
  button{padding:8px 16px;font-size:14px;cursor:pointer;margin-right:8px}
  #log{background:#111;color:#0f0;padding:14px;border-radius:8px;font-family:monospace;
       font-size:12px;white-space:pre-wrap;max-height:420px;overflow:auto;margin-top:16px}
  .warn{background:#fff4e5;border:1px solid #f59e0b;padding:12px;border-radius:8px}
</style>
</head>
<body>
<h1>Migrate <code>candidate_key</code></h1>
<div class="warn">
  <strong>ก่อนกด "ลงมือจริง":</strong> export Firestore สำรองไว้ก่อน — การลบ field กู้คืนไม่ได้<br>
  รัน <strong>ตรวจสอบอย่างเดียว</strong> ก่อนเสมอ ถ้าพบ record ที่ไม่มีอีเมล ให้หยุดและรายงาน
</div>
<p>
  <input id="email" type="email" placeholder="อีเมล superadmin" size="34">
  <input id="pass" type="password" placeholder="รหัสผ่าน">
  <button onclick="login()">เข้าสู่ระบบ</button>
</p>
<p>
  <button onclick="run(true)">ตรวจสอบอย่างเดียว (dry-run)</button>
  <button onclick="run(false)">ลงมือจริง</button>
</p>
<div id="log">รอเข้าสู่ระบบ…</div>

<script src="https://www.gstatic.com/firebasejs/9.23.0/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/9.23.0/firebase-auth-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/9.23.0/firebase-firestore-compat.js"></script>
<script>
const firebaseConfig = {
  apiKey: "AIzaSyBkcnCg_NSBxawmLRdyx4GykDCDcZcu_pw",
  authDomain: "hma-testing-a38f0.firebaseapp.com",
  projectId: "hma-testing-a38f0",
};
firebase.initializeApp(firebaseConfig);
const auth = firebase.auth(), db = firebase.firestore();
const logEl = document.getElementById('log');
const log = m => { logEl.textContent += '\n' + m; logEl.scrollTop = logEl.scrollHeight; };

async function login(){
  try {
    await auth.signInWithEmailAndPassword(
      document.getElementById('email').value.trim(),
      document.getElementById('pass').value);
    log('✅ เข้าสู่ระบบสำเร็จ');
  } catch(e){ log('❌ ' + (e.code || e.message)); }
}

// exam_records ใช้ field national_id, result_snapshots ใช้ nid
const COLLECTIONS = [
  { name: 'exam_records',     legacy: 'national_id' },
  { name: 'result_snapshots', legacy: 'nid' },
];

async function run(dryRun){
  if (!auth.currentUser) { log('❌ ต้องเข้าสู่ระบบก่อน'); return; }
  if (!dryRun && !confirm('ลบ field เลขบัตรถาวร — export สำรองแล้วใช่ไหม?')) return;
  logEl.textContent = dryRun ? '— ตรวจสอบอย่างเดียว —' : '— ลงมือจริง —';

  for (const { name, legacy } of COLLECTIONS) {
    let migrated = 0, already = 0;
    const orphans = [];
    const snap = await db.collection(name).get();
    log(`\n[${name}] ทั้งหมด ${snap.size} record`);

    for (const doc of snap.docs) {
      const d = doc.data();
      if (d.candidate_key) { already++; continue; }
      const key = (d.email || '').toLowerCase();
      if (!key) { orphans.push(doc.id); continue; }
      if (!dryRun) {
        await doc.ref.update({
          candidate_key: key,
          [legacy]: firebase.firestore.FieldValue.delete(),
        });
      }
      migrated++;
    }

    log(`  มี candidate_key อยู่แล้ว : ${already}`);
    log(`  ${dryRun ? 'จะย้าย' : 'ย้ายแล้ว'}            : ${migrated}`);
    log(`  ไม่มีอีเมล (ข้ามไว้)      : ${orphans.length}`);
    if (orphans.length) {
      log(`  ⚠️ หยุดก่อน — record เหล่านี้จะไม่มี key เลยถ้าลบเลขบัตรทิ้ง:`);
      orphans.forEach(id => log(`     - ${id}`));
    }
  }
  log('\nเสร็จสิ้น');
}
</script>
</body>
</html>
```

- [ ] **Step 2: ทดสอบว่าหน้าเปิดได้และไม่มี JS error**

```bash
python -m http.server 8791 &
```

เปิด `http://127.0.0.1:8791/tools/migrate-candidate-key.html` แล้วดู console
Expected: ไม่มี error, ปุ่มกดได้, กด "ตรวจสอบอย่างเดียว" โดยยังไม่ login ต้องขึ้น `❌ ต้องเข้าสู่ระบบก่อน`

- [ ] **Step 3: Commit**

```bash
git add tools/migrate-candidate-key.html
git commit -m "Add a one-off tool to migrate Firestore records onto candidate_key"
```

---

### Task 7: Template อีเมลเชิญสอบ

**Files:**
- Create: `docs/email-invite-template.md`

- [ ] **Step 1: สร้างไฟล์**

````markdown
# Template อีเมลเชิญทำแบบทดสอบ

กติกา — ถ้าข้อไหนทำไม่ได้ ผู้สมัครจะกลับมาสงสัยอีก:

1. ส่งจากอีเมล `@hinomotorsasia.com` เท่านั้น ห้ามส่งจาก Gmail ส่วนตัว
2. เขียน URL เต็มเป็นข้อความ ไม่ใช่ปุ่มหรือลิงก์ย่อ — ผู้สมัครต้องเทียบกับ address bar ได้
3. ชื่อและเบอร์ผู้ส่งต้องตรงกับที่แสดงบนหน้าเว็บ
4. บอกล่วงหน้าว่าเราจะไม่ขออะไรบ้าง

---

**หัวข้อ:** แบบทดสอบประกอบการสมัครงาน ตำแหน่ง [ตำแหน่ง] — Hino Motors Asia

เรียน คุณ[ชื่อผู้สมัคร]

ตามที่ท่านได้สมัครงานตำแหน่ง **[ตำแหน่ง]** กับบริษัท ฮีโน่ มอเตอร์ส เอเซีย จำกัด
ทางฝ่ายทรัพยากรบุคคลขอเชิญท่านทำแบบทดสอบออนไลน์ ใช้เวลาประมาณ [X] นาที

ลิงก์แบบทดสอบ — กรุณาตรวจสอบว่า address bar ตรงกับข้อความนี้ทุกตัวอักษร:

```
https://assessment.hinomotorsasia.com/
```

กรุณาทำให้เสร็จภายในวันที่ **[วันที่]**

**ข้อมูลที่เราจะขอ:** ชื่อ-นามสกุล อีเมล เบอร์โทรศัพท์ อายุ ประสบการณ์ทำงาน และตำแหน่งที่สมัคร
**ข้อมูลที่เราจะไม่ขอเด็ดขาด:** รหัสผ่าน เลขบัตรประชาชน เลขบัญชีธนาคาร หรือข้อมูลบัตรเครดิต

หากได้รับอีเมลที่อ้างชื่อบริษัทแล้วขอข้อมูลเหล่านี้ กรุณาอย่าให้ และแจ้งกลับมาที่เบอร์ด้านล่าง

หากไม่แน่ใจว่าอีเมลหรือลิงก์นี้เป็นของจริง โทรหาผมได้โดยตรงตามเบอร์ด้านล่าง

ขอแสดงความนับถือ
[ชื่อ-นามสกุล]
ฝ่ายทรัพยากรบุคคล บริษัท ฮีโน่ มอเตอร์ส เอเซีย จำกัด
[อีเมล @hinomotorsasia.com] · [เบอร์โทร]
````

- [ ] **Step 2: Commit**

```bash
git add docs/email-invite-template.md
git commit -m "Add an exam invitation email template candidates can verify"
```

---

### Task 8: ย้าย repo, ผูก domain, และตั้ง redirect

Task นี้เป็นงาน ops เกือบทั้งหมด ทำ **หลังจาก Task 1–7 merge เข้า `main` แล้วเท่านั้น**

⚠️ **จังหวะที่ทำ:** ความคืบหน้าของข้อสอบเก็บใน localStorage ซึ่งผูกกับ origin — ผู้สมัครที่
กำลังสอบค้างอยู่ตอนเปลี่ยน domain จะเริ่มใหม่หมด **ทำ Step 9–10 นอกเวลาที่มีคนสอบเท่านั้น**
และเช็คกับ HR ก่อนว่าไม่มีใครค้างอยู่

**Files:**
- Create (repo ใหม่): `index.html`, `privacy.html`, `hino-logo.png`, `.nojekyll`, `CNAME`, `tests/`
- Modify (repo เดิม): `index.html` → หน้า redirect
- Delete (repo เดิม): `hma-testing-system.html`, `hma-personality.html`, `privacy.html`, `index.html` ตัวเดิม

- [ ] **Step 1: ใส่ข้อมูล HR จริงก่อนทุกอย่าง**

แก้ `HR_CONTACT` ทั้งใน `index.html` และ `privacy.html` ให้เป็นชื่อ/อีเมล/เบอร์จริง

Run: `python -m pytest tests/test_pdpa_key.py -v -k trust`
Expected: PASS — และเปิดหน้าแรกด้วยตาต้อง**ไม่เห็นแถบเตือนสีแดง** ถ้ายังเห็น แปลว่ายังใส่ไม่ครบ ห้ามไปต่อ

- [ ] **Step 2: สร้าง repo ใหม่แล้วย้ายไฟล์ พร้อมประวัติ**

```bash
cd ..
git clone hma=testing-system/files assessment
cd assessment
git filter-repo --path index.html --path privacy.html --path hino-logo.png --path .nojekyll --path tests/ --path .gitignore
```

ถ้าไม่มี `git-filter-repo` ให้คัดลอกไฟล์แล้ว `git init` ใหม่แทน — ประวัติไม่ใช่สิ่งจำเป็นสำหรับ repo นี้

- [ ] **Step 3: ลบเทสต์ของ ATS ออกจาก repo ใหม่ และเทสต์ของหน้าสอบออกจาก repo เดิม**

```bash
# ใน repo ใหม่ assessment/
rm tests/test_scorecard.py
```

แล้วลบออกจาก `tests/conftest.py` ของ repo ใหม่: fixture `open_ats` ทั้งก้อน,
function `candidate()`, function `scorecard()` — เหลือไว้เฉพาะ `server`, `browser`,
`open_exam`, `exam_record`, `legacy_exam_record`

ในทางกลับกัน ที่ `tests/conftest.py` ของ **repo เดิม** ให้ลบ `open_exam`,
`exam_record`, `legacy_exam_record` ออก และลบ `tests/test_pdpa_key.py` ทิ้ง

```bash
python -m pytest tests/ -v
```

Expected: PASS — เทสต์ของหน้าสอบทั้งหมดผ่านใน repo ใหม่ และรันในrepo เดิมแล้ว
เทสต์ ATS ต้องยังผ่านครบ

- [ ] **Step 4: เพิ่ม `CNAME`**

```bash
echo "assessment.hinomotorsasia.com" > CNAME
git add -A
git commit -m "Split the candidate exam app into its own repository"
```

- [ ] **Step 5: push ขึ้น GitHub แล้วเปิด Pages**

```bash
gh repo create assessment --public --source=. --push
```

ใน Settings → Pages ตั้ง Source = `main` / root
**อย่าเพิ่งเปิด Enforce HTTPS**

- [ ] **Step 6: ขอ DNS record จาก IT แล้วรอ propagate**

ข้อความที่ส่ง IT:

> ขอเพิ่ม DNS record ให้ระบบแบบทดสอบผู้สมัครงานของฝ่าย HR ครับ
> ชนิด: CNAME · ชื่อ: `assessment` · ค่า: `ppintarawut-cmyk.github.io`

ตรวจว่า propagate แล้ว:

```bash
nslookup assessment.hinomotorsasia.com
```

Expected: ชี้ไป `ppintarawut-cmyk.github.io`

- [ ] **Step 7: เปิด Enforce HTTPS แล้วตรวจ**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://assessment.hinomotorsasia.com/
```

Expected: `200`

- [ ] **Step 8: ตรวจว่าไฟล์ภายในไม่หลุดมาบน domain ใหม่**

```bash
for f in hma-ats.html CONTEXT.md README.md hma-testing-system.html tools/migrate-candidate-key.html; do
  echo -n "$f : "
  curl -s -o /dev/null -w "%{http_code}\n" https://assessment.hinomotorsasia.com/$f
done
```

Expected: `404` ทุกไฟล์ — ถ้าเจอ 200 แม้แต่ตัวเดียว ให้ลบไฟล์นั้นออกจาก repo ใหม่แล้วเริ่ม Step 8 ใหม่

- [ ] **Step 9: เปลี่ยน `index.html` ใน repo เดิมเป็นหน้า redirect**

```html
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ย้ายที่อยู่แล้ว — HMA Testing System</title>
<meta http-equiv="refresh" content="0; url=https://assessment.hinomotorsasia.com/">
<link rel="canonical" href="https://assessment.hinomotorsasia.com/">
<style>
  body{font-family:system-ui,sans-serif;max-width:520px;margin:80px auto;padding:0 20px;
       line-height:1.8;text-align:center;color:#1a1d1f}
  a{color:#0f9b78;font-weight:600;word-break:break-all}
</style>
</head>
<body>
  <h1>แบบทดสอบย้ายที่อยู่แล้ว</h1>
  <p>ระบบกำลังพาท่านไปยังที่อยู่ใหม่ ถ้าไม่ถูกพาไปอัตโนมัติภายใน 5 วินาที กรุณากดลิงก์ด้านล่าง</p>
  <p><a href="https://assessment.hinomotorsasia.com/">https://assessment.hinomotorsasia.com/</a></p>
</body>
</html>
```

- [ ] **Step 10: ลบไฟล์ที่ย้ายไปแล้วออกจาก repo เดิม แล้ว commit**

```bash
cd ../hma=testing-system/files
rm hma-testing-system.html hma-personality.html privacy.html
git add -A
git commit -m "Redirect the old exam URL to assessment.hinomotorsasia.com"
git push
```

- [ ] **Step 11: ตรวจว่าลิงก์เก่ายังพาไปถึงข้อสอบ**

```bash
curl -s https://ppintarawut-cmyk.github.io/hma-hr-assessment/ | grep -c "assessment.hinomotorsasia.com"
```

Expected: มากกว่า 0

- [ ] **Step 12: ตรวจว่า ATS ยังทำงานที่เดิม**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://ppintarawut-cmyk.github.io/hma-hr-assessment/hma-ats.html
```

Expected: `200` — และเปิดด้วยเบราว์เซอร์แล้วข้อมูลผู้สมัครใน localStorage ต้องยังอยู่ครบ

- [ ] **Step 13: รัน migration บน Firestore**

เปิด `tools/migrate-candidate-key.html` → login superadmin → **กด "ตรวจสอบอย่างเดียว" ก่อน**

ถ้ารายงานว่ามี record ที่ไม่มีอีเมล → **หยุด** และรายงาน Pin ห้ามกด "ลงมือจริง"
ถ้าเป็น 0 → export Firestore สำรอง → กด "ลงมือจริง"

- [ ] **Step 14: ตรวจผลหลัง migrate**

เปิด ATS แล้ว login cloud — ผลสอบของผู้สมัครเดิมต้องยังจับคู่กับใบสมัครได้เหมือนเดิม

---

## หลัง Task 8 — ยังค้างอยู่ (เฟส 2)

- ATS และเอกสารภายในยังถูกเสิร์ฟสาธารณะที่ URL เดิม รวมถึง `tools/migrate-candidate-key.html` ที่เพิ่งเพิ่ม (inert ถ้าไม่ login แต่ไม่ควรเปิดค้างไว้ — ลบทิ้งได้หลัง migrate เสร็จ)
- เฉลยและการให้คะแนนยังอยู่ฝั่ง client
- Firestore rules ยังยอมให้ create `exam_records` / `result_snapshots` แบบไม่ต้อง login
- Firebase project ยังอยู่ใต้บัญชี Gmail ส่วนตัว
- รหัสผ่านเก่า 3 ตัวยังอยู่ใน git history สาธารณะ
- ลบ fallback `national_id` / `nid` ออกจาก `candKey()` ได้หลัง migration นิ่งแล้วอย่างน้อย 1 รอบสรรหา
