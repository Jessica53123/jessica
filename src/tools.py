"""
Tool definitions for the Sourcing & Procurement AI Agent.

Each tool maps to one callable action the LLM can invoke during its
reasoning loop.  Tools call sap_client.py (live) or mock_data/ (dev/test).
"""

from __future__ import annotations
import json
import statistics
from datetime import date, datetime
from typing import Any

import config
from sap_client import SAPClient

# Use mock data when SAP connectivity is not available (local dev / CI)
if config.USE_MOCK_DATA:
    from mock_data import mock_store as _store

    class _MockClient:
        """Thin shim so tool functions work identically against mock data."""

        def get_purchase_requisition(self, pr_number):
            return _store.purchase_requisitions.get(pr_number, {})

        def get_pr_items(self, pr_number):
            return _store.pr_items.get(pr_number, [])

        def get_sources_of_supply(self, material, plant):
            return _store.sources_of_supply.get(f"{material}|{plant}", [])

        def get_info_record(self, info_record):
            return _store.info_records.get(info_record, {})

        def get_historical_pos(self, supplier, material, max_results=50):
            key = f"{supplier}|{material}"
            return _store.historical_pos.get(key, [])[:max_results]

        def get_supplier_evaluation(self, supplier, purchasing_org):
            return _store.supplier_evaluations.get(supplier, {})

        def get_all_supplier_evaluations(self, suppliers, purchasing_org):
            return {s: _store.supplier_evaluations.get(s, {}) for s in suppliers}

    _client = _MockClient()
else:
    _client = SAPClient()


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _avg(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None]
    return round(statistics.mean(clean), 2) if clean else None


def _delivery_reliability(pos: list[dict]) -> float | None:
    """
    Percentage of PO lines delivered on or before the schedule date.
    Only counts lines where both dates are present.
    """
    total, on_time = 0, 0
    for po in pos:
        sched = po.get("ScheduleLineDeliveryDate")
        actual = po.get("ActualDeliveryDate")
        if sched and actual:
            try:
                s = datetime.fromisoformat(sched[:10])
                a = datetime.fromisoformat(actual[:10])
                total += 1
                if a <= s:
                    on_time += 1
            except ValueError:
                pass
    return round(on_time / total * 100, 1) if total else None


# ---------------------------------------------------------------------------
# Tool 1 — Fetch Purchase Requisition
# ---------------------------------------------------------------------------

def fetch_purchase_requisition(pr_number: str) -> dict:
    """
    Retrieve header and line-item data for a Purchase Requisition from
    SAP S/4HANA (API_PURCHASEREQ_PROCESS_SRV).

    Returns:
        {
          "pr_number": "...",
          "created_by": "...",
          "created_on": "...",
          "items": [
            {
              "item": "00010",
              "material": "MAT-0042",
              "description": "...",
              "quantity": 100,
              "unit": "EA",
              "plant": "1010",
              "delivery_date": "2026-09-01",
              "purchase_group": "001",
              "account_assignment": "K",
              "gl_account": "...",
              "cost_center": "..."
            },
            ...
          ]
        }
    """
    raw = _client.get_purchase_requisition(pr_number)
    items_raw = _client.get_pr_items(pr_number)

    items = []
    for it in items_raw:
        items.append(
            {
                "item": it.get("PurchaseRequisitionItem"),
                "material": it.get("Material"),
                "description": it.get("PurchaseRequisitionItemText"),
                "quantity": it.get("RequestedQuantity"),
                "unit": it.get("BaseUnit"),
                "plant": it.get("Plant"),
                "delivery_date": it.get("DeliveryDate", "")[:10],
                "purchase_group": it.get("PurchasingGroup"),
                "account_assignment": it.get("AccountAssignmentCategory"),
                "gl_account": it.get("GLAccount"),
                "cost_center": it.get("CostCenter"),
            }
        )

    return {
        "pr_number": pr_number,
        "created_by": raw.get("CreatedByUser"),
        "created_on": str(raw.get("CreationDate", ""))[:10],
        "purchasing_org": raw.get("PurchasingOrganization"),
        "items": items,
    }


# ---------------------------------------------------------------------------
# Tool 2 — Fetch Sources of Supply
# ---------------------------------------------------------------------------

def fetch_sources_of_supply(material: str, plant: str) -> list[dict]:
    """
    Return all valid sources of supply for a material/plant pair,
    mirroring the 'Assign Source of Supply' step in F1048A.

    Each source includes: supplier, info record / contract reference,
    price, currency, validity period, and fixed-source flag.
    """
    raw = _client.get_sources_of_supply(material, plant)

    sources = []
    for s in raw:
        sources.append(
            {
                "supplier": s.get("Supplier"),
                "supplier_name": s.get("SupplierName"),
                "info_record": s.get("PurchasingInfoRecord"),
                "contract": s.get("SupplyingPlant") or s.get("OutlineAgreement"),
                "net_price": s.get("NetPriceAmount"),
                "currency": s.get("DocumentCurrency"),
                "price_unit": s.get("NetPriceQuantityUnit"),
                "valid_from": str(s.get("ValidityStartDate", ""))[:10],
                "valid_to": str(s.get("ValidityEndDate", ""))[:10],
                "is_fixed_source": s.get("IsFixedSource", False),
                "purchasing_org": s.get("PurchasingOrganization"),
            }
        )
    return sources


# ---------------------------------------------------------------------------
# Tool 3 — Analyze Historical PO Performance
# ---------------------------------------------------------------------------

def analyze_historical_po_performance(
    supplier: str, material: str
) -> dict:
    """
    Derive key performance metrics for a supplier+material combination
    from historical Purchase Order data.

    Returns:
        {
          "supplier": "...",
          "material": "...",
          "po_count": 12,
          "avg_net_price": 49.80,
          "currency": "EUR",
          "avg_order_quantity": 200,
          "delivery_reliability_pct": 91.7,
          "last_po_date": "2026-04-12"
        }
    """
    pos = _client.get_historical_pos(supplier, material)
    if not pos:
        return {
            "supplier": supplier,
            "material": material,
            "po_count": 0,
            "avg_net_price": None,
            "currency": None,
            "avg_order_quantity": None,
            "delivery_reliability_pct": None,
            "last_po_date": None,
        }

    prices = [float(p["NetPriceAmount"]) for p in pos if p.get("NetPriceAmount")]
    quantities = [float(p["OrderQuantity"]) for p in pos if p.get("OrderQuantity")]
    dates = sorted(
        [p["PurchaseOrderDate"][:10] for p in pos if p.get("PurchaseOrderDate")],
        reverse=True,
    )

    return {
        "supplier": supplier,
        "material": material,
        "po_count": len(pos),
        "avg_net_price": _avg(prices),
        "currency": pos[0].get("NetPriceQuantityUnit", "EUR") if pos else None,
        "avg_order_quantity": _avg(quantities),
        "delivery_reliability_pct": _delivery_reliability(pos),
        "last_po_date": dates[0] if dates else None,
    }


# ---------------------------------------------------------------------------
# Tool 4 — Fetch Supplier Evaluation Scores
# ---------------------------------------------------------------------------

def fetch_supplier_evaluation(supplier: str, purchasing_org: str) -> dict:
    """
    Fetch the SAP MM Supplier Evaluation scorecard (transaction ME6H).

    Scores are on a 1–100 scale. Sub-criteria:
      - PriceScore       : competitiveness of prices offered
      - QualityScore     : defect rates, goods-receipt quality inspections
      - DeliveryScore    : on-time delivery performance
      - ServiceScore     : responsiveness, complaint handling

    Returns:
        {
          "supplier": "...",
          "purchasing_org": "...",
          "overall_score": 87,
          "price_score": 82,
          "quality_score": 91,
          "delivery_score": 88,
          "service_score": 85,
          "evaluation_date": "2026-06-30"
        }
    """
    raw = _client.get_supplier_evaluation(supplier, purchasing_org)
    return {
        "supplier": supplier,
        "purchasing_org": purchasing_org,
        "overall_score": raw.get("OverallScore"),
        "price_score": raw.get("PriceScore"),
        "quality_score": raw.get("QualityScore"),
        "delivery_score": raw.get("DeliveryScore"),
        "service_score": raw.get("ServiceScore"),
        "evaluation_date": str(raw.get("EvaluationDate", ""))[:10],
    }


# ---------------------------------------------------------------------------
# Tool 5 — Score and Rank Suppliers
# ---------------------------------------------------------------------------

def score_and_rank_suppliers(
    sources: list[dict],
    po_metrics: list[dict],
    evaluations: list[dict],
    weights: dict | None = None,
) -> list[dict]:
    """
    Combine price competitiveness, delivery reliability, and supplier
    evaluation scores into a single ranked recommendation list.

    Default weights (all must sum to 1.0):
      price_weight        = 0.35
      delivery_weight     = 0.30
      evaluation_weight   = 0.35

    Returns list sorted by composite_score descending, each entry with
    transparent per-dimension scores and a human-readable rationale.
    """
    w = weights or config.DEFAULT_SCORING_WEIGHTS

    # Build lookup maps
    po_map: dict[str, dict] = {m["supplier"]: m for m in po_metrics}
    eval_map: dict[str, dict] = {e["supplier"]: e for e in evaluations}

    # Price normalisation: lowest price = 100, others scaled proportionally
    prices = [
        float(s["net_price"])
        for s in sources
        if s.get("net_price") is not None
    ]
    min_price = min(prices) if prices else None

    ranked = []
    for src in sources:
        supplier = src["supplier"]
        po = po_map.get(supplier, {})
        ev = eval_map.get(supplier, {})

        # --- price score (0-100) ---
        raw_price = src.get("net_price")
        if raw_price and min_price:
            price_score = round(min_price / float(raw_price) * 100, 1)
        else:
            price_score = None

        # --- delivery score (0-100) ---
        delivery_score = po.get("delivery_reliability_pct")

        # --- evaluation score (0-100) ---
        eval_score = ev.get("overall_score")

        # --- composite (only from available dimensions) ---
        scores, total_weight = [], 0.0
        if price_score is not None:
            scores.append(price_score * w["price_weight"])
            total_weight += w["price_weight"]
        if delivery_score is not None:
            scores.append(delivery_score * w["delivery_weight"])
            total_weight += w["delivery_weight"]
        if eval_score is not None:
            scores.append(eval_score * w["evaluation_weight"])
            total_weight += w["evaluation_weight"]

        composite = round(sum(scores) / total_weight, 1) if total_weight > 0 else None

        ranked.append(
            {
                "rank": None,  # filled after sorting
                "supplier": supplier,
                "supplier_name": src.get("supplier_name"),
                "info_record": src.get("info_record"),
                "quoted_price": raw_price,
                "currency": src.get("currency"),
                "po_count": po.get("po_count", 0),
                "avg_historical_price": po.get("avg_net_price"),
                "delivery_reliability_pct": delivery_score,
                "overall_eval_score": eval_score,
                "price_score": price_score,
                "composite_score": composite,
                "rationale": _build_rationale(
                    supplier,
                    src.get("supplier_name", ""),
                    price_score,
                    delivery_score,
                    eval_score,
                    composite,
                    po.get("po_count", 0),
                    raw_price,
                    src.get("currency", ""),
                ),
            }
        )

    ranked.sort(key=lambda x: x["composite_score"] or 0, reverse=True)
    for i, entry in enumerate(ranked, 1):
        entry["rank"] = i

    return ranked


def _build_rationale(
    supplier: str,
    name: str,
    price_score: float | None,
    delivery: float | None,
    eval_score: float | None,
    composite: float | None,
    po_count: int,
    price: float | None,
    currency: str,
) -> str:
    parts = []
    if price_score is not None:
        parts.append(f"price competitiveness {price_score}/100 (quoted {price} {currency})")
    if delivery is not None:
        parts.append(f"delivery reliability {delivery}% on-time across {po_count} historical POs")
    elif po_count == 0:
        parts.append("no prior PO history with this supplier")
    if eval_score is not None:
        parts.append(f"SAP supplier evaluation score {eval_score}/100")
    body = "; ".join(parts) if parts else "insufficient data for full scoring"
    return f"{name or supplier}: composite score {composite}/100 — {body}."


# ---------------------------------------------------------------------------
# Tool registry (consumed by agent.py to build Claude tool_use blocks)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "fetch_purchase_requisition",
        "description": (
            "Fetch header and item data for a SAP Purchase Requisition from "
            "API_PURCHASEREQ_PROCESS_SRV. Use this first to understand what "
            "material, plant, quantity and delivery date are requested."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pr_number": {
                    "type": "string",
                    "description": "SAP Purchase Requisition number, e.g. '0010000042'",
                }
            },
            "required": ["pr_number"],
        },
    },
    {
        "name": "fetch_sources_of_supply",
        "description": (
            "Return all valid sources of supply (info records, outline agreements) "
            "for a material/plant combination from API_PURCHASING_SOURCE_SRV. "
            "Call once per PR line item."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "material": {"type": "string", "description": "SAP material number"},
                "plant": {"type": "string", "description": "SAP plant code, e.g. '1010'"},
            },
            "required": ["material", "plant"],
        },
    },
    {
        "name": "analyze_historical_po_performance",
        "description": (
            "Compute average price, delivery reliability, and order frequency "
            "for a supplier+material pair from historical PO data "
            "(API_PURCHASE_ORDER_SRV). Call for each candidate supplier."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "supplier": {"type": "string", "description": "SAP supplier/vendor number"},
                "material": {"type": "string", "description": "SAP material number"},
            },
            "required": ["supplier", "material"],
        },
    },
    {
        "name": "fetch_supplier_evaluation",
        "description": (
            "Retrieve the SAP MM Supplier Evaluation scorecard (overall + sub-criteria: "
            "price, quality, delivery, service) from API_SUPPLIER_EVALUATION_SRV."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "supplier": {"type": "string", "description": "SAP supplier/vendor number"},
                "purchasing_org": {
                    "type": "string",
                    "description": "SAP Purchasing Organization, e.g. '1010'",
                },
            },
            "required": ["supplier", "purchasing_org"],
        },
    },
    {
        "name": "score_and_rank_suppliers",
        "description": (
            "Combine price competitiveness, delivery reliability, and supplier evaluation "
            "scores into a weighted composite ranking. Call this after gathering all "
            "sources, PO metrics and evaluation data. Returns ranked list with transparent "
            "per-dimension scores and human-readable rationale."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "array",
                    "description": "Output of fetch_sources_of_supply",
                    "items": {"type": "object"},
                },
                "po_metrics": {
                    "type": "array",
                    "description": "List of outputs from analyze_historical_po_performance",
                    "items": {"type": "object"},
                },
                "evaluations": {
                    "type": "array",
                    "description": "List of outputs from fetch_supplier_evaluation",
                    "items": {"type": "object"},
                },
                "weights": {
                    "type": "object",
                    "description": (
                        "Optional custom weights, e.g. "
                        '{"price_weight":0.4,"delivery_weight":0.3,"evaluation_weight":0.3}. '
                        "Values must sum to 1.0. Omit to use defaults."
                    ),
                },
            },
            "required": ["sources", "po_metrics", "evaluations"],
        },
    },
]

# Map tool name → Python function for the agent loop dispatcher
TOOL_FUNCTIONS: dict[str, Any] = {
    "fetch_purchase_requisition": fetch_purchase_requisition,
    "fetch_sources_of_supply": fetch_sources_of_supply,
    "analyze_historical_po_performance": analyze_historical_po_performance,
    "fetch_supplier_evaluation": fetch_supplier_evaluation,
    "score_and_rank_suppliers": score_and_rank_suppliers,
}
