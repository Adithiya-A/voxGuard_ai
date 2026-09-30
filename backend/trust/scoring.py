from typing import Dict, Any, Optional
from backend.config import settings

class TrustEngine:
    def __init__(self):
        self.weights = {
            "voice_synthetic": settings.WEIGHT_VOICE_SYNTHETIC,
            "speaker_anomaly": settings.WEIGHT_SPEAKER_ANOMALY,
            "prosody_anomaly": settings.WEIGHT_PROSODY_ANOMALY,
            "conversation_risk": settings.WEIGHT_CONVERSATION_RISK,
            "caller_risk": settings.WEIGHT_CALLER_RISK,
            "transaction_risk": settings.WEIGHT_TRANSACTION_RISK,
        }

    def update_weights(self, new_weights: Dict[str, float]):
        total = sum(new_weights.values())
        if abs(total - 1.0) > 0.05:
            # Normalize if slightly off
            self.weights = {k: v / total for k, v in new_weights.items()}
        else:
            self.weights = new_weights

    def calculate_trust(
        self,
        voice_synthetic_risk: float,
        speaker_similarity: float,
        prosody_anomaly: float,
        conversation_risk: float,
        caller_risk: float,
        transaction_risk: float,
        claimed_identity_match: bool = True
    ) -> Dict[str, Any]:
        """
        Calculates dynamic multi-signal trust score and preventive recommendation.
        Note the core security differentiator:
        If speaker_similarity is HIGH (claimed identity matches voice) BUT voice_synthetic_risk is HIGH,
        this is the classic AI Voice Clone Impersonation attack! We penalize heavily.
        """
        # If claimed identity matches registered voice, speaker anomaly is 100 - similarity
        # BUT if voice is synthetic and similarity is high, the speaker anomaly is boosted
        raw_speaker_anomaly = max(0.0, 100.0 - speaker_similarity)
        if voice_synthetic_risk > 70 and speaker_similarity > 80:
            # High similarity + high synthetic probability = deliberate clone attack
            effective_speaker_anomaly = max(raw_speaker_anomaly, 85.0)
        else:
            effective_speaker_anomaly = raw_speaker_anomaly

        weighted_risk = (
            self.weights["voice_synthetic"] * voice_synthetic_risk +
            self.weights["speaker_anomaly"] * effective_speaker_anomaly +
            self.weights["prosody_anomaly"] * prosody_anomaly +
            self.weights["conversation_risk"] * conversation_risk +
            self.weights["caller_risk"] * caller_risk +
            self.weights["transaction_risk"] * transaction_risk
        )

        trust_score = int(round(max(0.0, min(100.0, 100.0 - weighted_risk))))

        # Determine Risk Level and Recommended Action
        if trust_score >= settings.THRESHOLD_SAFE:
            risk_level = "SAFE"
            action = "ALLOW"
            action_label = "Verified Voice - Call Permitted"
        elif trust_score >= settings.THRESHOLD_CAUTION:
            risk_level = "WARNING"
            action = "WARN"
            action_label = "Suspicious Characteristics - Advisory Alert"
        elif trust_score >= settings.THRESHOLD_HIGH_RISK:
            risk_level = "HIGH"
            action = "REQUIRE_MFA"
            action_label = "Secondary Out-of-Band MFA Required"
        else:
            risk_level = "CRITICAL"
            action = "BLOCK_TRANSACTION"
            action_label = "AI Voice Impersonation - Transaction Blocked"

        breakdown = {
            "voice_synthetic_risk": round(voice_synthetic_risk, 1),
            "speaker_anomaly": round(effective_speaker_anomaly, 1),
            "speaker_similarity": round(speaker_similarity, 1),
            "prosody_anomaly": round(prosody_anomaly, 1),
            "conversation_risk": round(conversation_risk, 1),
            "caller_risk": round(caller_risk, 1),
            "transaction_risk": round(transaction_risk, 1),
            "weighted_risk": round(weighted_risk, 1)
        }

        contributions = {
            "voice": round(self.weights["voice_synthetic"] * voice_synthetic_risk, 1),
            "speaker": round(self.weights["speaker_anomaly"] * effective_speaker_anomaly, 1),
            "prosody": round(self.weights["prosody_anomaly"] * prosody_anomaly, 1),
            "conversation": round(self.weights["conversation_risk"] * conversation_risk, 1),
            "caller": round(self.weights["caller_risk"] * caller_risk, 1),
            "transaction": round(self.weights["transaction_risk"] * transaction_risk, 1),
        }

        return {
            "trust_score": trust_score,
            "risk_level": risk_level,
            "recommended_action": action,
            "action_label": action_label,
            "breakdown": breakdown,
            "contributions": contributions,
            "weights": self.weights
        }

    def fuse_live_signals(
        self,
        aasist: Optional[Dict[str, Any]] = None,
        ecapa: Optional[Dict[str, Any]] = None,
        prosody: Optional[Dict[str, Any]] = None,
        gemini: Optional[Dict[str, Any]] = None,
        caller_context: Optional[Dict[str, Any]] = None,
        transaction_context: Optional[Dict[str, Any]] = None,
        possible_voice_clone: bool = False,
        speech_detected: bool = True,
    ) -> Dict[str, Any]:
        """
        Deterministic fusion. Gemini is evidence only and cannot output BLOCK.
        INCONCLUSIVE / missing signals are excluded (weights renormalized).
        """
        aasist = aasist or {}
        ecapa = ecapa or {}
        prosody = prosody or {}
        gemini = gemini or {}
        caller_context = caller_context or {}
        transaction_context = transaction_context or {}

        aasist_ok = aasist.get("status") == "OK" and aasist.get("spoof_probability") is not None
        ecapa_ok = ecapa.get("status") in ("MATCH", "MISMATCH")
        gemini_ok = gemini.get("status") in ("OK", None) and (
            gemini.get("social_engineering_risk") is not None or gemini.get("risk_score") is not None
        ) and gemini.get("status") not in ("EMPTY_TRANSCRIPT", "GEMINI_UNAVAILABLE")
        if gemini.get("status") == "GEMINI_UNAVAILABLE" and gemini.get("social_engineering_risk") is not None:
            gemini_ok = True
        caller_ok = caller_context.get("caller_risk") is not None
        txn_ok = transaction_context.get("transaction_risk") is not None
        prosody_ok = True

        voice_risk = float(aasist.get("spoof_probability", 0.0) * 100.0) if aasist_ok else None
        speaker_sim = float(ecapa.get("similarity_pct", 50.0)) if ecapa_ok else None
        if ecapa_ok and ecapa.get("status") == "MISMATCH":
            speaker_sim = min(float(speaker_sim or 0.0), 50.0)
        prosody_risk = float(prosody.get("behavior_anomaly", 15.0) or 0.0)
        conversation_risk = float(gemini.get("risk_score") or gemini.get("social_engineering_risk") or 0.0) if gemini_ok else None
        caller_risk = float(caller_context["caller_risk"]) if caller_ok else None
        txn_risk = float(transaction_context["transaction_risk"]) if txn_ok else None

        if possible_voice_clone:
            result = self.calculate_trust(
                voice_synthetic_risk=voice_risk if voice_risk is not None else 90.0,
                speaker_similarity=speaker_sim if speaker_sim is not None else 90.0,
                prosody_anomaly=prosody_risk,
                conversation_risk=conversation_risk if conversation_risk is not None else 0.0,
                caller_risk=caller_risk if caller_risk is not None else 0.0,
                transaction_risk=txn_risk if txn_risk is not None else 0.0,
            )
            result["trust_score"] = min(result["trust_score"], 9)
            result["risk_level"] = "CRITICAL"
            result["recommended_action"] = "BLOCK"
            result["action_label"] = "Voice clone paradox: synthetic speech with matching enrolled identity"
            result["possible_voice_clone"] = True
            result["signal_status"] = {
                "aasist": "available" if aasist_ok else "inconclusive",
                "ecapa": "available" if ecapa_ok else "inconclusive",
                "prosody": "available",
                "conversation": "available" if gemini_ok else "not_ready",
                "caller": "available" if caller_ok else "not_provided",
                "transaction": "available" if txn_ok else "not_provided",
            }
            return result

        if not speech_detected and not aasist_ok:
            return {
                "trust_score": 85,
                "risk_level": "LOW",
                "recommended_action": "ALLOW",
                "action_label": "Silence / ambient floor (provisional)",
                "possible_voice_clone": False,
                "breakdown": {},
                "contributions": {},
                "weights": self.weights,
                "signal_status": {
                    "aasist": "inconclusive",
                    "ecapa": "inconclusive",
                    "prosody": "available",
                    "conversation": "not_ready",
                    "caller": "available" if caller_ok else "not_provided",
                    "transaction": "available" if txn_ok else "not_provided",
                },
            }

        parts = []
        if aasist_ok and voice_risk is not None:
            parts.append(("voice_synthetic", self.weights["voice_synthetic"], voice_risk))
        if ecapa_ok and speaker_sim is not None:
            speaker_anomaly = max(0.0, 100.0 - speaker_sim)
            parts.append(("speaker_anomaly", self.weights["speaker_anomaly"], speaker_anomaly))
        if prosody_ok:
            parts.append(("prosody_anomaly", self.weights["prosody_anomaly"], prosody_risk))
        if gemini_ok and conversation_risk is not None:
            parts.append(("conversation_risk", self.weights["conversation_risk"], conversation_risk))
        if caller_ok and caller_risk is not None:
            parts.append(("caller_risk", self.weights["caller_risk"], caller_risk))
        if txn_ok and txn_risk is not None:
            parts.append(("transaction_risk", self.weights["transaction_risk"], txn_risk))

        if not parts:
            weighted_risk = 15.0
            used_weights = dict(self.weights)
        else:
            total_w = sum(w for _, w, _ in parts) or 1.0
            weighted_risk = sum((w / total_w) * val for _, w, val in parts)
            used_weights = {name: (w / total_w) for name, w, _ in parts}

        trust_score = int(round(max(0.0, min(100.0, 100.0 - weighted_risk))))

        if trust_score >= settings.THRESHOLD_SAFE:
            risk_level, action, label = "LOW", "ALLOW", "Verified voice — call permitted"
        elif trust_score >= settings.THRESHOLD_CAUTION:
            risk_level, action, label = "MEDIUM", "WARN", "Suspicious characteristics — advisory alert"
        elif trust_score >= settings.THRESHOLD_HIGH_RISK:
            risk_level, action, label = "HIGH", "MFA", "Secondary out-of-band MFA required"
        else:
            risk_level, action, label = "CRITICAL", "BLOCK", "High combined risk — block transaction"

        if gemini_ok and gemini.get("credential_request") and action == "ALLOW":
            action = "MFA"
            risk_level = "HIGH"
        if gemini_ok and gemini.get("financial_request") and gemini.get("authority_impersonation") and trust_score < 70:
            if action in ("ALLOW", "WARN"):
                action = "INDEPENDENT_CALLBACK"
                risk_level = "HIGH"

        return {
            "trust_score": trust_score,
            "risk_level": risk_level,
            "recommended_action": action,
            "action_label": label,
            "possible_voice_clone": False,
            "breakdown": {
                "voice_synthetic_risk": round(voice_risk, 1) if voice_risk is not None else None,
                "speaker_similarity": round(speaker_sim, 1) if speaker_sim is not None else None,
                "prosody_anomaly": round(prosody_risk, 1),
                "conversation_risk": round(conversation_risk, 1) if conversation_risk is not None else None,
                "caller_risk": round(caller_risk, 1) if caller_risk is not None else None,
                "transaction_risk": round(txn_risk, 1) if txn_risk is not None else None,
                "weighted_risk": round(weighted_risk, 1),
            },
            "contributions": {name: round((w / (sum(x[1] for x in parts) or 1.0)) * val, 1) for name, w, val in parts} if parts else {},
            "weights": used_weights,
            "signal_status": {
                "aasist": "available" if aasist_ok else "inconclusive",
                "ecapa": "available" if ecapa_ok else "inconclusive",
                "prosody": "available",
                "conversation": "available" if gemini_ok else "not_ready",
                "caller": "available" if caller_ok else "not_provided",
                "transaction": "available" if txn_ok else "not_provided",
            },
        }

trust_engine = TrustEngine()
