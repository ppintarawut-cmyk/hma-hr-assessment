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
