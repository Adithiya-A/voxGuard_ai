import json
import logging
from typing import Any, Dict, Optional

from backend.config import settings

logger = logging.getLogger("voxguard.gemini")

HIGH_RISK_PHRASES = (
    "otp", "one-time", "password", "passcode", "pin", "cvv",
    "transfer", "wire", "rtgs", "immediately", "emergency",
    "don't tell", "do not tell", "confidential", "secret",
    "account number", "beneficiary",
)


class ConversationIntelligence:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY or ""
        self.model_name = settings.GEMINI_MODEL or "gemini-2.5-flash"

    def _empty(self, status: str, engine: str, extra: Dict[str, Any] = None) -> Dict[str, Any]:
        payload = {
            "risk_score": 0,
            "intent": "",
            "social_engineering": False,
            "authority_impersonation": False,
            "financial_request": False,
            "credential_request": False,
            "urgency": False,
            "confidentiality_pressure": False,
            "psychological_pressure": False,
            "manipulation_indicators": [],
            "reasoning": "",
            "recommended_action": "",
            "social_engineering_risk": 0,
            "detected_signals": [],
            "summary": "",
            "engine": engine,
            "status": status,
            "available": status == "OK",
        }
        if extra:
            payload.update(extra)
        return payload

    def contains_high_risk_phrase(self, transcript: str) -> bool:
        lower = (transcript or "").lower()
        return any(p in lower for p in HIGH_RISK_PHRASES)

    def analyze_transcript(self, transcript: str) -> Dict[str, Any]:
        """
        Semantic / conversational risk only. Does not decide if a voice is synthetic.
        Gemini never authoritatively emits BLOCK; that is the trust engine's job.
        """
        text = (transcript or "").strip()
        if len(text) < 3:
            return self._empty("EMPTY_TRANSCRIPT", "none")

        if self.api_key and len(text) > 10:
            gemini = self._analyze_gemini(text)
            if gemini is not None:
                return gemini

        return self._analyze_heuristic(text)

    def _analyze_gemini(self, transcript: str) -> Optional[Dict[str, Any]]:
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            prompt = f"""You are VoxGuard AI conversation intelligence.
Analyze ONLY the semantic content of this live call transcript.
Do NOT judge whether the voice is AI-generated or cloned. Anti-spoofing is handled elsewhere.

Transcript:
\"\"\"{transcript}\"\"\"

Return ONLY valid JSON:
{{
  "risk_score": 0,
  "intent": "",
  "social_engineering": false,
  "authority_impersonation": false,
  "financial_request": false,
  "credential_request": false,
  "urgency": false,
  "confidentiality_pressure": false,
  "psychological_pressure": false,
  "manipulation_indicators": [],
  "reasoning": "",
  "recommended_action": ""
}}
recommended_action must be one of: ALLOW, WARN, MFA, INDEPENDENT_CALLBACK, MONITOR.
Never output BLOCK. Never claim the voice is synthetic.
"""
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            raw = (response.text or "").strip()
            if "```json" in raw:
                raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
            elif "```" in raw:
                raw = raw.split("```", 1)[1].split("```", 1)[0].strip()
            data = json.loads(raw)
            risk = int(max(0, min(100, int(data.get("risk_score", 0)))))
            action = str(data.get("recommended_action") or "MONITOR").upper()
            if action in ("BLOCK", "BLOCK_TRANSACTION"):
                action = "MFA"
            signals = list(data.get("manipulation_indicators") or [])
            return {
                "risk_score": risk,
                "intent": data.get("intent") or "",
                "social_engineering": bool(data.get("social_engineering")),
                "authority_impersonation": bool(data.get("authority_impersonation")),
                "financial_request": bool(data.get("financial_request")),
                "credential_request": bool(data.get("credential_request")),
                "urgency": bool(data.get("urgency")),
                "confidentiality_pressure": bool(data.get("confidentiality_pressure")),
                "psychological_pressure": bool(data.get("psychological_pressure")),
                "manipulation_indicators": signals,
                "reasoning": data.get("reasoning") or data.get("summary") or "",
                "recommended_action": action,
                "social_engineering_risk": risk,
                "detected_signals": signals,
                "summary": data.get("reasoning") or data.get("summary") or "",
                "engine": f"Gemini ({self.model_name})",
                "status": "OK",
                "available": True,
            }
        except Exception as e:
            logger.warning(f"[GEMINI] API failure, using heuristic: {e}")
            fallback = self._analyze_heuristic(transcript)
            fallback["status"] = "GEMINI_UNAVAILABLE"
            fallback["gemini_error"] = str(e)
            fallback["engine"] = "VoxGuard Heuristic NLP Engine (Gemini unavailable)"
            return fallback

    def _analyze_heuristic(self, transcript: str) -> Dict[str, Any]:
        lower = transcript.lower()
        has_auth = any(w in lower for w in [
            "cfo", "chief financial officer", "executive", "arun", "director",
            "helpdesk", "it security", "ceo", "manager",
        ])
        has_fin = any(w in lower for w in [
            "transfer", "₹", "lakh", "crore", "account", "rtgs", "fund",
            "money", "payment", "wire", "beneficiary",
        ])
        has_urg = any(w in lower for w in [
            "immediately", "now", "urgent", "emergency", "hurry", "right now",
            "boarding", "flight", "expiring",
        ])
        has_conf = any(w in lower for w in [
            "confidential", "secret", "don't tell", "do not tell", "private",
            "nobody", "acquisition", "strictly",
        ])
        has_otp = any(w in lower for w in [
            "code", "otp", "password", "passcode", "verify", "pin", "sms", "cvv",
        ])

        signals = []
        risk = 10
        if has_auth:
            signals.append("Executive/Authority Hierarchy Claim")
            risk += 25
        if has_fin:
            signals.append("High-Value Capital Transfer Directive")
            risk += 30
        if has_urg:
            signals.append("Artificially Induced Operational Urgency")
            risk += 20
        if has_conf:
            signals.append("Isolation & Confidentiality Coercion")
            risk += 15
        if has_otp:
            signals.append("Out-of-band Credential Solicit")
            risk += 25
        risk = min(98, max(5, risk))

        intent = "Routine Business Dialogue"
        if has_fin and has_auth:
            intent = "Coercive Wire Transfer Hijack"
        elif has_otp or ("helpdesk" in lower):
            intent = "Credential Harvesting / SIM-Swap"
        elif has_urg:
            intent = "Urgent Administrative Request"

        recommended = "MONITOR"
        if has_otp:
            recommended = "MFA"
        elif has_fin and has_auth:
            recommended = "INDEPENDENT_CALLBACK"
        elif risk >= 60:
            recommended = "WARN"

        summary = (
            f"Detected {len(signals)} social engineering markers in conversational stream."
            if signals else "No coercive conversational indicators detected."
        )
        return {
            "risk_score": risk,
            "intent": intent,
            "social_engineering": bool(signals),
            "authority_impersonation": has_auth,
            "financial_request": has_fin,
            "credential_request": has_otp,
            "urgency": has_urg,
            "confidentiality_pressure": has_conf,
            "psychological_pressure": has_urg or has_conf,
            "manipulation_indicators": signals,
            "reasoning": summary,
            "recommended_action": recommended,
            "social_engineering_risk": risk,
            "detected_signals": signals,
            "summary": summary,
            "engine": "VoxGuard Heuristic NLP Engine (Rule-based Fallback)",
            "status": "OK" if not self.api_key else "OK",
            "available": True,
        }


conversation_intelligence = ConversationIntelligence()
