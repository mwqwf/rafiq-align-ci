#!/usr/bin/env python3
"""اختباراتُ شجرة ffmpeg المخبّأة (‏2026-10-23): الاستعادةُ بلا شبكة، وإهمالُ التالف، والغلافُ يضع مكتباتِ الشجرة أمام مكتبات النظام."""
import importlib.util, os, pathlib, shutil, stat, sys, tempfile, unittest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("iqf", HERE / "install_qa_ffmpeg.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


class TreeTests(unittest.TestCase):
    def setUp(self):
        self.d = pathlib.Path(tempfile.mkdtemp())
        self.old = (M.BIN, M.TREE, os.environ.get("GITHUB_PATH"), os.environ["PATH"])
        M.BIN, M.TREE = self.d / "bin", self.d / "apt-tree"
        os.environ.pop("GITHUB_PATH", None)

    def tearDown(self):
        M.BIN, M.TREE = self.old[0], self.old[1]
        if self.old[2] is not None:
            os.environ["GITHUB_PATH"] = self.old[2]
        os.environ["PATH"] = self.old[3]
        shutil.rmtree(self.d, ignore_errors=True)

    def _fake_tree(self, ok):
        (M.TREE / "bin").mkdir(parents=True)
        (M.TREE / "lib").mkdir()
        for n in ("ffmpeg", "ffprobe"):
            p = M.TREE / "bin" / (n + ".real")
            p.write_text("#!/bin/sh\n" + ("exit 0\n" if ok else "exit 3\n"))
            p.chmod(p.stat().st_mode | stat.S_IXUSR)

    def test_absent_tree_is_not_restored(self):
        self.assertFalse(M.restore_tree())

    def test_good_tree_restores_wrappers_and_path(self):
        self._fake_tree(True)
        self.assertTrue(M.restore_tree())
        for n in ("ffmpeg", "ffprobe"):
            w = (M.BIN / n).read_text()
            self.assertIn("apt-tree", w)
            self.assertIn("LD_LIBRARY_PATH", w)
            self.assertIn(n + ".real", w)
        self.assertTrue(os.environ["PATH"].startswith(str(M.BIN)))

    def test_broken_tree_is_discarded(self):
        self._fake_tree(False)
        self.assertFalse(M.restore_tree())
        self.assertFalse(M.TREE.exists())
        self.assertFalse((M.BIN / "ffmpeg").exists())

    def test_wrapper_does_not_depend_on_path_tools(self):
        self._fake_tree(True)
        M.restore_tree()
        w = (M.BIN / "ffmpeg").read_text()
        self.assertNotIn("dirname", w)   # الغلافُ لا يستدعي أداةً خارجيّة (‏PATH قد يكون مقيَّداً)


if __name__ == "__main__":
    unittest.main()
