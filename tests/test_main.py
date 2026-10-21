# -*- coding: utf-8 -*-
"""入口层错误格式测试：^ 指示行按显示宽度对齐（v0.3）。"""

import contextlib
import io
import os
import tempfile
import unittest

from gb.__main__ import _format_error, _pointer_line, main


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
