from lead_scorer.score import score_lead, score_leads

HIGH = {
    "google_rating": 4.8,
    "google_reviews": 200,
    "website": "https://example.com",
    "phone": "+1-555-0000",
    "intel_json": {"types": ["real_estate_agency"]},
}
LOW = {
    "google_rating": None,
    "google_reviews": 0,
    "website": None,
    "phone": None,
    "intel_json": {"types": []},
}


def test_score_lead_returns_float():
    assert isinstance(score_lead(HIGH), float)


def test_score_lead_range():
    for lead in (HIGH, LOW, {}):
        s = score_lead(lead)
        assert 0.0 <= s <= 1.0


def test_score_lead_high_quality():
    assert score_lead(HIGH) > 0.3


def test_score_lead_low_quality():
    assert score_lead(LOW) < 0.15


def test_score_leads_batch():
    out = score_leads([HIGH, LOW, HIGH])
    assert len(out) == 3
    assert out[0] > out[1]
    assert out[0] == out[2]


def test_score_leads_empty():
    assert score_leads([]) == []


def test_score_deterministic():
    assert score_lead(HIGH) == score_lead(HIGH)
