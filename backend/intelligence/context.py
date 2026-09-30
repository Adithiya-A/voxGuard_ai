from typing import Any, Dict, Optional


def empty_session_context() -> Dict[str, Any]:
    return {
        "caller_number": None,
        "claimed_identity": None,
        "known_contact": None,
        "contact_history": None,
        "beneficiary": None,
        "transaction_amount": None,
        "transaction_currency": None,
        "transaction_type": None,
        "source": None,
        "label": None,
    }


class ContextEngine:
    def merge_session_context(
        self,
        existing: Optional[Dict[str, Any]],
        updates: Optional[Dict[str, Any]],
        source: str = "DEMO_CONTEXT",
    ) -> Dict[str, Any]:
        ctx = dict(existing or empty_session_context())
        for key in empty_session_context().keys():
            if updates and key in updates and updates[key] is not None:
                ctx[key] = updates[key]
        ctx["source"] = source
        ctx["label"] = "DEMO_CONTEXT" if source == "DEMO_CONTEXT" else "LIVE_CONTEXT"
        return ctx

    def evaluate_caller(
        self,
        caller_number: Optional[str] = None,
        known_contact: Optional[bool] = None,
        registered_device: Optional[bool] = None,
        previous_interaction: Optional[bool] = None,
        claimed_identity: Optional[str] = None,
        contact_history: Optional[Any] = None,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        provided = any(v is not None for v in (
            caller_number, known_contact, registered_device, previous_interaction, claimed_identity
        ))
        if not provided:
            return {
                "caller_number": None,
                "claimed_identity": claimed_identity,
                "telephony_trunk": None,
                "known_contact": None,
                "registered_device": None,
                "previous_interaction": previous_interaction,
                "contact_history": contact_history,
                "caller_reputation": "NOT_PROVIDED",
                "caller_risk": None,
                "status": "NOT_PROVIDED",
                "source": source,
                "note": "No caller context supplied. Browser microphone is not telephony CLI.",
            }

        known = bool(known_contact)
        registered = bool(registered_device) if registered_device is not None else False
        previous = bool(previous_interaction) if previous_interaction is not None else False
        risk = 15
        if not known:
            risk += 35
        if not registered:
            risk += 25
        if not previous:
            risk += 15
        risk = min(100, max(5, risk))
        reputation = (
            "High Confidence" if risk < 30
            else ("Moderate" if risk < 60 else "Low Confidence / Untrusted Trunk")
        )
        return {
            "caller_number": caller_number,
            "claimed_identity": claimed_identity,
            "telephony_trunk": None,
            "known_contact": known,
            "registered_device": registered,
            "previous_interaction": previous,
            "contact_history": contact_history,
            "caller_reputation": reputation,
            "caller_risk": risk,
            "status": "OK",
            "source": source or "DEMO_CONTEXT",
            "label": source or "DEMO_CONTEXT",
        }

    def evaluate_transaction(
        self,
        amount: Optional[float] = None,
        currency: Optional[str] = None,
        new_beneficiary: Optional[bool] = None,
        beneficiary_name: Optional[str] = None,
        previous_similar_transfer: Optional[bool] = None,
        transaction_type: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        if amount is None and not beneficiary_name and not transaction_type:
            return {
                "requested_amount": None,
                "currency": None,
                "formatted_amount": None,
                "new_beneficiary": None,
                "beneficiary_name": None,
                "transaction_type": None,
                "previous_similar_transfer": None,
                "transaction_risk": None,
                "status": "NOT_PROVIDED",
                "source": source,
                "note": "No transaction context supplied for this session.",
            }

        amt = float(amount or 0.0)
        is_new = True if new_beneficiary is None else bool(new_beneficiary)
        prev = bool(previous_similar_transfer)
        risk = 10
        if amt >= 1000000:
            risk += 40
        elif amt >= 100000:
            risk += 20
        if is_new:
            risk += 35
        if not prev:
            risk += 15
        risk = min(99, max(5, risk))
        cur = currency or "INR"
        formatted = f"₹{amt:,.0f}" if cur == "INR" else f"{amt:,.0f} {cur}"
        return {
            "requested_amount": amt,
            "currency": cur,
            "formatted_amount": formatted,
            "new_beneficiary": is_new,
            "beneficiary_name": beneficiary_name,
            "transaction_type": transaction_type,
            "previous_similar_transfer": prev,
            "transaction_risk": risk,
            "status": "OK",
            "source": source or "DEMO_CONTEXT",
            "label": source or "DEMO_CONTEXT",
        }


context_engine = ContextEngine()
