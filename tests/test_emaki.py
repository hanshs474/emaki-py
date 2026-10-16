import os
import unittest

import emaki


def fake(calls, polls, submit_reply=(200, {"success": True, "data": {"id": "v1", "status": "generating"}})):
    polls = list(polls)

    def t(method, url, body, headers):
        calls.append((method, url, body, headers))
        if url.endswith("/api/video/ai"):
            return submit_reply
        if url.endswith("/api/video/status"):
            return 200, {"success": True, "data": polls.pop(0)}
        return 200, {"code": 0, "data": {"remainingCredits": 42, "hasPurchasedCredits": False}}

    return t


class EmakiTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("EMAKI_API_KEY", None)

    def test_validates(self):
        with self.assertRaises(ValueError):
            emaki.submit("  ", api_key="sk-x")

    def test_needs_a_key(self):
        with self.assertRaises(emaki.AuthError):
            emaki.generate_video("x")

    def test_video_polls_until_completed(self):
        calls = []
        polls = [
            {"id": "v1", "status": "generating"},
            {"id": "v1", "status": "completed", "videoUrl": "https://cdn/v.mp4"},
        ]
        url = emaki.generate_video("a boat", api_key="sk-abc", duration=5, resolution="720p", poll_every=0, base_url="https://t", transport=fake(calls, polls))
        self.assertEqual(url, "https://cdn/v.mp4")
        self.assertEqual(calls[0][1], "https://t/api/video/ai")
        self.assertEqual(calls[0][2], {"prompt": "a boat", "model": "seedance_2_5", "parameters": {"duration": 5, "resolution": "720p"}})
        self.assertEqual(calls[0][3], {"Authorization": "Bearer sk-abc"})
        self.assertEqual(calls[1][2], {"videoId": "v1"})
        self.assertEqual(len(calls), 3)

    def test_image_default_model(self):
        calls = []
        polls = [{"id": "v1", "status": "completed", "videoUrl": "https://cdn/i.png"}]
        url = emaki.generate_image("x", api_key="sk", aspect_ratio="1:1", poll_every=0, transport=fake(calls, polls))
        self.assertEqual(url, "https://cdn/i.png")
        self.assertEqual(calls[0][2]["model"], "nano_banana_2_lite")
        self.assertEqual(calls[0][2]["parameters"], {"aspect_ratio": "1:1"})

    def test_failed_run(self):
        with self.assertRaises(emaki.GenerationFailed) as cm:
            emaki.generate_video("x", api_key="sk", poll_every=0, transport=fake([], [{"status": "failed", "failureCode": "provider_error"}]))
        self.assertEqual(cm.exception.code, "provider_error")

    def test_error_mapping(self):
        cases = [
            ((401, {"error": "Invalid API key. Create one at https://emaki.ai/settings/apikeys"}), emaki.AuthError),
            ((402, {"error": "Insufficient credits"}), emaki.QuotaError),
            ((403, {"error": "purchase required"}), emaki.PlanError),
            ((409, {"error": "Video generation is already in progress"}), emaki.BusyError),
            ((429, {"error": "slow down", "code": "content_cooldown"}), emaki.RejectedError),
            ((400, {"error": "blocked", "code": "content_blocked"}), emaki.RejectedError),
        ]
        for reply, exc in cases:
            with self.assertRaises(exc):
                emaki.submit("x", api_key="sk", transport=fake([], [], reply))
        with self.assertRaises(emaki.EmakiError) as cm:
            emaki.submit("x", api_key="sk", transport=fake([], [], (400, {"error": "duration must be 4-30"})))
        self.assertIs(type(cm.exception), emaki.EmakiError)
        self.assertIn("duration", str(cm.exception))

    def test_credits(self):
        self.assertEqual(emaki.credits(api_key="sk", transport=fake([], [])), 42)

        def bad(method, url, body, headers):
            return 200, {"code": -1, "message": "no auth, please sign in"}

        with self.assertRaises(emaki.AuthError):
            emaki.credits(api_key="sk", transport=bad)


if __name__ == "__main__":
    unittest.main()
