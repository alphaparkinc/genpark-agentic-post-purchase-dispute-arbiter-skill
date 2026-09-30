"""Example usage for AgenticPostPurchaseDisputeArbiter."""
import json
import time
from client import AgenticPostPurchaseDisputeArbiter

def main():
    print("=== Agentic Post-Purchase Operations & Delivery Dispute Arbiter Demo ===")
    arbiter = AgenticPostPurchaseDisputeArbiter(stall_threshold_hours=48.0)

    # 1. Simulate stalled package timeline (Meta Muse consumer agent tracking order)
    now = time.time()
    carrier_timeline = [
        {"timestamp": now - 96*3600, "status": "PICKED_UP", "location": "Dallas Sort Facility"},
        {"timestamp": now - 75*3600, "status": "IN_TRANSIT", "location": "Kansas City Hub"}, # idle for 75h
    ]
    expected_eta = now - 20*3600 # Promised yesterday

    print("\n--- 1. Evaluating Carrier Tracking Telemetry ---")
    eval_res = arbiter.evaluate_shipment_status("ORD-SHOPIFY-7712", carrier_timeline, expected_delivery_timestamp=expected_eta)
    print(json.dumps(eval_res, indent=2))

    # 2. Assess refund claim eligibility
    print("\n--- 2. Assessing SLA Refund Eligibility ---")
    elig = arbiter.assess_refund_eligibility(order_total_usd=185.0, shipment_evaluation=eval_res)
    print(json.dumps(elig, indent=2))

    # 3. Generate formal merchant dispute claim payload
    print("\n--- 3. Formulating Autonomous Merchant Claim Submission ---")
    claim = arbiter.generate_merchant_claim_payload("ORD-SHOPIFY-7712", "Tokyo Streetwear Direct", elig)
    print(claim["formal_letter"])

if __name__ == "__main__":
    main()
