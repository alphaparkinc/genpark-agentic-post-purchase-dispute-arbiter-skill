"""MCP Server for Agentic Post-Purchase Dispute Arbiter."""
import sys
import json
import time
from client import AgenticPostPurchaseDisputeArbiter

arbiter = AgenticPostPurchaseDisputeArbiter()

def handle_call_tool(params):
    name = params.get("name")
    args = params.get("arguments", {})
    if name != "arbitrate_post_purchase_dispute":
        raise ValueError(f"Unknown tool: {name}")

    action = args.get("action", "evaluate_shipment_status")
    if action == "evaluate_shipment_status":
        return arbiter.evaluate_shipment_status(
            order_id=args.get("order_id", "ORD-1"),
            carrier_events=args.get("carrier_events", []),
            expected_delivery_timestamp=args.get("expected_delivery_timestamp")
        )
    elif action == "assess_refund_eligibility":
        eval_res = arbiter.evaluate_shipment_status(
            order_id=args.get("order_id", "ORD-1"),
            carrier_events=args.get("carrier_events", []),
            expected_delivery_timestamp=args.get("expected_delivery_timestamp")
        )
        return arbiter.assess_refund_eligibility(
            order_total_usd=float(args.get("order_total_usd", 100.0)),
            shipment_evaluation=eval_res
        )
    elif action == "generate_merchant_claim_payload":
        eval_res = arbiter.evaluate_shipment_status(
            order_id=args.get("order_id", "ORD-1"),
            carrier_events=args.get("carrier_events", []),
            expected_delivery_timestamp=args.get("expected_delivery_timestamp")
        )
        elig = arbiter.assess_refund_eligibility(float(args.get("order_total_usd", 100.0)), eval_res)
        return arbiter.generate_merchant_claim_payload(
            order_id=args.get("order_id", "ORD-1"),
            merchant_name="Merchant",
            eligibility=elig
        )
    else:
        raise ValueError(f"Invalid action: {action}")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("Running self-test...")
        now = time.time()
        events = [
            {"status": "PICKED_UP", "timestamp": now - 90*3600, "location": "Atlanta Hub"},
            {"status": "IN_TRANSIT", "timestamp": now - 85*3600, "location": "Memphis Sorting"}
        ]
        status = arbiter.evaluate_shipment_status("ORD-TEST", events, expected_delivery_timestamp=now - 24*3600)
        assert status["is_stalled"] is True
        elig = arbiter.assess_refund_eligibility(150.0, status)
        assert elig["claim_eligible"] is True
        print("Self-test PASSED!")
        sys.exit(0)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            msg_id = req.get("id")
            method = req.get("method")
            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": "AgenticPostPurchaseDisputeArbiter", "version": "1.0.0"},
                        "capabilities": {"tools": {}}
                    }
                }
            elif method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "tools": [{
                            "name": "arbitrate_post_purchase_dispute",
                            "description": "Post-checkout telemetry and dispute arbitration: track multi-carrier shipping updates, detect delay anomalies, assess refund eligibility, and generate merchant dispute claim payloads.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "action": {"type": "string", "enum": ["evaluate_shipment_status", "assess_refund_eligibility", "generate_merchant_claim_payload"]},
                                    "order_id": {"type": "string"},
                                    "carrier_events": {"type": "array"},
                                    "expected_delivery_timestamp": {"type": "number"},
                                    "order_total_usd": {"type": "number"},
                                    "claim_reason": {"type": "string"}
                                },
                                "required": ["action"]
                            }
                        }]
                    }
                }
            elif method == "tools/call":
                res = handle_call_tool(req.get("params", {}))
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}
                }
            else:
                resp = {"jsonrpc": "2.0", "id": msg_id, "result": {}}
            print(json.dumps(resp), flush=True)
        except Exception as e:
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(e)}}
            print(json.dumps(err_resp), flush=True)

if __name__ == "__main__":
    main()
