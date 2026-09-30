from typing import Dict, Any, List

class PolicyMatrix:
    def __init__(self):
        self.rules = [
            {
                "id": "POL-001",
                "name": "High-Value Transfer with Synthetic Voice",
                "condition": "voice_synthetic_risk > 75 and transaction_amount > 1000000",
                "action": "BLOCK_TRANSACTION",
                "severity": "CRITICAL",
                "enabled": True
            },
            {
                "id": "POL-002",
                "name": "CFO Impersonation via Unregistered Trunk",
                "condition": "claimed_identity == 'CFO' and not known_contact and voice_synthetic_risk > 60",
                "action": "BLOCK_TRANSACTION",
                "severity": "CRITICAL",
                "enabled": True
            },
            {
                "id": "POL-003",
                "name": "Coercive BEC Urgency with Anomaly",
                "condition": "conversation_risk > 80 and prosody_anomaly > 65",
                "action": "REQUIRE_MFA",
                "severity": "HIGH",
                "enabled": True
            },
            {
                "id": "POL-004",
                "name": "New Beneficiary Step-Up Verification",
                "condition": "new_beneficiary and trust_score < 70",
                "action": "INDEPENDENT_CALLBACK",
                "severity": "HIGH",
                "enabled": True
            }
        ]

    def evaluate_policies(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        triggered = []
        for r in self.rules:
            if not r["enabled"]:
                continue
            # Safe evaluation against context keys
            try:
                if eval(r["condition"], {}, context):
                    triggered.append(r)
            except Exception:
                pass
        return triggered

policy_matrix = PolicyMatrix()
