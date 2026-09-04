from typing import Dict, Any
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

trust_engine = TrustEngine()
