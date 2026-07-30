"""
Unit tests for tools.py using mock data.

Run with:  cd jessica && python -m pytest tests/ -v
"""

import sys
import os

# Ensure src/ and mock_data/ are on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("USE_MOCK_DATA", "true")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("SAP_BASE_URL", "https://mock")
os.environ.setdefault("SAP_USER", "mock")
os.environ.setdefault("SAP_PASSWORD", "mock")

import tools


# ---------------------------------------------------------------------------
# fetch_purchase_requisition
# ---------------------------------------------------------------------------

def test_fetch_pr_returns_items():
    result = tools.fetch_purchase_requisition("0010000042")
    assert result["pr_number"] == "0010000042"
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["material"] == "MAT-0042"
    assert item["quantity"] == 500
    assert item["plant"] == "1010"


# ---------------------------------------------------------------------------
# fetch_sources_of_supply
# ---------------------------------------------------------------------------

def test_fetch_sources_returns_three_suppliers():
    sources = tools.fetch_sources_of_supply("MAT-0042", "1010")
    assert len(sources) == 3
    suppliers = {s["supplier"] for s in sources}
    assert "VEND-001" in suppliers
    assert "VEND-003" in suppliers


def test_fetch_sources_price_present():
    sources = tools.fetch_sources_of_supply("MAT-0042", "1010")
    for s in sources:
        assert s["net_price"] is not None, f"Price missing for {s['supplier']}"


# ---------------------------------------------------------------------------
# analyze_historical_po_performance
# ---------------------------------------------------------------------------

def test_po_performance_vend001():
    result = tools.analyze_historical_po_performance("VEND-001", "MAT-0042")
    assert result["po_count"] == 3
    assert result["avg_net_price"] == 92.17
    assert result["delivery_reliability_pct"] == 100.0


def test_po_performance_new_supplier():
    result = tools.analyze_historical_po_performance("VEND-003", "MAT-0042")
    assert result["po_count"] == 0
    assert result["delivery_reliability_pct"] is None


# ---------------------------------------------------------------------------
# fetch_supplier_evaluation
# ---------------------------------------------------------------------------

def test_eval_vend001():
    result = tools.fetch_supplier_evaluation("VEND-001", "1010")
    assert result["overall_score"] == 87
    assert result["delivery_score"] == 88


def test_eval_missing_supplier():
    result = tools.fetch_supplier_evaluation("VEND-003", "1010")
    assert result["overall_score"] is None


# ---------------------------------------------------------------------------
# score_and_rank_suppliers
# ---------------------------------------------------------------------------

def test_ranking_top_supplier():
    sources = tools.fetch_sources_of_supply("MAT-0042", "1010")
    po_metrics = [
        tools.analyze_historical_po_performance(s["supplier"], "MAT-0042")
        for s in sources
    ]
    evaluations = [
        tools.fetch_supplier_evaluation(s["supplier"], "1010")
        for s in sources
    ]
    ranked = tools.score_and_rank_suppliers(sources, po_metrics, evaluations)

    assert len(ranked) == 3
    # All ranks are assigned
    assert {r["rank"] for r in ranked} == {1, 2, 3}
    # Top supplier has a composite score
    assert ranked[0]["composite_score"] is not None
    # Rationale is a non-empty string
    assert isinstance(ranked[0]["rationale"], str) and len(ranked[0]["rationale"]) > 10


def test_ranking_custom_weights():
    sources = tools.fetch_sources_of_supply("MAT-0042", "1010")
    po_metrics = [
        tools.analyze_historical_po_performance(s["supplier"], "MAT-0042")
        for s in sources
    ]
    evaluations = [
        tools.fetch_supplier_evaluation(s["supplier"], "1010")
        for s in sources
    ]
    # Heavily price-driven
    ranked = tools.score_and_rank_suppliers(
        sources,
        po_metrics,
        evaluations,
        weights={"price_weight": 0.80, "delivery_weight": 0.10, "evaluation_weight": 0.10},
    )
    # With 80% weight on price, the cheapest supplier (VEND-003 @ 75 EUR) should rank first
    assert ranked[0]["supplier"] == "VEND-003"
