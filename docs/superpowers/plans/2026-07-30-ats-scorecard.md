# ATS Interview Scorecard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the recruiter record weighted 1–5 interview ratings for a candidate across multiple rounds, and surface the latest round's score in the candidate table, the Kanban card, and the CSV export.

**Architecture:** Everything lives in the single file `hma-ats.html` — this app has no build step and no modules. The criteria template is one array on the existing `DB` object (same pattern as `DB.emailTemplates`); each filled scorecard is an entry in `candidate.scorecards`. Every saved scorecard freezes both its computed `total` and a full snapshot of the criteria used (`weightsUsed`), so later edits to the criteria never rewrite past evaluations. Tests are browser tests driven by patchright against a local static server.

**Tech Stack:** Vanilla JS + HTML in one file · localStorage (`hma_ats_v1`) · pytest 8.3.3 + patchright (Chromium, headless) · `python -m http.server`

## Global Constraints

- Target file is `hma-ats.html` only. No new runtime files, no build step, no dependencies.
- Local-first, single user. Do not add a backend, sync, or auth (`docs/decisions/0001`).
- Never modify `c.score` or its renderers — that is the resume-match score, a different number.
- Add new candidate fields through `makeCandidate()` only; it is the single constructor for every candidate source (the code comment says so explicitly).
- Read possibly-missing arrays defensively as `(c.scorecards || [])`, matching the existing `(c.matched || [])` style. Do not write a migration that rewrites candidate records.
- Unrated criteria are excluded from **both** numerator and denominator. Never score them as 0.
- "Not yet evaluated" renders as a grey `—`, never `0`.
- CSS custom properties available: `--teal --teal-d --teal-l --teal-b --gray-50 --gray-100 --gray-200 --gray-300 --gray-400 --gray-500 --gray-700 --gray-900 --white --radius --radius-lg --shadow --pass --pass-l --pass-b --fail --fail-l --pend`. **There is no `--gray-600`.**
- Button classes available: `.btn` plus `.btn-primary .btn-secondary .btn-ghost .btn-danger .btn-sm`.
- Existing helpers to reuse, not reimplement: `esc()`, `toast()`, `fmtDate()`, `uid()`, `scoreBar()`, `scoreClass()`, `saveDB()`, `jobById()`, `renderCandidates()`.
- Run every test command from the `files/` directory (the repo root of this project).

---

## File Structure

| File | Responsibility |
|---|---|
| `hma-ats.html` | All feature code (data, calculation, UI, export). Modified by every task. |
| `tests/conftest.py` | **Create in Task 1.** pytest fixtures: static server, browser, page-with-seeded-DB, candidate factory. |
| `tests/test_scorecard.py` | **Create in Task 1, extended by every later task.** All scorecard tests. |

Tests go in the repo (not a scratchpad) deliberately: previous test suites for this project were written to session scratchpads and were lost when those sessions expired.

---

### Task 1: Data layer — criteria template, candidate field, score calculation

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_scorecard.py`
- Modify: `hma-ats.html` (near `seedEmailTemplates()` ~line 918, `loadDB()` ~line 919, `makeCandidate()` ~line 1367)

**Interfaces:**
- Consumes: nothing (first task)
- Produces:
  - `SC_DEFAULT_CRITERIA` — `Array<{id: string, label: string, weight: number}>`
  - `seedScorecardCriteria()` → fresh copy of the above
  - `DB.scorecardCriteria` — `Array<{id, label, weight}>`, guaranteed non-empty after `loadDB()`
  - `calcScorecardTotal(ratings, criteria)` → `number` 0–100, or `null` when nothing is rated
    - `ratings`: `{[criterionId: string]: number}` — absent key means "not rated"
    - `criteria`: `Array<{id: string, weight: number}>` (extra properties ignored)
  - `candidate.scorecards` — `Array<Scorecard>`, `[]` on new candidates
  - `Scorecard` = `{id, round, at, ratings, note, total, weightsUsed}` where `weightsUsed` is `Array<{id, label, weight}>`

- [ ] **Step 1: Write the failing tests**

Create `tests/conftest.py`:

```python
import json
import pathlib
import socket
import subprocess
import sys
import time

import pytest
from patchright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent   # โฟลเดอร์ files/
PORT = 8791
BASE = f"http://127.0.0.1:{PORT}"


def _port_open(port):
    with socket.socket() as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture(scope="session")
def server():
    """เสิร์ฟโฟลเดอร์ files/ ถ้ามีเซิร์ฟเวอร์รันอยู่แล้วก็ใช้ตัวนั้น"""
    if _port_open(PORT):
        yield BASE
        return
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(PORT)],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if _port_open(PORT):
            break
        time.sleep(0.1)
    else:
        proc.terminate()
        raise RuntimeError(f"http.server ไม่ขึ้นที่พอร์ต {PORT}")
    yield BASE
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def open_ats(browser, server):
    """เปิด hma-ats.html โดย seed localStorage ก่อนสคริปต์ของหน้าจะรัน"""
    contexts = []

    def _open(db=None):
        ctx = browser.new_context()
        contexts.append(ctx)
        if db is not None:
            # seed ค่าตั้งต้นเท่านั้น — add_init_script รันทุกครั้งที่ navigate รวมถึง
            # page.reload() ถ้าเขียนทับทุกครั้ง เทสต์ persistence จะผ่านไม่ได้เลย
            payload = json.dumps(json.dumps(db))
            ctx.add_init_script(
                f"if (!localStorage.getItem('hma_ats_v1')) localStorage.setItem('hma_ats_v1', {payload})")
        page = ctx.new_page()
        page.goto(f"{server}/hma-ats.html")
        page.wait_for_function("typeof DB !== 'undefined'")
        return page

    yield _open
    for ctx in contexts:
        ctx.close()


def candidate(**over):
    """record ผู้สมัครขั้นต่ำที่ผ่าน guard ของ renderer ทุกตัว"""
    base = {
        "id": "cand1", "name": "สมชาย ทดสอบ", "email": "somchai@example.com",
        "phone": "", "jobId": "", "source": "manual", "fileName": "",
        "resumeText": "", "expYears": 3, "education": "", "warnings": [],
        "score": 60, "breakdown": [], "matched": [], "missing": [],
        "missingRequired": [], "stage": "Interview",
        "addedAt": "2026-07-01T00:00:00.000Z", "scorecards": [],
    }
    base.update(over)
    return base


def scorecard(**over):
    base = {
        "id": "sc1", "round": "สัมภาษณ์ HR", "at": "2026-07-20T03:00:00.000Z",
        "ratings": {"c1": 4, "c2": 5, "c3": 3, "c4": 4, "c5": 3},
        "note": "สื่อสารดี", "total": 78,
        "weightsUsed": [
            {"id": "c1", "label": "ความรู้ทางเทคนิค / ตรงสายงาน", "weight": 3},
            {"id": "c2", "label": "การสื่อสาร", "weight": 2},
            {"id": "c3", "label": "ทัศนคติ & ความรับผิดชอบ", "weight": 2},
            {"id": "c4", "label": "ความเหมาะสมกับทีม", "weight": 2},
            {"id": "c5", "label": "การแก้ปัญหา", "weight": 1},
        ],
    }
    base.update(over)
    return base
```

Create `tests/test_scorecard.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_scorecard.py -v`

Expected: all 6 FAIL. The `calcScorecardTotal` tests fail with a page error containing `calcScorecardTotal is not defined`; `test_fresh_db_seeds_five_criteria` fails with `TypeError: Cannot read properties of undefined (reading 'map')`.

- [ ] **Step 3: Add the criteria template and seeder**

In `hma-ats.html`, immediately **after** the existing `seedEmailTemplates()` line (~918), insert:

```js
/* เกณฑ์ประเมินสัมภาษณ์ — ชุดกลางชุดเดียวใช้ทุกตำแหน่ง แก้ได้ในโมดัลตั้งค่า */
const SC_DEFAULT_CRITERIA = [
  { id: 'c1', label: 'ความรู้ทางเทคนิค / ตรงสายงาน', weight: 3 },
  { id: 'c2', label: 'การสื่อสาร',                    weight: 2 },
  { id: 'c3', label: 'ทัศนคติ & ความรับผิดชอบ',        weight: 2 },
  { id: 'c4', label: 'ความเหมาะสมกับทีม',              weight: 2 },
  { id: 'c5', label: 'การแก้ปัญหา',                   weight: 1 },
];
function seedScorecardCriteria() { return SC_DEFAULT_CRITERIA.map(c => Object.assign({}, c)); }
```

- [ ] **Step 4: Add the migration guard in `loadDB()`**

In `loadDB()`, directly after the existing `emailTemplates` guard line, add:

```js
  if (!Array.isArray(d.scorecardCriteria) || !d.scorecardCriteria.length) d.scorecardCriteria = seedScorecardCriteria();  // migration/safety
```

Also extend the default object at the top of `loadDB()` so a first run has it too — change:

```js
  let d = { jobs: [], candidates: [], emailTemplates: seedEmailTemplates() };
```

to:

```js
  let d = { jobs: [], candidates: [], emailTemplates: seedEmailTemplates(), scorecardCriteria: seedScorecardCriteria() };
```

- [ ] **Step 5: Add `scorecards` to `makeCandidate()`**

In `makeCandidate()`, add one property to the object literal, directly after the `stage: 'Applied', addedAt: ...` line:

```js
    stage: 'Applied', addedAt: new Date().toISOString(),
    scorecards: [],
```

- [ ] **Step 6: Add the calculation helpers**

Directly after `seedScorecardCriteria()` from Step 3, add:

```js
/* คิดคะแนนจากหัวข้อที่ให้คะแนนจริงเท่านั้น — หัวข้อที่เว้นไว้ถูกตัดออกทั้งเศษและส่วน
   คืน null เมื่อไม่มีหัวข้อไหนถูกให้คะแนนเลย (ต่างจาก 0 ซึ่งแปลว่า "ประเมินแล้วได้ศูนย์") */
function calcScorecardTotal(ratings, criteria) {
  let earned = 0, possible = 0;
  (criteria || []).forEach(c => {
    const r = ratings ? ratings[c.id] : undefined;
    if (r == null) return;
    earned   += r * c.weight;
    possible += 5 * c.weight;
  });
  return possible ? Math.round(earned / possible * 100) : null;
}
/* "รอบล่าสุด" = ใบที่เพิ่มล่าสุด (ท้าย array) — ฟอร์มไม่ให้แก้วันที่ ลำดับการเพิ่มจึงคือลำดับเวลา */
function latestScorecard(c) {
  const list = (c && c.scorecards) || [];
  return list.length ? list[list.length - 1] : null;
}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest tests/test_scorecard.py -v`

Expected: 6 passed.

- [ ] **Step 8: Commit**

```bash
git add tests/conftest.py tests/test_scorecard.py hma-ats.html
git commit -m "Add scorecard criteria template and weighted score calculation"
```

---

### Task 2: Show the latest round in the candidate table and Kanban card

**Files:**
- Modify: `hma-ats.html` (table header ~line 335, `renderCandTable()` ~line 1708, `candCardHTML()` ~line 1735, CSS block near line 149)
- Test: `tests/test_scorecard.py`

**Interfaces:**
- Consumes: `latestScorecard(c)` and the `Scorecard` shape from Task 1
- Produces:
  - `scorecardCell(c)` → HTML string for the table cell
  - `scorecardChip(c)` → HTML string for the Kanban card, `''` when there is no scorecard

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scorecard.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_scorecard.py -v -k "table or kanban"`

Expected: 4 FAIL. `test_table_shows_dash_when_never_evaluated` fails because column index 4 is currently the skills column, not an interview column.

- [ ] **Step 3: Add the two renderers**

Directly after the existing `scoreCell()` function (~line 961), add:

```js
/* คะแนนสัมภาษณ์รอบล่าสุด — ยังไม่ประเมินต้องเป็น "—" ไม่ใช่ 0
   (0 อ่านว่า "สัมภาษณ์แล้วได้ศูนย์" ซึ่งคนละความหมาย) */
function scorecardCell(c) {
  const list = (c.scorecards || []);
  const sc = latestScorecard(c);
  if (!sc || sc.total == null) return '<span style="color:var(--gray-400)">—</span>';
  const rounds = list.length > 1 ? ` <span class="hint">·${list.length}</span>` : '';
  return `<div style="display:flex; align-items:center; gap:6px">${scoreBar(sc.total)}${rounds}</div>`;
}
function scorecardChip(c) {
  const sc = latestScorecard(c);
  if (!sc || sc.total == null) return '';
  const cls = scoreClass(sc.total);
  const badge = cls === 'hi' ? 'pass' : cls === 'mid' ? 'pend' : 'fail';
  return `<span class="badge ${badge}" title="คะแนนสัมภาษณ์รอบล่าสุด">🗣 ${sc.total}</span>`;
}
```

- [ ] **Step 4: Add the table header cell**

At line ~335, change:

```html
          <th>#</th><th>ผู้สมัคร</th><th>ตำแหน่ง</th><th>คะแนน Match</th><th>ทักษะ</th><th>ประสบการณ์</th><th>สถานะ</th><th>วันที่</th><th></th>
```

to:

```html
          <th>#</th><th>ผู้สมัคร</th><th>ตำแหน่ง</th><th>คะแนน Match</th><th>สัมภาษณ์</th><th>ทักษะ</th><th>ประสบการณ์</th><th>สถานะ</th><th>วันที่</th><th></th>
```

- [ ] **Step 5: Add the table body cell**

In `renderCandTable()`, directly after the `<td>${scoreCell(c.id, c.score)}</td>` line, add:

```js
      <td>${scorecardCell(c)}</td>
```

- [ ] **Step 6: Add the Kanban chip**

In `candCardHTML()`, change the `kc-foot` line from:

```js
    <div class="kc-foot">${scoreCell(c.id, c.score)}
```

to:

```js
    <div class="kc-foot">${scoreCell(c.id, c.score)}${scorecardChip(c)}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest tests/test_scorecard.py -v`

Expected: 10 passed.

- [ ] **Step 8: Commit**

```bash
git add hma-ats.html tests/test_scorecard.py
git commit -m "Show latest interview score in candidate table and Kanban card"
```

---

### Task 3: Scorecard section and rating form in the candidate detail modal

**Files:**
- Modify: `hma-ats.html` (CSS near line 199, `detailHTML()` ~line 1441)
- Test: `tests/test_scorecard.py`

**Interfaces:**
- Consumes: `calcScorecardTotal()`, `latestScorecard()`, `scoreBar()`, `currentDetail` (module-level, set by `showCandDetail`), `uid()`, `saveDB()`, `renderCandidates()`, `toast()`, `esc()`, `fmtDate()`
- Produces:
  - `scorecardSectionHTML(c)` → HTML for the whole section
  - `scorecardBreakdownHTML(s)` → per-criterion rows for one scorecard, rendered from `s.weightsUsed`
  - `toggleScSection()`, `toggleScDetail(id)`, `refreshScorecardSection()`
  - `openScorecardForm(id?)` — renders the form into `#scForm`; omit `id` to add, pass one to edit
  - `scorecardFormHTML(id)`, `editScorecard(id)`, `pickRating(btn)`, `readScForm()`, `scFormCriteria()`, `updateScTotal()`, `saveScorecard()`, `closeScorecardForm()`, `deleteScorecard(id)`
  - DOM contract: section wrapped in `<div id="scSection">`; per-round detail panes `#scd-<scorecardId>`; form container `#scForm`; `#scRound`, `#scNote`, `#scTotal`; rating buttons `.sc-pill[data-crit][data-val]`

`openCriteriaManager()` is referenced by a button rendered here but is implemented in Task 4. Because a missing global would throw on click, Task 4 must land before this feature is used; within this task the button is expected to be inert. Do **not** add a placeholder stub for it — Task 4 defines it.

**Single source for "which criteria does this form use":** `scFormCriteria()` is the only place that decides between an existing scorecard's frozen `weightsUsed` and the current `DB.scorecardCriteria`. `scorecardFormHTML()` must call it rather than repeating the expression. This is safe because `openScorecardForm()` assigns `scEditId` before calling `scorecardFormHTML()`, so both see the same scorecard.

Editing an existing scorecard scores against **that scorecard's `weightsUsed`**, not the current criteria — this is what keeps historical evaluations stable.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scorecard.py`:

```python
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


def test_saved_scorecard_survives_reload(open_ats):
    page = open_ats({"jobs": [], "candidates": [candidate()]})
    _open_form(page)
    page.click(".sc-pill[data-crit='c1'][data-val='4']")
    page.evaluate("() => saveScorecard()")
    page.reload()
    page.wait_for_function("typeof DB !== 'undefined'")
    assert page.evaluate("() => DB.candidates[0].scorecards.length") == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_scorecard.py -v -k "detail or round or scan or form or save or edit or delete or survives"`

Expected: 11 FAIL — Playwright timeouts or `count() == 0` mismatches because `#scSection` does not exist yet, plus `openScorecardForm is not defined`.

- [ ] **Step 3: Add the CSS**

Directly after the `.break-pts` rule (~line 199), add:

```css
.sc-row { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--gray-100); cursor: pointer; }
.sc-detail { padding: 4px 0 10px; }
.sc-crit { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 6px 0; flex-wrap: wrap; }
.sc-pills { display: flex; gap: 4px; }
.sc-pill { min-width: 32px; padding: 5px 8px; border: 1px solid var(--gray-300); background: transparent; color: var(--gray-500); border-radius: var(--radius); cursor: pointer; font-weight: 700; font-size: 12px; }
.sc-pill.on { background: var(--teal); color: #fff; border-color: var(--teal); }
.sc-pill.skip.on { background: var(--gray-300); color: var(--gray-700); border-color: var(--gray-300); }
```

- [ ] **Step 4: Add the section renderers**

Directly before `function detailHTML(r)` (~line 1441), add:

```js
/* ── Scorecard section (ในโมดัลรายละเอียดผู้สมัคร) ── */
const SC_OPEN_KEY = 'hma_ats_sc_open';
function scOpen() { return localStorage.getItem(SC_OPEN_KEY) === '1'; }
function toggleScSection() {
  localStorage.setItem(SC_OPEN_KEY, scOpen() ? '0' : '1');
  refreshScorecardSection();
}
function refreshScorecardSection() {
  const el = document.getElementById('scSection');
  if (el && currentDetail) el.innerHTML = scorecardSectionHTML(currentDetail);
}
function toggleScDetail(id) {
  const el = document.getElementById('scd-' + id);
  if (el) el.style.display = el.style.display === 'none' ? '' : 'none';
}
/* กางรายหัวข้อจาก weightsUsed ที่ freeze ไว้ — ไม่ใช่จากเกณฑ์ปัจจุบัน
   ใบประเมินจึงอ่านได้เสมอแม้หัวข้อจะถูกแก้หรือลบไปแล้ว */
function scorecardBreakdownHTML(s) {
  return (s.weightsUsed || []).map(w => {
    const r = s.ratings ? s.ratings[w.id] : undefined;
    return `<div class="break-row">
      <b>${esc(w.label)}</b>
      <span class="hint">น้ำหนัก ×${w.weight}</span>
      <span class="break-pts">${r == null ? '—' : r + ' / 5'}</span>
    </div>`;
  }).join('') || '<div class="hint">ใบนี้ไม่มีข้อมูลหัวข้อ</div>';
}
function scorecardSectionHTML(c) {
  const list = (c.scorecards || []);
  const sc = latestScorecard(c);
  const open = scOpen();
  const summary = (sc && sc.total != null) ? `${sc.total} · ${list.length} รอบ` : 'ยังไม่ได้ประเมิน';
  const head = `<div class="section-title" style="cursor:pointer" onclick="toggleScSection()">
      🗣 ผลสัมภาษณ์ — ${esc(summary)} ${open ? '▾' : '▸'}
    </div>`;
  if (!open) return head;
  const rows = list.slice().reverse().map(s => `
    <div class="sc-row" onclick="toggleScDetail('${s.id}')">
      <div>
        <b>${esc(s.round)}</b> <span class="hint">· ${fmtDate(s.at)}</span>
        ${s.note ? `<div class="hint" style="margin-top:2px">${esc(s.note)}</div>` : ''}
      </div>
      <div style="display:flex; align-items:center; gap:8px">
        ${s.total == null ? '—' : scoreBar(s.total)}
        <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();editScorecard('${s.id}')">แก้ไข</button>
        <button class="btn btn-danger btn-sm" onclick="event.stopPropagation();deleteScorecard('${s.id}')">ลบ</button>
      </div>
    </div>
    <div id="scd-${s.id}" class="sc-detail" style="display:none">${scorecardBreakdownHTML(s)}</div>`).join('')
    || '<div class="hint">ยังไม่มีใบประเมิน</div>';
  return `${head}
    <div class="sc-list">${rows}</div>
    <div id="scForm"></div>
    <div style="margin-top:10px; display:flex; gap:8px; flex-wrap:wrap">
      <button class="btn btn-secondary btn-sm" onclick="openScorecardForm()">＋ เพิ่มรอบสัมภาษณ์</button>
      <button class="btn btn-ghost btn-sm" onclick="openCriteriaManager()">⚙ ตั้งค่าหัวข้อประเมิน</button>
    </div>`;
}
```

- [ ] **Step 5: Wire the section into `detailHTML()`**

In `detailHTML()`, change:

```js
    <div id="cloudSection">${cloudSectionHTML(r)}</div>
```

to:

```js
    <div id="cloudSection">${cloudSectionHTML(r)}</div>
    ${r.stage ? `<div id="scSection">${scorecardSectionHTML(r)}</div>` : ''}
```

The `r.stage` guard is the same one the email-draft button already uses: saved candidates have a `stage`, unsaved scan results do not.

- [ ] **Step 6: Add the rating form**

Directly after `scorecardSectionHTML()` from Step 4, add:

```js
let scEditId = null;
function openScorecardForm(id) {
  scEditId = id || null;
  const el = document.getElementById('scForm');
  if (el) el.innerHTML = scorecardFormHTML(scEditId);
  updateScTotal();
}
function editScorecard(id) { openScorecardForm(id); }
/* ที่เดียวที่ตัดสินว่าฟอร์มนี้ใช้เกณฑ์ชุดไหน — ใบเก่าใช้ weightsUsed ที่ freeze ไว้
   ใบใหม่ใช้เกณฑ์ปัจจุบัน คะแนนที่บันทึกแล้วจึงไม่ขยับตามการแก้เกณฑ์ */
function scFormCriteria() {
  const ex = scEditId ? ((currentDetail.scorecards || []).find(s => s.id === scEditId)) : null;
  return (ex && ex.weightsUsed && ex.weightsUsed.length) ? ex.weightsUsed : DB.scorecardCriteria;
}
function scorecardFormHTML(id) {
  const ex = id ? ((currentDetail.scorecards || []).find(s => s.id === id)) : null;
  const crit = scFormCriteria();
  const rows = crit.map(w => {
    const cur = (ex && ex.ratings) ? ex.ratings[w.id] : undefined;
    const pills = [1, 2, 3, 4, 5].map(n =>
      `<button type="button" class="sc-pill ${cur === n ? 'on' : ''}" data-crit="${w.id}" data-val="${n}" onclick="pickRating(this)">${n}</button>`).join('');
    return `<div class="sc-crit">
      <div><b>${esc(w.label)}</b> <span class="hint">×${w.weight}</span></div>
      <div class="sc-pills">${pills}<button type="button" class="sc-pill skip ${cur == null ? 'on' : ''}" data-crit="${w.id}" data-val="" onclick="pickRating(this)" title="ไม่ประเมินหัวข้อนี้">—</button></div>
    </div>`;
  }).join('');
  return `<div style="margin-top:12px; border-top:1px solid var(--gray-200); padding-top:12px">
    <div class="field"><label>ชื่อรอบ</label>
      <input id="scRound" list="scRoundList" value="${esc(ex ? ex.round : '')}" placeholder="เช่น สัมภาษณ์ HR">
      <datalist id="scRoundList">
        <option value="สัมภาษณ์ HR"></option>
        <option value="สัมภาษณ์หัวหน้างาน"></option>
        <option value="สัมภาษณ์ผู้บริหาร"></option>
      </datalist>
    </div>
    ${rows}
    <div class="field"><label>บันทึกย่อ</label><textarea id="scNote" rows="2">${esc(ex ? ex.note : '')}</textarea></div>
    <div style="display:flex; align-items:center; gap:10px; margin-top:8px">
      <b>คะแนนรวม: <span id="scTotal">—</span></b>
      <span style="flex:1"></span>
      <button class="btn btn-primary btn-sm" onclick="saveScorecard()">บันทึก</button>
      <button class="btn btn-ghost btn-sm" onclick="closeScorecardForm()">ยกเลิก</button>
    </div>
  </div>`;
}
function pickRating(btn) {
  btn.parentElement.querySelectorAll('.sc-pill').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  updateScTotal();
}
function readScForm() {
  const ratings = {};
  document.querySelectorAll('#scForm .sc-pill.on').forEach(b => {
    if (b.dataset.val !== '') ratings[b.dataset.crit] = Number(b.dataset.val);
  });
  return ratings;
}
function updateScTotal() {
  const el = document.getElementById('scTotal');
  if (!el) return;
  const t = calcScorecardTotal(readScForm(), scFormCriteria());
  el.textContent = t == null ? '—' : t;
}
function closeScorecardForm() {
  scEditId = null;
  const el = document.getElementById('scForm');
  if (el) el.innerHTML = '';
}
function saveScorecard() {
  const crit = scFormCriteria();
  const ratings = readScForm();
  const total = calcScorecardTotal(ratings, crit);
  if (total == null) { toast('ให้คะแนนอย่างน้อย 1 หัวข้อก่อนบันทึก'); return; }
  const round = (document.getElementById('scRound').value || '').trim() || 'สัมภาษณ์';
  const note  = (document.getElementById('scNote').value || '').trim();
  const c = currentDetail;
  if (!Array.isArray(c.scorecards)) c.scorecards = [];
  if (scEditId) {
    const s = c.scorecards.find(x => x.id === scEditId);
    if (s) Object.assign(s, { round, note, ratings, total });
  } else {
    c.scorecards.push({
      id: uid('sc'), round, at: new Date().toISOString(), ratings, note, total,
      weightsUsed: crit.map(w => ({ id: w.id, label: w.label, weight: w.weight })),
    });
  }
  scEditId = null;
  saveDB();
  refreshScorecardSection();
  renderCandidates();
  toast('บันทึกผลสัมภาษณ์แล้ว');
}
function deleteScorecard(id) {
  if (!confirm('ลบใบประเมินนี้?')) return;
  currentDetail.scorecards = (currentDetail.scorecards || []).filter(s => s.id !== id);
  saveDB();
  refreshScorecardSection();
  renderCandidates();
  toast('ลบใบประเมินแล้ว');
}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest tests/test_scorecard.py -v`

Expected: 21 passed.

- [ ] **Step 8: Commit**

```bash
git add hma-ats.html tests/test_scorecard.py
git commit -m "Add scorecard section and rating form to candidate detail modal"
```

---


### Task 4: Criteria manager modal

**Files:**
- Modify: `hma-ats.html` (new modal markup after the email-template modal ~line 543, new functions beside the Task 3 scorecard code)
- Test: `tests/test_scorecard.py`

**Interfaces:**
- Consumes: `DB.scorecardCriteria`, `seedScorecardCriteria()`, `saveDB()`, `refreshScorecardSection()`, `toast()`, `esc()`
- Produces:
  - `openCriteriaManager()`, `renderCriteriaList()`, `addCriterion()`, `updateCriterion(id, field, value)`, `deleteCriterion(id)`, `resetCriteria()`
  - DOM contract: modal `#critModalBg`, list container `#critList`, add button `#critAddBtn`, reset button `#critResetBtn`

The modal must state that changes apply only to scorecards filled from now on — otherwise the frozen-total behaviour reads as a bug.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_scorecard.py`:

```python
def test_criteria_manager_lists_current_criteria(open_ats):
    page = open_ats()
    page.evaluate("() => openCriteriaManager()")
    assert page.locator("#critModalBg").get_attribute("class").find("open") >= 0
    assert page.locator("#critList .sc-crit").count() == 5


def test_criteria_manager_warns_change_is_not_retroactive(open_ats):
    page = open_ats()
    page.evaluate("() => openCriteriaManager()")
    assert "หลังจากนี้" in page.locator("#critModalBg").inner_text()


def test_add_and_delete_criterion(open_ats):
    page = open_ats()
    page.on("dialog", lambda d: d.accept())
    page.evaluate("() => openCriteriaManager()")
    page.evaluate("() => addCriterion()")
    assert page.evaluate("() => DB.scorecardCriteria.length") == 6
    page.evaluate("() => deleteCriterion(DB.scorecardCriteria[5].id)")
    assert page.evaluate("() => DB.scorecardCriteria.length") == 5


def test_changing_weight_does_not_move_saved_totals(open_ats):
    """หัวใจของดีไซน์ — คะแนนที่บันทึกแล้วต้องนิ่ง"""
    page = open_ats({"jobs": [], "candidates": [
        candidate(scorecards=[scorecard(id="a", total=78)])]})
    page.evaluate("() => openCriteriaManager()")
    page.evaluate("() => updateCriterion('c1', 'weight', 5)")
    assert page.evaluate("() => DB.candidates[0].scorecards[0].total") == 78
    assert page.evaluate("() => DB.candidates[0].scorecards[0].weightsUsed[0].weight") == 3


def test_reset_restores_defaults(open_ats):
    page = open_ats()
    page.on("dialog", lambda d: d.accept())
    page.evaluate("() => openCriteriaManager()")
    page.evaluate("() => updateCriterion('c1', 'label', 'เปลี่ยนแล้ว')")
    page.evaluate("() => resetCriteria()")
    assert page.evaluate("() => DB.scorecardCriteria[0].label") == "ความรู้ทางเทคนิค / ตรงสายงาน"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_scorecard.py -v -k "criteria or criterion or reset or weight_does_not"`

Expected: 5 FAIL with `#critModalBg` not found / `addCriterion is not defined`.

- [ ] **Step 3: Add the modal markup**

Directly after the closing `</div>` of the email-template manager modal (the block starting `<div class="modal-bg" id="tplModalBg">` ~line 545), add:

```html
<!-- ============ SCORECARD CRITERIA MODAL ============ -->
<div class="modal-bg" id="critModalBg">
  <div class="modal">
    <div class="modal-head">
      <h2>⚙ ตั้งค่าหัวข้อประเมินสัมภาษณ์</h2>
      <button class="x-btn" data-close="critModalBg">&times;</button>
    </div>
    <div class="modal-body">
      <p class="hint" style="margin-bottom:10px">
        หัวข้อชุดนี้ใช้กับทุกตำแหน่ง · น้ำหนัก 1–5 ยิ่งมากยิ่งมีผลต่อคะแนนรวม ·
        <b>การแก้ไขมีผลกับใบที่ประเมินหลังจากนี้เท่านั้น</b> คะแนนที่บันทึกไปแล้วจะไม่เปลี่ยน
      </p>
      <div id="critList"></div>
      <div style="margin-top:10px; display:flex; gap:8px; flex-wrap:wrap">
        <button class="btn btn-secondary btn-sm" id="critAddBtn">＋ เพิ่มหัวข้อ</button>
        <button class="btn btn-ghost btn-sm" id="critResetBtn">↺ คืนค่าเริ่มต้น</button>
      </div>
    </div>
    <div class="modal-foot">
      <button class="btn btn-ghost" data-close="critModalBg">ปิด</button>
    </div>
  </div>
</div>
```

- [ ] **Step 4: Add the criteria manager functions**

Task 3 rendered a button calling `openCriteriaManager()` but did not define it. Define it now, directly after the scorecard form functions from Task 3:

```js
/* ── Scorecard criteria manager ── */
function openCriteriaManager() {
  renderCriteriaList();
  document.getElementById('critModalBg').classList.add('open');
}
function renderCriteriaList() {
  document.getElementById('critList').innerHTML = DB.scorecardCriteria.map(c => `
    <div class="sc-crit">
      <input value="${esc(c.label)}" style="flex:1; min-width:180px"
             onchange="updateCriterion('${c.id}', 'label', this.value)">
      <div style="display:flex; align-items:center; gap:6px">
        <span class="hint">น้ำหนัก</span>
        <select onchange="updateCriterion('${c.id}', 'weight', Number(this.value))"
                style="padding:5px 8px; border:1px solid var(--gray-300); border-radius:var(--radius); background:var(--white); color:var(--gray-900); font-size:12px">
          ${[1, 2, 3, 4, 5].map(n => `<option ${c.weight === n ? 'selected' : ''}>${n}</option>`).join('')}
        </select>
        <button class="btn btn-danger btn-sm" onclick="deleteCriterion('${c.id}')">ลบ</button>
      </div>
    </div>`).join('') || '<div class="hint">ยังไม่มีหัวข้อ — กด "เพิ่มหัวข้อ"</div>';
}
function updateCriterion(id, field, value) {
  const c = DB.scorecardCriteria.find(x => x.id === id);
  if (!c) return;
  c[field] = value;
  saveDB();
  renderCriteriaList();
  refreshScorecardSection();
}
function addCriterion() {
  DB.scorecardCriteria.push({ id: uid('cr'), label: 'หัวข้อใหม่', weight: 1 });
  saveDB();
  renderCriteriaList();
  refreshScorecardSection();
}
function deleteCriterion(id) {
  if (!confirm('ลบหัวข้อนี้? ใบที่ประเมินไปแล้วจะยังแสดงหัวข้อนี้ได้ตามเดิม')) return;
  DB.scorecardCriteria = DB.scorecardCriteria.filter(x => x.id !== id);
  saveDB();
  renderCriteriaList();
  refreshScorecardSection();
}
function resetCriteria() {
  if (!confirm('คืนค่าหัวข้อทั้งหมดเป็นค่าเริ่มต้น?')) return;
  DB.scorecardCriteria = seedScorecardCriteria();
  saveDB();
  renderCriteriaList();
  refreshScorecardSection();
  toast('คืนค่าหัวข้อเริ่มต้นแล้ว');
}
```

- [ ] **Step 5: Wire the two modal buttons**

The email-template modal binds its buttons with `addEventListener` at lines 2205 and 2208. Add the two matching lines directly after line 2208:

```js
document.getElementById('critAddBtn').addEventListener('click', addCriterion);
document.getElementById('critResetBtn').addEventListener('click', resetCriteria);
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/test_scorecard.py -v`

Expected: 26 passed.

- [ ] **Step 7: Commit**

```bash
git add hma-ats.html tests/test_scorecard.py
git commit -m "Add scorecard criteria manager modal"
```

---

### Task 5: CSV export columns

**Files:**
- Modify: `hma-ats.html` (`exportCSV()` ~line 1860)
- Test: `tests/test_scorecard.py`

**Interfaces:**
- Consumes: `latestScorecard(c)`
- Produces: two new CSV columns, `Interview Score` and `Interview Rounds`, positioned directly after `Match Score`

`exportCSV()` appends a **dynamic** run of exam-result columns (`codes.forEach(...)`) to both `head` and `row`. The new columns must be inserted before that run in both places or the header and data will not line up.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scorecard.py`:

```python
def test_csv_includes_interview_columns(open_ats):
    page = open_ats({"jobs": [], "candidates": [
        candidate(id="c1", name="มีคะแนน",
                  scorecards=[scorecard(id="a", total=72), scorecard(id="b", total=85)]),
        candidate(id="c2", name="ยังไม่ประเมิน", email="none@example.com")]})
    rows = page.evaluate("""() => {
        const out = [];
        const orig = window.downloadCSV;
        window.downloadCSV = r => out.push(r);
        return Promise.resolve(exportCSV()).then(() => { window.downloadCSV = orig; return out[0]; });
    }""")
    head = rows[0]
    assert head.index("Interview Score") == head.index("Match Score") + 1
    assert head[head.index("Interview Score") + 1] == "Interview Rounds"
    i = head.index("Interview Score")
    assert rows[1][i] == 85 and rows[1][i + 1] == 2      # รอบล่าสุด
    assert rows[2][i] == "" and rows[2][i + 1] == ""     # ยังไม่ประเมิน → ว่าง ไม่ใช่ 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_scorecard.py::test_csv_includes_interview_columns -v`

Expected: FAIL with `ValueError: 'Interview Score' is not in list`.

- [ ] **Step 3: Add the header columns**

In `exportCSV()`, change:

```js
  const head = ['Name', 'Email', 'Phone', 'Position', 'Match Score', 'Skills Matched', 'Skills Missing', 'Experience (yrs)', 'Education', 'Stage', 'Source', 'File', 'Added'];
```

to:

```js
  const head = ['Name', 'Email', 'Phone', 'Position', 'Match Score', 'Interview Score', 'Interview Rounds', 'Skills Matched', 'Skills Missing', 'Experience (yrs)', 'Education', 'Stage', 'Source', 'File', 'Added'];
```

- [ ] **Step 4: Add the row values**

In the `rows0.forEach` body, change:

```js
    const row = [c.name, c.email, c.phone, job ? job.title : '', c.score,
      (c.matched || []).join('; '), (c.missing || []).join('; '),
```

to:

```js
    const sc = latestScorecard(c);
    const row = [c.name, c.email, c.phone, job ? job.title : '', c.score,
      (sc && sc.total != null) ? sc.total : '',
      (c.scorecards || []).length || '',
      (c.matched || []).join('; '), (c.missing || []).join('; '),
```

- [ ] **Step 5: Run the full suite to verify everything passes**

Run: `python -m pytest tests/test_scorecard.py -v`

Expected: 27 passed.

- [ ] **Step 6: Commit**

```bash
git add hma-ats.html tests/test_scorecard.py
git commit -m "Add interview score columns to candidate CSV export"
```

---

## Spec Coverage

| Spec requirement | Task |
|---|---|
| `DB.scorecardCriteria` + migration guard | 1 |
| `candidate.scorecards` via `makeCandidate()` | 1 |
| Weighted formula, unrated excluded, `null` when nothing rated | 1 |
| Frozen `total` | 3 (written on save), 4 (proven stable) |
| `weightsUsed` full snapshot incl. label | 1 (shape), 3 (written + rendered from it) |
| Table column, `—` not `0`, round count | 2 |
| Kanban chip | 2 |
| Collapsible section, position after cloud section, state in localStorage | 3 |
| Round list newest→oldest, per-round breakdown | 3 |
| Inline form, 1–5 pills, `—` skip, live total, datalist | 3 |
| Save refuses when nothing rated | 3 |
| Edit reuses the form, delete with `confirm()` | 3 |
| Criteria manager modal + non-retroactive warning | 4 |
| CSV columns | 5 |
| Old records without `scorecards` don't crash | 2 (`test_table_shows_dash_when_never_evaluated`) |
| Scan results show no scorecard section | 3 |
| Deleting a criterion keeps old cards readable | 3 (`test_round_breakdown_uses_frozen_labels`) |
| Changing a weight doesn't move saved totals | 4 (`test_changing_weight_does_not_move_saved_totals`) |
| Persistence across reload | 3 (`test_saved_scorecard_survives_reload`) |
