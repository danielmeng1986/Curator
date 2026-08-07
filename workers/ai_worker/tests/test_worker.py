import unittest
from workers.ai_worker.workflow import AnalysisWorkflow
from workers.ai_worker.provider import ProviderError
class FakeProvider:
    def __init__(self, failures=0): self.failures=failures
    def complete(self, prompt):
        if self.failures: self.failures-=1; raise ProviderError("x")
        return '{"suggested_names": []}'
class WorkerTests(unittest.TestCase):
    def test_result_is_suggestion_only_after_retry(self):
        result=AnalysisWorkflow(FakeProvider(1), sleep=lambda _: None).analyze("x")
        self.assertEqual("suggestion_only", result["status"]); self.assertEqual(2, result["attempt"])
