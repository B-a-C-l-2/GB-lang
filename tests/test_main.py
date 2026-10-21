# -*- coding: utf-8 -*-
"""入口层错误格式测试：^ 指示行按显示宽度对齐（v0.3）。"""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

from gb.__main__ import _format_error, _pointer_line, main

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestPointerLine(unittest.TestCase):
    def test_narrow(self):
        self.assertEqual(_pointer_line("print(a[5]);", 7), "      ^")

    def test_wide_chars(self):
        # 第 10 列前是 9 个窄字符；第 12 列前含 中/文 两个宽字符（各计 2）
        self.assertEqual(_pointer_line('let s = "中文";', 10),
                         " " * 9 + "^")
        self.assertEqual(_pointer_line('let s = "中文";', 12),
                         " " * (9 + 2 + 2) + "^")

    def test_tab_expands(self):
        # Tab 展开到 8 列制表位
        self.assertEqual(_pointer_line("\tlet x = 1;", 2),
                         " " * 8 + "^")
        self.assertEqual(_pointer_line("\tlet x = 1;", 9),
                         " " * (8 + 7) + "^")

    def test_format_error_uses_width(self):
        src = 'let s = "中文";'
        text = _format_error("词法", "测试", src, 1, 13)
        # 第 13 列是行尾 ; 之后？ 行共 13 字符；出错列前 12 字符：
        # 8 窄 + 2 宽(4) = 12 宽度
        self.assertEqual(text.splitlines()[-1], " " * 14 + "^")


class TestEofAfterTrailingNewline(unittest.TestCase):
    """v0.4.4：EOF 落在末行换行之后时，仍打印（空）源码行与 ^ 指示。"""

    def _run_source_bytes(self, data):
        fd, path = tempfile.mkstemp(suffix=".gb")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = main(["gb", path])
        finally:
            os.unlink(path)
        return code, err.getvalue()

    def test_newline_before_eof(self):
        code, text = self._run_source_bytes(b"let x =\n")
        self.assertEqual(code, 1)
        self.assertIn("文件末尾", text)
        # 末行为空：先一行空串，再一行仅 ^（print 末尾另有换行）
        self.assertTrue(text.endswith("\n\n^\n"), repr(text))

    def test_no_newline_before_eof_unchanged(self):
        code, text = self._run_source_bytes(b"let x =")
        self.assertEqual(code, 1)
        self.assertIn("文件末尾", text)
        self.assertTrue(text.endswith("\nlet x =\n       ^\n"), repr(text))


class TestParseRecursion(unittest.TestCase):
    """v0.3.1：解析阶段深层嵌套报友好错误，不输出裸 traceback。"""

    def test_deep_nesting_reports_friendly_error(self):
        src = "print(" + "(" * 5000 + "1" + ")" * 5000 + ");"
        fd, path = tempfile.mkstemp(suffix=".gb")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(src)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = main(["gb", path])
        finally:
            os.unlink(path)
        self.assertEqual(code, 1)
        self.assertIn("嵌套过深", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())


class TestBrokenPipe(unittest.TestCase):
    """v0.4.4：下游管道提前关闭（如 | head）时静默退出，无裸 traceback。"""

    def _closed_pipe_child(self, unbuffered):
        """20 万行确保写满管道缓冲：下游读一行即关闭，返回子进程结果。"""
        fd, path = tempfile.mkstemp(suffix=".gb")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("for (let i in [1, 200000]) { print(i); }\n")
            argv = [sys.executable] + (["-u"] if unbuffered else []) + \
                ["-m", "gb", path]
            p = subprocess.Popen(
                argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=_REPO_ROOT)
            p.stdout.readline()  # 只读一行便关闭接收端
            p.stdout.close()
            p.wait(timeout=30)
            err = p.stderr.read()
            p.stderr.close()
            return p.returncode, err
        finally:
            os.unlink(path)

    def test_downstream_closed_emits_no_traceback(self):
        # 缓冲写路径（Windows 实测抛 OSError EINVAL）
        rc, err = self._closed_pipe_child(unbuffered=False)
        self.assertEqual(rc, 1)
        self.assertNotIn(b"Traceback", err)
        self.assertNotIn(b"Exception ignored", err)

    def test_downstream_closed_unbuffered(self):
        # 无缓冲写路径（BrokenPipeError）
        rc, err = self._closed_pipe_child(unbuffered=True)
        self.assertEqual(rc, 1)
        self.assertNotIn(b"Traceback", err)


class TestBomSource(unittest.TestCase):
    """v0.4.3：源文件可带 UTF-8 BOM。"""

    def test_bom_source_is_accepted(self):
        fd, path = tempfile.mkstemp(suffix=".gb")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(b"\xef\xbb\xbfprint(1);")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out):
                with contextlib.redirect_stderr(err):
                    code = main(["gb", path])
        finally:
            os.unlink(path)
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue(), "1\n")
        self.assertEqual(err.getvalue(), "")


class TestNonUtf8Source(unittest.TestCase):
    """v0.4.1：非 UTF-8 源文件报友好错误，不输出裸 traceback。"""

    def test_gbk_file_reports_friendly_error(self):
        fd, path = tempfile.mkstemp(suffix=".gb")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write('print("中文");'.encode("gbk"))
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = main(["gb", path])
        finally:
            os.unlink(path)
        self.assertEqual(code, 1)
        self.assertIn("UTF-8", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())


if __name__ == "__main__":
    unittest.main()
