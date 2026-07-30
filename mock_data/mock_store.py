"""
Realistic mock data for local development and CI testing.

Scenario: PR 0010000042 requests 500 EA of material MAT-0042
(Office Chair, ergonomic) for plant 1010 with three candidate suppliers.

Suppliers:
  VEND-001  GreenOffice GmbH       — low price, high eval score, good history
  VEND-002  OfficeSupply AG        — mid price, very reliable delivery
  VEND-003  BudgetFurniture Ltd    — lowest price, poor delivery, no eval score
"""

# ── Purchase Requisitions ──────────────────────────────────────────────────
purchase_requisitions = {
    "0010000042": {
        "PurchaseRequisition": "0010000042",
        "PurchaseRequisitionType": "NB",
        "CreatedByUser": "I536350",
        "CreationDate": "2026-07-28",
        "PurchasingOrganization": "1010",
    }
}

pr_items = {
    "0010000042": [
        {
            "PurchaseRequisition": "0010000042",
            "PurchaseRequisitionItem": "00010",
            "Material": "MAT-0042",
            "PurchaseRequisitionItemText": "Office Chair, ergonomic, adjustable armrests",
            "RequestedQuantity": 500,
            "BaseUnit": "EA",
            "Plant": "1010",
            "DeliveryDate": "2026-09-15",
            "PurchasingGroup": "001",
            "AccountAssignmentCategory": "K",
            "GLAccount": "0006173000",
            "CostCenter": "CC-1050",
        }
    ]
}

# ── Sources of Supply ──────────────────────────────────────────────────────
sources_of_supply = {
    "MAT-0042|1010": [
        {
            "Supplier": "VEND-001",
            "SupplierName": "GreenOffice GmbH",
            "PurchasingInfoRecord": "5300000101",
            "OutlineAgreement": None,
            "NetPriceAmount": 89.50,
            "DocumentCurrency": "EUR",
            "NetPriceQuantityUnit": "EA",
            "ValidityStartDate": "2026-01-01",
            "ValidityEndDate": "2026-12-31",
            "IsFixedSource": False,
            "PurchasingOrganization": "1010",
        },
        {
            "Supplier": "VEND-002",
            "SupplierName": "OfficeSupply AG",
            "PurchasingInfoRecord": "5300000102",
            "OutlineAgreement": None,
            "NetPriceAmount": 94.00,
            "DocumentCurrency": "EUR",
            "NetPriceQuantityUnit": "EA",
            "ValidityStartDate": "2026-01-01",
            "ValidityEndDate": "2026-12-31",
            "IsFixedSource": False,
            "PurchasingOrganization": "1010",
        },
        {
            "Supplier": "VEND-003",
            "SupplierName": "BudgetFurniture Ltd",
            "PurchasingInfoRecord": "5300000103",
            "OutlineAgreement": None,
            "NetPriceAmount": 75.00,
            "DocumentCurrency": "EUR",
            "NetPriceQuantityUnit": "EA",
            "ValidityStartDate": "2026-03-01",
            "ValidityEndDate": "2026-11-30",
            "IsFixedSource": False,
            "PurchasingOrganization": "1010",
        },
    ]
}

# ── Info Records (extended price data) ────────────────────────────────────
info_records = {
    "5300000101": {"PurchasingInfoRecord": "5300000101", "Supplier": "VEND-001", "NetPriceAmount": 89.50},
    "5300000102": {"PurchasingInfoRecord": "5300000102", "Supplier": "VEND-002", "NetPriceAmount": 94.00},
    "5300000103": {"PurchasingInfoRecord": "5300000103", "Supplier": "VEND-003", "NetPriceAmount": 75.00},
}

# ── Historical Purchase Orders ─────────────────────────────────────────────
historical_pos = {
    "VEND-001|MAT-0042": [
        {
            "PurchaseOrder": "4500001001", "PurchaseOrderItem": "00010",
            "Supplier": "VEND-001", "Material": "MAT-0042",
            "PurchaseOrderDate": "2026-04-10", "NetPriceAmount": 91.00,
            "NetPriceQuantityUnit": "EUR", "OrderQuantity": 200,
            "GoodsReceiptQuantity": 200,
            "ScheduleLineDeliveryDate": "2026-05-05",
            "ActualDeliveryDate": "2026-05-04",
            "InvoiceQuantity": 200,
        },
        {
            "PurchaseOrder": "4500000880", "PurchaseOrderItem": "00010",
            "Supplier": "VEND-001", "Material": "MAT-0042",
            "PurchaseOrderDate": "2025-11-15", "NetPriceAmount": 92.50,
            "NetPriceQuantityUnit": "EUR", "OrderQuantity": 150,
            "GoodsReceiptQuantity": 150,
            "ScheduleLineDeliveryDate": "2025-12-10",
            "ActualDeliveryDate": "2025-12-09",
            "InvoiceQuantity": 150,
        },
        {
            "PurchaseOrder": "4500000721", "PurchaseOrderItem": "00010",
            "Supplier": "VEND-001", "Material": "MAT-0042",
            "PurchaseOrderDate": "2025-07-03", "NetPriceAmount": 93.00,
            "NetPriceQuantityUnit": "EUR", "OrderQuantity": 300,
            "GoodsReceiptQuantity": 300,
            "ScheduleLineDeliveryDate": "2025-08-01",
            "ActualDeliveryDate": "2025-07-30",
            "InvoiceQuantity": 300,
        },
    ],
    "VEND-002|MAT-0042": [
        {
            "PurchaseOrder": "4500001010", "PurchaseOrderItem": "00010",
            "Supplier": "VEND-002", "Material": "MAT-0042",
            "PurchaseOrderDate": "2026-03-20", "NetPriceAmount": 95.00,
            "NetPriceQuantityUnit": "EUR", "OrderQuantity": 100,
            "GoodsReceiptQuantity": 100,
            "ScheduleLineDeliveryDate": "2026-04-15",
            "ActualDeliveryDate": "2026-04-15",
            "InvoiceQuantity": 100,
        },
        {
            "PurchaseOrder": "4500000900", "PurchaseOrderItem": "00010",
            "Supplier": "VEND-002", "Material": "MAT-0042",
            "PurchaseOrderDate": "2026-01-08", "NetPriceAmount": 96.00,
            "NetPriceQuantityUnit": "EUR", "OrderQuantity": 50,
            "GoodsReceiptQuantity": 50,
            "ScheduleLineDeliveryDate": "2026-02-01",
            "ActualDeliveryDate": "2026-02-01",
            "InvoiceQuantity": 50,
        },
    ],
    # VEND-003 has no prior POs — new supplier
    "VEND-003|MAT-0042": [],
}

# ── Supplier Evaluations (SAP MM — ME6H) ──────────────────────────────────
supplier_evaluations = {
    "VEND-001": {
        "Supplier": "VEND-001",
        "PurchasingOrganization": "1010",
        "OverallScore": 87,
        "PriceScore": 82,
        "QualityScore": 91,
        "DeliveryScore": 88,
        "ServiceScore": 85,
        "EvaluationDate": "2026-06-30",
    },
    "VEND-002": {
        "Supplier": "VEND-002",
        "PurchasingOrganization": "1010",
        "OverallScore": 79,
        "PriceScore": 71,
        "QualityScore": 84,
        "DeliveryScore": 95,
        "ServiceScore": 78,
        "EvaluationDate": "2026-06-30",
    },
    # VEND-003 has not yet been evaluated
}
