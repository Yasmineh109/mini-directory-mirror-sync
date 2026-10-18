import os
import shutil
import tempfile
import unittest

from mini_directory_mirror_sync import MirrorSync, SyncResult


class MirrorSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.source = os.path.join(self.tmp, "src")
        self.dest = os.path.join(self.tmp, "dst")
        os.makedirs(self.source)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, root, rel, content):
        path = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return path

    def read(self, root, rel):
        path = os.path.join(root, *rel.split("/"))
        with open(path) as f:
            return f.read()

    def test_empty_source_creates_empty_dest(self):
        result = MirrorSync().sync(self.source, self.dest)
        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.copied, [])
        self.assertEqual(result.updated, [])
        self.assertEqual(result.removed, [])
        self.assertTrue(os.path.isdir(self.dest))

    def test_copies_new_files(self):
        self.write(self.source, "a.txt", "hello")
        self.write(self.source, "sub/b.txt", "world")
        result = MirrorSync().sync(self.source, self.dest)
        self.assertEqual(sorted(result.copied), ["a.txt", "sub/b.txt"])
        self.assertEqual(result.updated, [])
        self.assertEqual(result.removed, [])
        self.assertEqual(self.read(self.dest, "a.txt"), "hello")
        self.assertEqual(self.read(self.dest, "sub/b.txt"), "world")

    def test_no_change_means_no_copy(self):
        self.write(self.source, "a.txt", "hello")
        MirrorSync().sync(self.source, self.dest)
        result = MirrorSync().sync(self.source, self.dest)
        self.assertEqual(result.copied, [])
        self.assertEqual(result.updated, [])
        self.assertEqual(result.removed, [])

    def test_updates_changed_file(self):
        self.write(self.source, "a.txt", "hello")
        MirrorSync().sync(self.source, self.dest)
        self.write(self.source, "a.txt", "changed")
        result = MirrorSync().sync(self.source, self.dest)
        self.assertEqual(result.copied, [])
        self.assertEqual(result.updated, ["a.txt"])
        self.assertEqual(result.removed, [])
        self.assertEqual(self.read(self.dest, "a.txt"), "changed")

    def test_update_with_shorter_content(self):
        self.write(self.source, "a.txt", "aaaaaaaaaa")
        MirrorSync().sync(self.source, self.dest)
        self.write(self.source, "a.txt", "bb")
        MirrorSync().sync(self.source, self.dest)
        self.assertEqual(self.read(self.dest, "a.txt"), "bb")

    def test_removes_files_absent_from_source(self):
        self.write(self.source, "keep.txt", "keep")
        MirrorSync().sync(self.source, self.dest)
        self.write(self.dest, "stale.txt", "stale")
        self.write(self.dest, "sub/extra.txt", "extra")
        result = MirrorSync().sync(self.source, self.dest)
        self.assertEqual(result.copied, [])
        self.assertEqual(result.updated, [])
        self.assertEqual(sorted(result.removed), ["stale.txt", "sub/extra.txt"])
        self.assertFalse(os.path.exists(os.path.join(self.dest, "stale.txt")))

    def test_missing_source_raises(self):
        with self.assertRaises(FileNotFoundError):
            MirrorSync().sync(os.path.join(self.tmp, "does_not_exist"), self.dest)

    def test_idempotent(self):
        self.write(self.source, "a.txt", "hello")
        self.write(self.source, "sub/b.txt", "world")
        MirrorSync().sync(self.source, self.dest)
        r1 = MirrorSync().sync(self.source, self.dest)
        r2 = MirrorSync().sync(self.source, self.dest)
        self.assertEqual(r1.copied, [])
        self.assertEqual(r1.updated, [])
        self.assertEqual(r1.removed, [])
        self.assertEqual(r2.copied, [])
        self.assertEqual(r2.updated, [])
        self.assertEqual(r2.removed, [])

    def test_empty_subdir_mirrored(self):
        self.write(self.source, "sub/a.txt", "x")
        MirrorSync().sync(self.source, self.dest)
        os.remove(os.path.join(self.source, "sub", "a.txt"))
        result = MirrorSync().sync(self.source, self.dest)
        self.assertIn("sub/a.txt", result.removed)
        self.assertFalse(os.path.exists(os.path.join(self.dest, "sub", "a.txt")))

    def test_partial_dest_then_fill(self):
        self.write(self.source, "a.txt", "hello")
        self.write(self.source, "b.txt", "world")
        MirrorSync().sync(self.source, self.dest)
        os.remove(os.path.join(self.dest, "a.txt"))
        result = MirrorSync().sync(self.source, self.dest)
        self.assertEqual(result.copied, ["a.txt"])
        self.assertEqual(self.read(self.dest, "a.txt"), "hello")

    def test_result_lists_are_sorted(self):
        self.write(self.source, "c.txt", "1")
        self.write(self.source, "a.txt", "2")
        self.write(self.source, "b.txt", "3")
        result = MirrorSync().sync(self.source, self.dest)
        self.assertEqual(result.copied, ["a.txt", "b.txt", "c.txt"])

    def test_replaces_existing_file_with_different_content(self):
        self.write(self.dest, "a.txt", "old content")
        self.write(self.source, "a.txt", "new content")
        result = MirrorSync().sync(self.source, self.dest)
        self.assertEqual(result.updated, ["a.txt"])
        self.assertEqual(self.read(self.dest, "a.txt"), "new content")


if __name__ == "__main__":
    unittest.main()
