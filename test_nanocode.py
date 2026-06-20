import unittest
import os
import json
from nanocode import Memory, Config, Session, TOOLS

class TestNanocode(unittest.TestCase):
    def test_memory_persistence(self):
        m = Memory(".test_memory.json")
        m.add_history("user", "hello")
        m.data["scratchpad"] = "test scratch"
        m.save()

        m2 = Memory(".test_memory.json")
        self.assertEqual(m2.data["history"][0]["content"], "hello")
        self.assertEqual(m2.data["scratchpad"], "test scratch")
        os.remove(".test_memory.json")

    def test_config_provider_detection(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        c = Config()
        self.assertEqual(c.provider, "openai")
        self.assertEqual(c.api_url, "https://api.openai.com/v1/chat/completions")

        del os.environ["OPENAI_API_KEY"]
        os.environ["OPENROUTER_API_KEY"] = "sk-or"
        c2 = Config()
        self.assertEqual(c2.provider, "anthropic")
        self.assertIn("openrouter", c2.api_url)
        del os.environ["OPENROUTER_API_KEY"]

    def test_tool_registry(self):
        self.assertIn("read", TOOLS)
        self.assertIn("write", TOOLS)
        self.assertIn("bash", TOOLS)

    def test_session_schema(self):
        s = Session("test")
        schema = s.make_schema()
        self.assertTrue(any(t["name"] == "read" for t in schema))

if __name__ == "__main__":
    unittest.main()
