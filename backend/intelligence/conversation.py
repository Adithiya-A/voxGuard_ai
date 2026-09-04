import os
import json
from typing import Dict, Any
from backend.config import settings

class ConversationIntelligence:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")

    def analyze_transcript(self, transcript: str) -> Dict[str, Any]:
        """
        Analyzes conversation transcript for semantic indicators of Business Email Compromise (BEC)
        and voice social engineering.
        Uses Gemini if API key is provided; otherwise falls back to local heuristic NLP rules.
        """
        if self.api_key and len(transcript) > 10:
            try:
                # Try Google GenAI
                from google import genai
                client = genai.Client(api_key=self.api_key)
                prompt = f"""
                You are VoxGuard AI's real-time conversational threat analyzer.
                Analyze this phone call transcript snippet:
                "{transcript}"

                Return ONLY a valid JSON object matching this schema:
                {{
                  "intent": "Short summary of caller objective",
                  "authority_impersonation": boolean,
                  "urgency": boolean,
                  "financial_request": boolean,
                  "confidentiality_pressure": boolean,
                  "psychological_pressure": boolean,
                  "social_engineering_risk": integer 0-100,
                  "detected_signals": ["signal 1", "signal 2"],
                  "summary": "Forensic semantic explanation"
                }}
                """
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                text = response.text.strip()
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()
                data = json.loads(text)
                data["engine"] = "Gemini-2.5-Flash (Live NLP)"
                return data
            except Exception:
                pass # Fallback to local heuristic

        # Robust Heuristic Rule Fallback
        lower = transcript.lower()
        has_auth = any(w in lower for w in ["cfo", "chief financial officer", "executive", "arun", "director", "helpdesk", "it security"])
        has_fin = any(w in lower for w in ["transfer", "₹", "lakh", "crore", "account", "rtgs", "fund", "money", "payment", "wire"])
        has_urg = any(w in lower for w in ["immediately", "now", "urgent", "emergency", "hurry", "right now", "boarding", "flight", "expiring"])
        has_conf = any(w in lower for w in ["confidential", "secret", "don't tell", "private", "nobody", "acquisition", "strictly"])
        has_otp = any(w in lower for w in ["code", "otp", "password", "passcode", "verify", "pin", "sms"])

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

        return {
            "intent": intent,
            "authority_impersonation": has_auth,
            "urgency": has_urg,
            "financial_request": has_fin,
            "confidentiality_pressure": has_conf,
            "psychological_pressure": has_urg or has_conf,
            "social_engineering_risk": risk,
            "detected_signals": signals,
            "summary": f"Detected {len(signals)} social engineering markers in conversational stream." if signals else "No coercive conversational indicators detected.",
            "engine": "VoxGuard Heuristic NLP Engine (Rule-based Fallback)"
        }

conversation_intelligence = ConversationIntelligence()
