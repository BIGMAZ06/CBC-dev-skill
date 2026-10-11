"""Offline tests for CBC model catalog/probe; no network or API calls."""
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / ".opencode" / "scripts" / "cbc_model_pool.py"
spec = importlib.util.spec_from_file_location("cbc_model_pool", SCRIPT)
pool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pool)


class Result:
    def __init__(self, code=0, out="CBC_PROBE_OK\n", err=""):
        self.returncode = code
        self.stdout = out
        self.stderr = err


class ModelPoolTests(unittest.TestCase):
    def test_catalog_unique_and_provider_coverage(self):
        data = pool.load_catalog()
        ids = [entry["id"] for entry in data["candidates"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(x.split("/")[0] for x in ids),
                         {"google", "groq", "openrouter", "opencode", "nvidia"})
        self.assertTrue(all(not x["verified_for_autonomy"] for x in data["candidates"]))

    def test_probe_uses_exact_id_and_no_shell(self):
        called = []
        def fake(cmd, **kwargs):
            called.append((cmd, kwargs))
            return Result()
        result = pool.probe("nvidia/z-ai/glm-5.3", runner=fake)
        self.assertEqual(result["status"], "responded")
        self.assertEqual(called[0][0][:4],
                         ["opencode", "run", "--model", "nvidia/z-ai/glm-5.3"])
        self.assertNotIn("shell", called[0][1])

    def test_wrong_answer_is_not_success(self):
        self.assertEqual(pool.probe("google/gemini-3.8-flash",
                         runner=lambda *a, **k: Result(out="NOT_OK"))["status"],
                         "unexpected_response")

    def test_error_classes(self):
        for message, expected in [
            ("429 TooManyRequests", "rate_limited"),
            ("resource_exhausted quota exceeded", "rate_limited"),
            ("401 invalid API key", "auth_or_billing"),
            ("404 Model not found", "model_unavailable"),
            ("503 ServiceUnavailable", "temporary_error"),
        ]:
            with self.subTest(message=message):
                self.assertEqual(pool.classify_error(message), expected)

    def test_timeout_and_missing_cli(self):
        def timeout(*a, **k):
            raise subprocess.TimeoutExpired("opencode", 5)
        def missing(*a, **k):
            raise FileNotFoundError("opencode")
        self.assertEqual(pool.probe("test/model", runner=timeout)["status"], "timeout")
        self.assertEqual(pool.probe("test/model", runner=missing)["status"], "cli_unavailable")

    def test_private_state_contains_only_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = pathlib.Path(folder) / "state.json"
            pool.record({"model": "test/model", "status": "responded"}, dest)
            data = json.loads(dest.read_text())
            self.assertEqual(data[0]["model"], "test/model")
            self.assertEqual(set(data[0]), {"model", "status", "timestamp_utc"})
            self.assertEqual(len(data), 1)


if __name__ == "__main__":
    unittest.main()
