import unittest
import os
from tools.scripts.link_auditor import find_broken_links

class TestLinkAuditor(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_docs"
        os.makedirs(self.test_dir, exist_ok=True)
        # Create a valid file
        with open(os.path.join(self.test_dir, "valid.md"), "w") as f:
            f.write("content")
        # Create a file with broken link
        with open(os.path.join(self.test_dir, "broken.md"), "w") as f:
            f.write("[[nonexistent.md|Title]]")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir)

    def test_find_broken_links(self):
        broken = find_broken_links(self.test_dir)
        self.assertEqual(len(broken), 1)
        self.assertEqual(broken[0][0], os.path.join(self.test_dir, "broken.md"))
        self.assertEqual(broken[0][1], "nonexistent.md")

if __name__ == "__main__":
    unittest.main()
