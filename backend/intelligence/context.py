from typing import Dict, Any

class ContextEngine:
    def evaluate_caller(
        self,
        caller_number: str = "Unknown Number",
        known_contact: bool = False,
        registered_device: bool = False,
        previous_interaction: bool = False
    ) -> Dict[str, Any]:
        """
        Calculates caller risk score based on telephony trunk provenance and device trust.
        """
        risk = 15
        if not known_contact:
            risk += 35
        if not registered_device:
            risk += 25
        if not previous_interaction:
            risk += 15

        risk = min(100, max(5, risk))
        
        reputation = "High Confidence" if risk < 30 else ("Moderate" if risk < 60 else "Low Confidence / Untrusted Trunk")

        return {
            "caller_number": caller_number,
            "telephony_trunk": "SIP-901 // 8kHz G.711u VoIP Ingress",
            "known_contact": known_contact,
            "registered_device": registered_device,
            "previous_interaction": previous_interaction,
            "caller_reputation": reputation,
            "caller_risk": risk,
            "carrier_attestation_shaken": "STIR/SHAKEN Level C (Gateway)",
            "geo_origin": "Frankfurt, DE (Proxy Relay)"
        }

    def evaluate_transaction(
        self,
        amount: float = 2500000.0,
        currency: str = "INR",
        new_beneficiary: bool = True,
        beneficiary_name: str = "Apex Horizon Global Logistics",
        previous_similar_transfer: bool = False
    ) -> Dict[str, Any]:
        """
        Calculates transaction risk score based on amount anomalies, beneficiary history, and velocity.
        """
        risk = 10
        # Amount sensitivity
        if amount >= 1000000:
            risk += 40
        elif amount >= 100000:
            risk += 20
        
        # New beneficiary
        if new_beneficiary:
            risk += 35
        
        # Historical anomaly
        if not previous_similar_transfer:
            risk += 15

        risk = min(99, max(5, risk))

        return {
            "requested_amount": amount,
            "currency": currency,
            "formatted_amount": f"₹{amount:,.0f}" if currency == "INR" else f"${amount:,.0f}",
            "new_beneficiary": new_beneficiary,
            "beneficiary_name": beneficiary_name,
            "beneficiary_account": "HDFC-****-9821",
            "previous_similar_transfer": previous_similar_transfer,
            "transaction_risk": risk,
            "anomaly_factor": "4.8x above 90-day rolling baseline for desk operator"
        }

context_engine = ContextEngine()
