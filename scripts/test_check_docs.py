from pathlib import Path
import tempfile
import unittest
from check_docs import anchors, check, prose


class DocumentationChecks(unittest.TestCase):
    def test_fences_and_duplicate_unicode_headings(self):
        text, bad = prose("# Caf\u00e9\n# Caf\u00e9\n```text\n# hidden\n```\n")
        self.assertFalse(bad)
        self.assertEqual(anchors(text), {"caf\u00e9", "caf\u00e9-1"})
        self.assertTrue(prose("~~~text\nx\n")[1])

    def test_negative_links_anchors_commands_and_secret_are_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            content = "# Home\n[ok](target.md#exists) [bad](target.md#absent) [missing](missing.md)\n`tests/missing.py`\n"
            (root / "README.md").write_text(content, encoding="utf-8")
            (root / "target.md").write_text("# Exists\n", encoding="utf-8")
            failures, counts = check(root, ["README.md", "target.md"])
            self.assertEqual(len(failures), 3)
            self.assertEqual(counts["local_links"], 2)
            (root / "README.md").write_text("# Home\n[ok](target.md#exists)\n", encoding="utf-8")
            self.assertEqual(check(root, ["README.md", "target.md"])[0], [])
            (root / "README.md").write_text("# Secret\n" + "tvly-" + "x" * 32 + "\n", encoding="utf-8")
            failures, _ = check(root, ["README.md"])
            self.assertIn("forbidden", failures[0][1])
            self.assertNotIn("tvly", str(failures))


if __name__ == "__main__":
    unittest.main()
