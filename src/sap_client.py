"""
SAP S/4HANA OData client for Sourcing & Procurement data access.

Connects to the following SAP APIs:
  - API_PURCHASEREQ_PROCESS_SRV  (Purchase Requisitions)
  - API_SUPPLIER_EVALUATION_SRV  (Supplier Evaluation Scores)
  - API_PURCHASING_SOURCE_SRV    (Sources of Supply / Info Records)
  - API_PURCHASE_ORDER_SRV       (Historical Purchase Orders)

App context: Process Purchase Requisitions V2 (F1048A)
"""

import os
import requests
from requests.auth import HTTPBasicAuth
from typing import Any
import config


class SAPClient:
    def __init__(self):
        self.base_url = config.SAP_BASE_URL.rstrip("/")
        self.auth = HTTPBasicAuth(config.SAP_USER, config.SAP_PASSWORD)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
            "sap-client": config.SAP_CLIENT,
        })
        if config.SAP_CERT_PATH:
            self.session.verify = config.SAP_CERT_PATH

    def _get(self, service_path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}/{service_path}"
        params = params or {}
        params["$format"] = "json"
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("d", resp.json())

    # ------------------------------------------------------------------
    # Purchase Requisition APIs  (API_PURCHASEREQ_PROCESS_SRV)
    # ------------------------------------------------------------------

    def get_purchase_requisition(self, pr_number: str) -> dict:
        """Fetch header + item data for a single PR."""
        path = f"sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV/A_PurchaseRequisitionHeader('{pr_number}')"
        return self._get(path, {"$expand": "to_PurchaseReqItem"})

    def get_pr_items(self, pr_number: str) -> list[dict]:
        """Return all line items of a PR."""
        path = "sap/opu/odata/sap/API_PURCHASEREQ_PROCESS_SRV/A_PurchaseRequisitionItem"
        result = self._get(path, {"$filter": f"PurchaseRequisition eq '{pr_number}'"})
        return result.get("results", [])

    # ------------------------------------------------------------------
    # Sources of Supply  (API_PURCHASING_SOURCE_SRV)
    # ------------------------------------------------------------------

    def get_sources_of_supply(self, material: str, plant: str) -> list[dict]:
        """
        Return valid sources of supply (info records, outline agreements)
        for a material/plant combination — the same data shown in the
        'Assign Source of Supply' step of F1048A.
        """
        path = "sap/opu/odata/sap/API_PURCHASING_SOURCE_SRV/A_PurchasingSource"
        filters = (
            f"Material eq '{material}' and Plant eq '{plant}'"
        )
        result = self._get(path, {"$filter": filters, "$expand": "to_SupplierQuotation"})
        return result.get("results", [])

    def get_info_record(self, info_record: str) -> dict:
        """Fetch a purchasing info record (price, conditions, validity)."""
        path = f"sap/opu/odata/sap/API_PURCHASING_SOURCE_SRV/A_PurchasingInfoRecord('{info_record}')"
        return self._get(path)

    # ------------------------------------------------------------------
    # Historical Purchase Orders  (API_PURCHASE_ORDER_SRV)
    # ------------------------------------------------------------------

    def get_historical_pos(
        self,
        supplier: str,
        material: str,
        max_results: int = 50,
    ) -> list[dict]:
        """
        Retrieve historical POs for a supplier+material combination,
        ordered by creation date descending — used to derive avg price,
        delivery reliability, and order frequency.
        """
        path = "sap/opu/odata/sap/API_PURCHASE_ORDER_SRV/A_PurchaseOrderItem"
        filters = (
            f"Supplier eq '{supplier}' and Material eq '{material}'"
        )
        result = self._get(
            path,
            {
                "$filter": filters,
                "$orderby": "PurchaseOrderDate desc",
                "$top": str(max_results),
                "$select": (
                    "PurchaseOrder,PurchaseOrderItem,Supplier,Material,"
                    "PurchaseOrderDate,NetPriceAmount,NetPriceQuantityUnit,"
                    "OrderQuantity,GoodsReceiptQuantity,ScheduleLineDeliveryDate,"
                    "ActualDeliveryDate,InvoiceQuantity,PurchaseOrderItemText"
                ),
            },
        )
        return result.get("results", [])

    # ------------------------------------------------------------------
    # Supplier Evaluation  (API_SUPPLIER_EVALUATION_SRV)
    # ------------------------------------------------------------------

    def get_supplier_evaluation(self, supplier: str, purchasing_org: str) -> dict:
        """
        Fetch the latest supplier evaluation scorecard from SAP MM
        Supplier Evaluation (transaction ME6H / LDB ME).

        Returns overall score plus sub-criteria: Price, Quality,
        Delivery, Service.
        """
        path = (
            "sap/opu/odata/sap/API_SUPPLIER_EVALUATION_SRV"
            f"/A_SupplierEvaluation(Supplier='{supplier}',"
            f"PurchasingOrganization='{purchasing_org}')"
        )
        return self._get(path)

    def get_all_supplier_evaluations(
        self, suppliers: list[str], purchasing_org: str
    ) -> dict[str, dict]:
        """Batch-fetch evaluations for multiple suppliers."""
        results = {}
        for supplier in suppliers:
            try:
                results[supplier] = self.get_supplier_evaluation(supplier, purchasing_org)
            except requests.HTTPError as exc:
                results[supplier] = {"error": str(exc), "OverallScore": None}
        return results
