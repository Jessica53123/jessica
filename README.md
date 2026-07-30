# Sourcing & Procurement AI Agent — SAP S/4HANA F1048A

An AI agent that analyses available sources of supply for **non-catalog
purchase requisitions** in SAP S/4HANA Private Cloud and recommends the
best supplier with transparent, data-driven reasoning.

| | |
|---|---|
| **SAP App** | Process Purchase Requisitions V2 (F1048A) |
| **SAP Module** | MM — Sourcing & Procurement |
| **Deployment** | SAP S/4HANA Private Cloud |
| **AI Model** | Anthropic Claude (claude-sonnet-5) |

---

## What the agent does

```
PR received
    │
    ▼
1. Fetch PR items          (material, plant, quantity, delivery date)
    │
    ▼
2. Fetch Sources of Supply (info records, contracts — same as F1048A UI)
    │
    ▼
3. For each candidate supplier:
   ├─ Analyze historical PO data   (avg price, delivery reliability)
   └─ Fetch Supplier Evaluation    (overall + sub-criteria scores)
    │
    ▼
4. Score & Rank suppliers          (weighted composite: price 35% |
                                    delivery 30% | evaluation 35%)
    │
    ▼
5. Present recommendation          (ranked table + rationale + risks)
```

## Scoring model

| Dimension | Default weight | Data source |
|---|---|---|
| Price competitiveness | 35 % | Info record / source of supply |
| Delivery reliability | 30 % | Historical PO on-time rate |
| Supplier evaluation | 35 % | SAP MM Supplier Evaluation (ME6H) |

All weights are configurable via environment variables.

---

## Project structure

```
jessica/
├── src/
│   ├── agent.py        # Main agent loop (Anthropic tool-use)
│   ├── tools.py        # Tool definitions + business logic
│   ├── sap_client.py   # SAP OData API client
│   └── config.py       # Configuration from env vars
├── mock_data/
│   └── mock_store.py   # Realistic mock data (3 suppliers, 1 PR)
├── tests/
│   └── test_tools.py   # Unit tests (pytest)
├── .env.example        # Environment variable template
└── requirements.txt
```

---

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — fill in ANTHROPIC_API_KEY and SAP connection details
```

### 3a. Run against live SAP

```bash
cd src
python agent.py 0010000042 1010
```

### 3b. Run with mock data (no SAP needed)

```bash
USE_MOCK_DATA=true python src/agent.py 0010000042 1010
```

### 4. Run tests

```bash
python -m pytest tests/ -v
```

---

## SAP APIs used

| API | Purpose |
|---|---|
| `API_PURCHASEREQ_PROCESS_SRV` | Read PR header + items |
| `API_PURCHASING_SOURCE_SRV` | Sources of supply, info records |
| `API_PURCHASE_ORDER_SRV` | Historical PO data |
| `API_SUPPLIER_EVALUATION_SRV` | Supplier evaluation scores |

All APIs are standard SAP S/4HANA OData services — no custom development
required on the SAP side.

---

## Example output

```
Recommendation for PR 0010000042 — Office Chair, ergonomic (500 EA)

| Rank | Supplier             | Score | Price  | Delivery | Eval |
|------|----------------------|-------|--------|----------|------|
|  1   | GreenOffice GmbH     | 84.2  | 89.50€ | 100.0%   |  87  |
|  2   | OfficeSupply AG      | 82.1  | 94.00€ |  100.0%  |  79  |
|  3   | BudgetFurniture Ltd  | 55.0  | 75.00€ |  N/A     |  N/A |

Recommendation: GreenOffice GmbH (VEND-001)
Reason: Best balanced score across price, delivery reliability (100% on-time,
3 prior POs), and SAP supplier evaluation (87/100).

Risk flags:
  ⚠ BudgetFurniture Ltd has no prior PO history and no evaluation score.
  ⚠ BudgetFurniture Ltd info record expires 2026-11-30 — before delivery date.

Next step in F1048A: Assign source → GreenOffice GmbH info record 5300000101
→ Release PR → Create Purchase Order.
```
