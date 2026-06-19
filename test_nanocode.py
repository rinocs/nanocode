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

    def test_memory_bounding(self):
        m = Memory(".test_memory_bound.json")
        for i in range(30):
            m.add_history("user", f"msg {i}")
        self.assertEqual(len(m.data["history"]), 20)
        os.remove(".test_memory_bound.json")

    def test_config_defaults(self):
        c = Config()
        self.assertIn("claude", c.model)
        self.assertTrue(c.use_memory)

    def test_tool_registry(self):
        self.assertIn("read", TOOLS)
        self.assertIn("write", TOOLS)
        self.assertIn("bash", TOOLS)

    def test_session_schema(self):
        s = Session("test")
        schema = s.make_schema()
        self.assertTrue(any(t["name"] == "read" for t in schema))
        self.assertTrue(any(t["name"] == "bash" for t in schema))

if __name__ == "__main__":
    unittest.main()
