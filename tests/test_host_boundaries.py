# -*- coding: utf-8 -*-
"""v0.4.5：宿主异常边界测试。

解释器只允许 GbError（及自身的词法/语法错）面向用户；Python 宿主异常
必须在边界处翻译，否则会泄漏裸 traceback。
"""

import contextlib
import io
import os
import random
import subprocess
import sys
import tempfile
import unittest

from gb.builtins import Builtin, GbError
from gb.interpreter import Interpreter, make_global_env
from gb.parser import parse

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestBuiltinHostExceptions(unittest.TestCase):
    """内建调用边界：已知宿主异常翻译为 GbError，位置取调用起点。"""

    def _run_with_builtin(self, fn):
        interp = Interpreter(make_global_env())
        # 内建位于全局用户环境之外的只读外层帧
        interp.env.parent.vars["boom"] = Builtin("boom", 0, 0, fn)
        with contextlib.redirect_stdout(io.StringIO()):
            interp.run(parse("boom();"))

    def test_value_error_is_translated(self):
        def boom(args):
            raise ValueError("bad value")

        with self.assertRaises(GbError) as ctx:
            self._run_with_builtin(boom)
        e = ctx.exception
        self.assertEqual(e.message, "内建函数 boom 内部错误：bad value")
        self.assertEqual((e.line, e.col), (1, 1))

    def test_overflow_error_is_translated(self):
        def boom(args):
            raise OverflowError("too large")

        with self.assertRaises(GbError) as ctx:
            self._run_with_builtin(boom)
        e = ctx.exception
        self.assertEqual(e.message, "浮点溢出")
        self.assertEqual((e.line, e.col), (1, 1))

    def test_gb_error_is_kept(self):
        def boom(args):
            raise GbError("自定义错误")

        with self.assertRaises(GbError) as ctx:
            self._run_with_builtin(boom)
        e = ctx.exception
        self.assertEqual(e.message, "自定义错误")
        self.assertEqual((e.line, e.col), (1, 1))


class TestRandomHostBoundaries(unittest.TestCase):
    """固定种子轻量 fuzz：随机表达式/内建调用不得泄漏宿主异常。"""

    VALUES = [
        "0", "1", "-1", "2", "2.5", "-0.5",
        '"a"', '"12"', '""', "true", "false", "null",
        "[]", "[1, 2]",
        str(2 ** 16384),                 # 超大 int：混合算术的溢出入口
        "1" + "0" * 400 + ".0",          # 超大浮点字面量
    ]
    OPS = ["+", "-", "*", "/", "%", "==", "!=",
           "<", "<=", ">", ">=", "and", "or"]

    def _assert_only_gb_error(self, source):
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                Interpreter(make_global_env()).run(parse(source))
        except GbError:
            pass
        except Exception as e:  # noqa: BLE001 - 这里就是要拦住一切宿主异常
            self.fail(f"{source!r} 泄漏宿主异常 "
                      f"{type(e).__name__}: {e}")

    def test_random_binary_expressions(self):
        rng = random.Random(20261021)
        for _ in range(200):
            source = (f"print({rng.choice(self.VALUES)} "
                      f"{rng.choice(self.OPS)} "
                      f"{rng.choice(self.VALUES)});")
            self._assert_only_gb_error(source)

    def test_builtin_conversions(self):
        for fn in ("int", "float", "str", "len"):
            for value in self.VALUES:
                with self.subTest(fn=fn, value=value[:20]):
                    self._assert_only_gb_error(f"print({fn}({value}));")


class TestCliNoTraceback(unittest.TestCase):
    """v0.4.5：CLI 端到端只输出友好错误，绝不泄漏 Traceback。"""

    def _run_source(self, source, stdin=""):
        fd, path = tempfile.mkstemp(suffix=".gb")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write(source)
            return subprocess.run(
                [sys.executable, "-m", "gb", path],
                cwd=_REPO_ROOT, input=stdin, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=60)
        finally:
            os.unlink(path)

    def test_boundary_programs(self):
        big = "9" * 5000
        cases = [
            ("大整数字面量", f"print(len(str({big})));", "5000\n", None),
            ("超大 int 混合浮点",
             "let n = 2; for (let i in [1, 14]) { n = n * n; } "
             "print(n + 1.0);", None, "浮点溢出"),
            ("浮点字面量溢出",
             "let x = " + "1" + "0" * 400 + ".0;", None, "浮点溢出"),
            ("float() 溢出", 'print(float("' + "1" * 400 + '"));',
             None, "浮点溢出"),
            ("int() 尾随换行", 'print(int("12\\n"));', None, "无法将"),
            ("切片端点类型", "let a = [1]; print(a[0:true]);",
             None, "切片端点必须是 int"),
            ("for-in 后缀回退", "for (let x in [1, 2][0:2]) { print(x); }",
             "1\n2\n", None),
            ("EOF 末行指示", "let x = 1\n", None, "^"),
        ]
        for name, source, want_out, want_err in cases:
            with self.subTest(name=name):
                p = self._run_source(source)
                self.assertNotIn("Traceback", p.stderr)
                if want_out is not None:
                    self.assertEqual(p.returncode, 0)
                    self.assertEqual(p.stdout, want_out)
                else:
                    self.assertEqual(p.returncode, 1)
                    self.assertIn(want_err, p.stderr)

    def test_non_utf8_stdin(self):
        fd, path = tempfile.mkstemp(suffix=".gb")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("let s = input(); print(s);")
            p = subprocess.run(
                [sys.executable, "-m", "gb", path], cwd=_REPO_ROOT,
                input="中文\n".encode("gbk"), capture_output=True,
                timeout=60)
        finally:
            os.unlink(path)
        err = p.stderr.decode("utf-8", "replace")
        self.assertEqual(p.returncode, 1)
        self.assertNotIn("Traceback", err)
        self.assertIn("输入不是有效的 UTF-8", err)

    def test_bom_source(self):
        fd, path = tempfile.mkstemp(suffix=".gb")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(b"\xef\xbb\xbfprint(1);")
            p = subprocess.run(
                [sys.executable, "-m", "gb", path], cwd=_REPO_ROOT,
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60)
        finally:
            os.unlink(path)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "1\n")
        self.assertEqual(p.stderr, "")


if __name__ == "__main__":
    unittest.main()
