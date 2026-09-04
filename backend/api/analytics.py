from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

@router.get("")
def get_analytics() -> Dict[str, Any]:
    return {
        "kpis": {
            "active_calls": 3,
            "calls_analyzed_today": 1284,
            "threats_detected": 14,
            "transactions_protected_amount": "₹1,42,50,000",
            "critical_incidents": 2,
            "system_health": "OPTIMAL_ZERO_LATENCY"
        },
        "model_performance": {
            "label": "Prototype / Demonstration Benchmark Metrics",
            "precision": 98.4,
            "recall": 97.1,
            "f1_score": 97.7,
            "false_positive_rate": 0.8,
            "average_latency_ms": 142,
            "tested_samples": "12,400 Synthetic vs 8,900 Organic Telephony Chunks"
        },
        "threat_types": [
            {"name": "Neural Clone (ElevenLabs)", "count": 48, "percentage": 42},
            {"name": "Diffusion Vocoder Glottal Spoof", "count": 27, "percentage": 24},
            {"name": "WaveNet-XL Zero-Shot", "count": 21, "percentage": 18},
            {"name": "VALL-E 2 Sub-Packet Splicing", "count": 12, "percentage": 10},
            {"name": "Coercive Social Eng / Human Impersonation", "count": 7, "percentage": 6}
        ],
        "score_distribution": [
            {"range": "90–100 (Safe)", "count": 942, "color": "#10B981"},
            {"range": "60–89 (Advisory)", "count": 218, "color": "#F59E0B"},
            {"range": "30–59 (High Risk)", "count": 86, "color": "#F97316"},
            {"range": "0–29 (Critical)", "count": 38, "color": "#EF4444"}
        ],
        "detection_trend_7d": [
            {"day": "Mon", "analyzed": 1120, "threats": 8, "blocked": 6},
            {"day": "Tue", "analyzed": 1250, "threats": 12, "blocked": 10},
            {"day": "Wed", "analyzed": 1180, "threats": 9, "blocked": 7},
            {"day": "Thu", "analyzed": 1340, "threats": 15, "blocked": 14},
            {"day": "Fri", "analyzed": 1490, "threats": 18, "blocked": 16},
            {"day": "Sat", "analyzed": 850, "threats": 4, "blocked": 4},
            {"day": "Sun", "analyzed": 920, "threats": 7, "blocked": 5}
        ]
    }
