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

    def test_logical_returns_operands_and_short_circuits(self):
        # GB 中 0 为真，故 0 or "x" 取 0
        self.assertEqual(run('print(0 or "x", 1 and 2);'), "0 2\n")
        src = """
        fun boom() { return 1 / 0; }
        print(true or boom());
        print(false and boom());
        """
        self.assertEqual(run(src), "true\nfalse\n")


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

    def test_no_hoisting(self):
        # 定义之前调用：运行到调用点时 f 尚不存在
        run_error("print(f()); fun f() { return 1; }")

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
        run_error("let print = 1;")

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

    def test_input(self):
        src = 'let name = input("name? "); print("hi " + name);'
        self.assertEqual(run(src, stdin="Bob\n"), "name? hi Bob\n")


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
