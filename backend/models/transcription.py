from typing import List, Dict, Any

class TranscriptionService:
    def __init__(self):
        self.model_name = "Whisper-Large-v3-Turbo"

    def transcribe_chunk(self, chunk_index: int, scenario: str = "clone") -> Dict[str, Any]:
        """
        Provides progressive streaming transcripts corresponding to the SIH scenario timeline.
        """
        if scenario == "clone":
            timeline = [
                {"timestamp": "00:02", "speaker": "Caller", "text": "Hello? Can you hear me clearly?", "flagged": False},
                {"timestamp": "00:06", "speaker": "Caller", "text": "Hi, this is Arun, the CFO. We have an emergency.", "flagged": True, "category": "Authority Impersonation"},
                {"timestamp": "00:11", "speaker": "Caller", "text": "I need you to transfer ₹25 lakh to the new vendor account immediately.", "flagged": True, "category": "Financial Request"},
                {"timestamp": "00:16", "speaker": "Caller", "text": "Don't discuss this with anyone right now because this acquisition is strictly confidential.", "flagged": True, "category": "Confidentiality Coercion"},
                {"timestamp": "00:20", "speaker": "Caller", "text": "I am boarding a flight now. Release the RTGS immediately or we lose the contract.", "flagged": True, "category": "Extreme Pressure"}
            ]
        elif scenario == "genuine":
            timeline = [
                {"timestamp": "00:02", "speaker": "Arun Sharma", "text": "Good afternoon, finance team. Checking in on the Q3 audit report.", "flagged": False},
                {"timestamp": "00:07", "speaker": "Arun Sharma", "text": "Please confirm the routine payroll batch was cleared per standard operating procedure.", "flagged": False},
                {"timestamp": "00:14", "speaker": "Arun Sharma", "text": "I'll review the summary at tomorrow's scheduled executive board meeting.", "flagged": False}
            ]
        else: # social_eng
            timeline = [
                {"timestamp": "00:03", "speaker": "Caller", "text": "Hey there, this is IT Security Helpdesk. We detected suspicious sign-ins on your portal.", "flagged": True, "category": "Authority Impersonation"},
                {"timestamp": "00:09", "speaker": "Caller", "text": "To prevent account lockout, I need you to confirm your one-time SMS verification passcode.", "flagged": True, "category": "Credential Harvesting"},
                {"timestamp": "00:16", "speaker": "Caller", "text": "Hurry up, your session token is expiring in 30 seconds!", "flagged": True, "category": "Urgency"}
            ]

        idx = min(chunk_index, len(timeline) - 1)
        current = timeline[idx]
        all_so_far = timeline[:idx + 1]

        return {
            "current_line": current,
            "transcript_history": all_so_far,
            "full_text": " ".join([t["text"] for t in all_so_far]),
            "model_version": self.model_name
        }

transcription_service = TranscriptionService()
