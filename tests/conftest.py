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
            payload = json.dumps(json.dumps(db))
            # Seed once, on first navigation only — never overwrite state the page has
            # since written. add_init_script re-fires on every navigation in this context
            # (including page.reload()), so an unconditional setItem here would silently
            # wipe anything saved before a reload, turning reload-persistence tests into
            # no-ops regardless of whether the app actually persisted correctly.
            ctx.add_init_script(
                f"if (!localStorage.getItem('hma_ats_v1')) localStorage.setItem('hma_ats_v1', {payload})")
        page = ctx.new_page()
        # patchright's evaluate() defaults to an isolated JS world (its anti-detection patch —
        # see patchright METADATA: "avoids using Runtime.enable ... executing Javascript in
        # (isolated) ExecutionContexts"). hma-ats.html's DB/makeCandidate/calcScorecardTotal
        # are plain top-level let/const/function in the page's own inline <script>, which an
        # isolated world cannot see. Force main-world evaluation so page.evaluate(...) below
        # behaves like vanilla Playwright's default and can reach them.
        _orig_evaluate = page.evaluate
        page.evaluate = lambda expr, arg=None: _orig_evaluate(expr, arg, isolated_context=False)
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
