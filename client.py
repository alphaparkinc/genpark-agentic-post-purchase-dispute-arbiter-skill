"""
Autonomous Agentic Post-Purchase Tracking & Delivery Dispute Arbiter (Zero External Dependencies)
Provides carrier event timeline analysis, stalled shipment detection, and merchant claim payloads.
"""
import time
import math
import hashlib
import json
from typing import Dict, Any, List, Optional

class AgenticPostPurchaseDisputeArbiter:
    def __init__(self, stall_threshold_hours: float = 72.0):
        self.stall_threshold_sec = stall_threshold_hours * 3600.0

    def evaluate_shipment_status(
        self,
        order_id: str,
        carrier_events: List[Dict[str, Any]],
        expected_delivery_timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Parses carrier updates (e.g. FedEx, UPS, DHL, USPS), detects dead stalls and lost packages.
        """
        if not carrier_events:
            return {"order_id": order_id, "status": "NO_CARRIER_EVENTS", "is_stalled": False}

        sorted_events = sorted(carrier_events, key=lambda x: x.get("timestamp", 0))
        latest = sorted_events[-1]
        now = time.time()
        last_event_time = float(latest.get("timestamp", now))
        idle_duration_hours = round((now - last_event_time) / 3600.0, 1)

        is_delivered = latest.get("status") in ("DELIVERED", "COMPLETED")
        is_stalled = (not is_delivered) and ((now - last_event_time) >= self.stall_threshold_sec)

        is_late = False
        delay_hours = 0.0
        if expected_delivery_timestamp and now > expected_delivery_timestamp and not is_delivered:
            is_late = True
            delay_hours = round((now - expected_delivery_timestamp) / 3600.0, 1)

        risk_category = "NORMAL_TRANSIT"
        if is_delivered:
            risk_category = "FULFILLED_SUCCESS"
        elif is_stalled and is_late:
            risk_category = "CRITICAL_LOST_SHIPMENT_PROBABLE"
        elif is_stalled:
            risk_category = "WARNING_STALLED_IN_HUB"
        elif is_late:
            risk_category = "WARNING_CARRIER_DELAYED"

        return {
            "order_id": order_id,
            "current_status": latest.get("status", "IN_TRANSIT"),
            "risk_category": risk_category,
            "last_location": latest.get("location", "Transit Hub"),
            "idle_duration_hours": idle_duration_hours,
            "is_stalled": is_stalled,
            "is_past_expected_delivery": is_late,
            "delay_hours": delay_hours,
            "action_recommended": (
                "File automatic claim for full refund or replacement" if risk_category == "CRITICAL_LOST_SHIPMENT_PROBABLE"
                else ("File delay credit claim" if is_late else "Continue passive tracking monitoring")
            )
        }

    def assess_refund_eligibility(
        self,
        order_total_usd: float,
        shipment_evaluation: Dict[str, Any],
        is_perishable: bool = False
    ) -> Dict[str, Any]:
        """Calculates refund amount and claim eligibility based on merchant SLA terms."""
        risk = shipment_evaluation.get("risk_category")
        delay_hrs = shipment_evaluation.get("delay_hours", 0.0)

        eligible = False
        refund_amount = 0.0
        claim_type = "NONE"

        if risk == "CRITICAL_LOST_SHIPMENT_PROBABLE":
            eligible = True
            refund_amount = order_total_usd
            claim_type = "FULL_REFUND_LOST_GOODS"
        elif is_perishable and delay_hrs > 6.0: # Groceries/Instacart delay spoiled goods
            eligible = True
            refund_amount = order_total_usd
            claim_type = "FULL_REFUND_PERISHABLE_SPOILED"
        elif shipment_evaluation.get("is_past_expected_delivery"):
            eligible = True
            refund_amount = min(order_total_usd * 0.20, 25.0) # Standard shipping fee credit
            claim_type = "SHIPPING_DELAY_CREDIT"

        return {
            "claim_eligible": eligible,
            "claim_type": claim_type,
            "order_total_usd": round(order_total_usd, 2),
            "claimable_amount_usd": round(refund_amount, 2),
            "dispute_urgency": "HIGH" if claim_type.startswith("FULL_REFUND") else "LOW"
        }

    def generate_merchant_claim_payload(
        self,
        order_id: str,
        merchant_name: str,
        eligibility: Dict[str, Any],
        customer_account_id: str = "CUST-8812"
    ) -> Dict[str, Any]:
        """Formats structured API claim payload ready for submission to Shopify/Walmart merchant portals."""
        claim_id = "CLM-" + hashlib.sha256(f"{order_id}{merchant_name}{time.time()}".encode("utf-8")).hexdigest()[:12]
        return {
            "claim_id": claim_id,
            "merchant_name": merchant_name,
            "order_id": order_id,
            "customer_account_id": customer_account_id,
            "claim_type": eligibility.get("claim_type"),
            "requested_amount_usd": eligibility.get("claimable_amount_usd"),
            "filing_mode": "AUTONOMOUS_AGENT_MANDATE",
            "formal_letter": (
                f"Notice of Commerce Delivery SLA Breach - Order #{order_id}\n\n"
                f"To Customer Service Team at {merchant_name},\n\n"
                f"Our autonomous agent monitoring has confirmed that Order #{order_id} has exceeded guaranteed delivery thresholds "
                f"with status [{eligibility.get('claim_type')}].\n"
                f"We are exercising delegated mandate to request immediate credit of ${eligibility.get('claimable_amount_usd')} "
                f"to the original payment method.\n\n"
                f"Reference Claim ID: {claim_id}"
            )
        }
