import contextlib
import io
import sys
import unittest

from gb.parser import parse
from gb.interpreter import Interpreter, make_global_env
from gb.builtins import GbError


def run(src, stdin=""):
    """执行源码，返回标准输出字符串。"""
    out, sin = io.StringIO(), io.StringIO(stdin)
    interp = Interpreter(make_global_env())
    old_stdin = sys.stdin
    sys.stdin = sin
    try:
        with contextlib.redirect_stdout(out):
            interp.run(parse(src))
    finally:
        sys.stdin = old_stdin
    return out.getvalue()


def run_error(src):
    """断言源码抛出 GbError，返回该错误。"""
    with unittest.TestCase().assertRaises(GbError) as ctx:
        run(src)
    return ctx.exception


class TestArithmetic(unittest.TestCase):
    def test_precedence_and_division(self):
        self.assertEqual(run("print(1 + 2 * 3);"), "7\n")
        self.assertEqual(run("print(3 / 2); print(4 / 2);"), "1.5\n2.0\n")
        self.assertEqual(run("print(2 * 1.5);"), "3.0\n")

    def test_modulo_python_semantics(self):
        self.assertEqual(run("print(-7 % 3, 7 % -3, 6.5 % 2);"),
                         "2 -2 0.5\n")

    def test_unary(self):
        self.assertEqual(run("print(-5, --2, not 0, not null);"),
                         "-5 2 false true\n")

    def test_bool_is_not_a_number(self):
        for src in ("print(1 + true);", "print(true * 2);",
                    "print(-false);", "print(2.0 % true);"):
            run_error(src)

    def test_divide_by_zero(self):
        run_error("print(1 / 0);")
        run_error("print(1 % 0);")

    def test_string_concat_only_between_strings(self):
        self.assertEqual(run('print("a" + "b");'), "ab\n")
        run_error('print("a" + 1);')


class TestComparison(unittest.TestCase):
    def test_equality_strict(self):
        src = ('print(1 == 1.0, 1 != true, "1" != 1, '
               'null == null, null != false);')
        self.assertEqual(run(src), "true true true true true\n")

    def test_array_equality_is_structural(self):
        self.assertEqual(run("print([1, 2] == [1, 2], [1] == [1, 2]);"),
                         "true false\n")

    def test_struct_identity(self):
        src = ("struct P { x } let a = P(1); let b = P(1);"
               "print(a == b, a == a);")
        self.assertEqual(run(src), "false true\n")

    def test_ordering_cross_type_is_error(self):
        run_error("print(true < 2);")
        run_error("print(null < 1);")
        run_error('print("a" < 1);')

    def test_array_and_string_ordering(self):
        self.assertEqual(run('print([1, 2] < [1, 3], "abc" < "abd");'),
                         "true true\n")


class TestTruthiness(unittest.TestCase):
    def test_only_false_and_null_are_falsy(self):
        src = """
        fun isTruthy(x) { if (x) { return "t"; } else { return "f"; } }
        print(isTruthy(0), isTruthy(""), isTruthy([]),
              isTruthy(false), isTruthy(null));
        """
        self.assertEqual(run(src), "t t t f f\n")

    def test_logical_returns_bool_and_short_circuits(self):
        # v0.3：and/or 结果恒为布尔；GB 中 0、"" 皆为真
        self.assertEqual(run('print(0 or "x", 1 and 2);'), "true true\n")
        self.assertEqual(run("print(null or false);"), "false\n")
        src = """
        fun boom() { return 1 / 0; }
        print(true or boom());
        print(false and boom());
        """
        self.assertEqual(run(src), "true\nfalse\n")


class TestBreakContinueBoundary(unittest.TestCase):
    def test_break_cannot_escape_function(self):
        e = run_error("fun f() { break; }\nwhile (true) { f(); }")
        self.assertIn("break", e.message)

    def test_continue_cannot_escape_function(self):
        e = run_error("fun f() { continue; }\nwhile (true) { f(); }")
        self.assertIn("continue", e.message)


class TestIndexAndSlice(unittest.TestCase):
    def test_string_index(self):
        self.assertEqual(run('print("hello"[1]);'), "e\n")
        run_error('print("hello"[5]);')
        run_error('print("hello"[-1]);')

    def test_index_must_be_int(self):
        run_error("let a = [1]; print(a[true]);")
        run_error("print(\"ab\"[1.0]);")

    def test_slice_arrays_and_strings(self):
        self.assertEqual(run("print([1, 2, 3, 4][1:3]);"), "[2, 3]\n")
        self.assertEqual(run('print("hello"[1:4]);'), "ell\n")

    def test_slice_clamps(self):
        self.assertEqual(run('print("abc"[0:99], "abc"[2:2]);'),
                         "abc \n")
        self.assertEqual(run("print([1, 2][9:3]);"), "[]\n")

    def test_array_mutation(self):
        src = "let a = [1, 2]; a[0] = 9; print(a);"
        self.assertEqual(run(src), "[9, 2]\n")
        run_error('let s = "ab"; s[0] = "x";')
        run_error("let a = [1]; a[5] = 2;")


class TestStruct(unittest.TestCase):
    def test_construction_and_fields(self):
        src = ("struct Point { x, y } "
               "let p = Point(3, 4); p.x = 10; "
               "print(p, p.x + p.y);")
        self.assertEqual(run(src), "Point(10, 4) 14\n")

    def test_arity_and_unknown_field(self):
        run_error("struct P { x, y } P(1);")
        run_error("struct P { x } let p = P(1); print(p.z);")
        run_error("struct P { x } let p = P(1); p.z = 2;")


class TestFunctions(unittest.TestCase):
    def test_recursion(self):
        src = """
        fun fact(n) {
            if (n <= 1) { return 1; }
            return n * fact(n - 1);
        }
        print(fact(5));
        """
        self.assertEqual(run(src), "120\n")

    def test_closure_captures_outer_let(self):
        src = """
        fun outer() {
            let x = 10;
            fun inner() { return x; }
            return inner();
        }
        print(outer());
        """
        self.assertEqual(run(src), "10\n")

    def test_closure_mutation(self):
        src = """
        fun counter() {
            let n = 0;
            fun next() { n = n + 1; return n; }
            return next() + next();
        }
        print(counter());
        """
        self.assertEqual(run(src), "3\n")

    def test_hoisting_forward_call(self):
        # 定义语句执行之前即可调用
        self.assertEqual(run("print(f()); fun f() { return 1; }"), "1\n")
        src = ("let p = Point(3, 4); print(p.x);"
               "struct Point { x, y }")
        self.assertEqual(run(src), "3\n")

    def test_hoisting_mutual_recursion(self):
        src = """
        fun isEven(n) { if (n == 0) { return true; } return isOdd(n - 1); }
        fun isOdd(n) { if (n == 0) { return false; } return isEven(n - 1); }
        print(isEven(10), isOdd(7));
        """
        self.assertEqual(run(src), "true true\n")

    def test_hoisting_is_block_scoped(self):
        # 块内声明不提升到块外
        self.assertEqual(run("{ fun g() { return 1; } print(g()); }"), "1\n")
        run_error("g(); { fun g() { return 1; } }")

    def test_calling_never_declared_still_errors(self):
        run_error("print(nope());")

    def test_duplicate_fun_same_scope_errors(self):
        run_error("fun f() { return 1; } fun f() { return 2; }")

    def test_arity_mismatch(self):
        run_error("fun f(a) { } f(1, 2);")

    def test_functions_are_not_values(self):
        run_error("fun f() { } let g = f;")
        run_error("fun f() { } print(f);")
        run_error("let g = print;")

    def test_call_non_callable(self):
        run_error("let x = 1; x();")


class TestScope(unittest.TestCase):
    def test_block_shadowing_ok(self):
        src = "let x = 1; { let x = 2; print(x); } print(x);"
        self.assertEqual(run(src), "2\n1\n")

    def test_redeclare_same_scope_is_error(self):
        run_error("let x = 1; let x = 2;")
        run_error("fun f() { let x = 1; let x = 2; } f();")

    def test_redeclare_error_names_existing_kind(self):
        e = run_error("fun f() { } let f = 2;")
        self.assertIn("已声明为函数", e.message)
        e = run_error("struct S { x } fun S() { }")
        self.assertIn("已声明为struct", e.message)

    def test_builtin_names_are_shadowable(self):
        self.assertEqual(run("let len = 5; print(len);"), "5\n")
        # 顶层 fun 遮蔽内建 len（函数不是值，只能调用）
        self.assertEqual(run("fun len() { return 9; } print(len());"),
                         "9\n")
        # 函数内 let 遮蔽（v0.1 即支持）
        self.assertEqual(
            run("fun f() { let print = 3; return print; } print(f());"),
            "3\n")
        # 未遮蔽时内建照常可用
        self.assertEqual(run('print(len([1, 2]));'), "2\n")

    def test_builtins_cannot_be_reassigned_without_let(self):
        run_error("len = 5;")
        # 内建未被污染
        self.assertEqual(run("print(len([1, 2]));"), "2\n")

    def test_assign_undeclared_is_error(self):
        run_error("x = 1;")


class TestLoops(unittest.TestCase):
    def test_while_break_continue(self):
        src = """
        let i = 0;
        let sum = 0;
        while (true) {
            i = i + 1;
            if (i > 5) { break; }
            if (i == 3) { continue; }
            sum = sum + i;
        }
        print(sum);
        """
        self.assertEqual(run(src), "12\n")  # 1+2+4+5

    def test_c_style_for(self):
        src = "let s = 0; for (let i = 1; i <= 4; i = i + 1) { s = s + i; } print(s);"
        self.assertEqual(run(src), "10\n")

    def test_range_for_all_brackets(self):
        # [1, 4] = 1..4, [1, 4) = 1..3, (0, 4] = 1..4, (0, 4) = 1..3
        src = """
        let s = 0;
        for (let i in [1, 4]) { s = s + i; }
        for (let i in [1, 4)) { s = s + i; }
        for (let i in (0, 4]) { s = s + i; }
        for (let i in (0, 4)) { s = s + i; }
        print(s);
        """
        self.assertEqual(run(src), "32\n")  # 10+6+10+6

    def test_range_for_empty_and_non_int(self):
        self.assertEqual(run("for (let i in (5, 3)) { print(i); }"), "")
        run_error("for (let i in [1, 2.0]) { }")
        run_error("for (let i in [1, true]) { }")

    def test_range_for_without_let_reuses_outer_var(self):
        src = ("let i = -5;\n"
               "for (i in [1, 6]) { print(i); }\n"
               "print(i);")
        self.assertEqual(run(src), "1\n2\n3\n4\n5\n6\n6\n")

    def test_range_for_without_let_undeclared_is_error(self):
        e = run_error("for (z in [1, 3]) { print(z); }")
        self.assertEqual((e.line, e.col), (1, 6))  # 变量名 z

    def test_range_for_without_let_empty_assigns_start(self):
        # (5, 3) 换算起点为 6，零次循环也先赋起点
        self.assertEqual(
            run("let i = 9; for (i in (5, 3)) { } print(i);"), "6\n")

    def test_range_for_let_remains_block_scoped(self):
        run_error("for (let i in [1, 2]) { } print(i);")

    def test_break_continue_outside_loop(self):
        run_error("break;")
        run_error("continue;")

    def test_return_outside_function(self):
        run_error("return 1;")


class TestBuiltins(unittest.TestCase):
    def test_len_push_conversions(self):
        src = ("let a = [1]; push(a, 2);"
               "print(len(a), len(\"héllo\"));"
               "print(int(2.9), int(\"12\"), float(1), str(2.5));")
        self.assertEqual(run(src), "2 5\n2 12 1.0 2.5\n")

    def test_bad_conversion(self):
        run_error('print(int("abc"));')
        run_error("print(int(true));")

    def test_int_float_strict_string_parsing(self):
        # v0.3.1：严格匹配 GB 字面量语法（可选前导 -）
        src = 'print(int("-5"), int("007"), float("2"), float("-2.5"));'
        self.assertEqual(run(src), "-5 7 2.0 -2.5\n")
        # Python 扩展形式一律报错
        for src in ('print(int("１２"));',   # 全角数字
                    'print(int("1_0"));',    # 下划线
                    'print(int(" 12"));',    # 首尾空白
                    'print(int("12 "));',
                    'print(int("+12"));',    # + 号
                    'print(int("-"));',
                    'print(int(""));',
                    'print(float("nan"));',
                    'print(float("inf"));',
                    'print(float("1e3"));',  # 科学计数法
                    'print(float("2."));',
                    'print(float(".5"));',
                    'print(float("1_0.5"));'):
            run_error(src)

    def test_input(self):
        src = 'let name = input("name? "); print("hi " + name);'
        self.assertEqual(run(src, stdin="Bob\n"), "name? hi Bob\n")

    def test_pop(self):
        src = "let a = [1, 2, 3];\nprint(pop(a));\nprint(a);"
        self.assertEqual(run(src), "3\n[1, 2]\n")

    def test_pop_errors(self):
        run_error("pop([]);")
        run_error("pop(1);")

    def test_input_eof_returns_null(self):
        # v0.3：EOF 返回 null，区别于空行 ""
        self.assertEqual(run("print(input());"), "null\n")
        self.assertEqual(run("print(input());", stdin="\n"), "\n")
        src = "let x = input();\nif (x == null) { print(\"eof\"); }"
        self.assertEqual(run(src), "eof\n")


class TestErrorLocations(unittest.TestCase):
    def test_runtime_error_has_line_and_col(self):
        # 下标越界位置取对象起点 a
        e = run_error("let a = [1];\nprint(a[5]);")
        self.assertEqual((e.line, e.col), (2, 7))

    def test_undeclared_var_points_at_name(self):
        e = run_error("print(missing);")
        self.assertEqual((e.line, e.col), (1, 7))

    def test_builtin_error_backfilled_to_call_site(self):
        e = run_error('print(len(1));')
        self.assertEqual((e.line, e.col), (1, 7))  # len 调用起点


class TestCallStackFrames(unittest.TestCase):
    def test_frames_snapshot_innermost_first(self):
        src = ("fun inner() { return 1 / 0; }\n"
               "fun outer() { return inner(); }\n"
               "print(outer());")
        e = run_error(src)
        # 帧按调用顺序入栈：outer 先、inner 后
        self.assertEqual(e.gb_frames,
                         [("outer", 3, 7), ("inner", 2, 22)])

    def test_no_frames_at_top_level(self):
        e = run_error("print(1 / 0);")
        self.assertIsNone(getattr(e, "gb_frames", None))

    def test_frames_via_builtin_error(self):
        src = ("fun f() { return len(1); }\n"
               "print(f());")
        e = run_error(src)
        self.assertEqual(e.gb_frames, [("f", 2, 7)])


class TestCyclicReference(unittest.TestCase):
    """v0.3.1：禁止循环引用，遍历侧检测；无环的共享引用（菱形）不受影响。"""

    def test_display_cyclic_array_is_error(self):
        e = run_error("let a = []; push(a, a); print(a);")
        self.assertIn("循环引用", e.message)

    def test_display_diamond_sharing_is_fine(self):
        src = "let b = [1]; let a = [b, b]; print(a, a == [b, b]);"
        self.assertEqual(run(src), "[[1], [1]] true\n")

    def test_str_cyclic_is_error(self):
        run_error("let a = []; push(a, a); print(str(a));")

    def test_equal_cyclic_arrays_is_error(self):
        src = ("let a = []; push(a, a);"
               "let b = []; push(b, b); print(a == b);")
        e = run_error(src)
        self.assertIn("循环引用", e.message)

    def test_compare_cyclic_arrays_is_error(self):
        src = ("let a = []; push(a, a);"
               "let b = []; push(b, b); print(a < b);")
        run_error(src)

    def test_struct_instance_cycle_is_error(self):
        run_error("struct N { next } let n = N(null); n.next = n; print(n);")

    def test_mixed_array_struct_cycle_is_error(self):
        src = ("struct B { v } let a = []; let b = B(null);"
               "b.v = a; push(a, b); print(a);")
        run_error(src)


class TestEndToEnd(unittest.TestCase):
    def test_design_example(self):
        src = """
        struct Point { x, y }
        fun dist2(p) {
            return p.x * p.x + p.y * p.y;
        }
        let p = Point(3, 4);
        print("dist2 =", dist2(p));
        for (let i in (0, 20]) {
            if (i % 5 == 0) { print(i); }
        }
        let a = [1, 2, 3, 4];
        let tail = a[1:4];
        print(tail);
        print("hello"[1:4]);
        """
        self.assertEqual(run(src),
                         "dist2 = 25\n5\n10\n15\n20\n[2, 3, 4]\nell\n")


if __name__ == "__main__":
    unittest.main()
