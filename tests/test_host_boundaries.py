# -*- coding: utf-8 -*-
"""v0.4.5：宿主异常边界测试。

解释器只允许 GbError（及自身的词法/语法错）面向用户；Python 宿主异常
必须在边界处翻译，否则会泄漏裸 traceback。
"""

import contextlib
import io
import random
import unittest

from gb.builtins import Builtin, GbError
from gb.interpreter import Interpreter, make_global_env
from gb.parser import parse


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


if __name__ == "__main__":
    unittest.main()
