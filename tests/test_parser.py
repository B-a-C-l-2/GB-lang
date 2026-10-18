import unittest

from gb.parser import parse, ParseError
from gb import ast


def parse_one(text):
    return parse(text).statements[0]


class TestParser(unittest.TestCase):
    def test_precedence(self):
        node = parse_one("1 + 2 * 3;").expression
        self.assertIsInstance(node, ast.Binary)
        self.assertEqual(node.op, "+")
        self.assertIsInstance(node.right, ast.Binary)
        self.assertEqual(node.right.op, "*")

    def test_comparison_is_not_chainable_as_logic(self):
        node = parse_one("1 < 2 == true;").expression
        self.assertEqual(node.op, "==")
        self.assertEqual(node.left.op, "<")

    def test_unary_and_not(self):
        node = parse_one("-not x;").expression
        self.assertEqual(node.op, "-")
        self.assertIsInstance(node.operand, ast.Unary)
        self.assertEqual(node.operand.op, "not")

    def test_slice_and_index_chain(self):
        node = parse_one("a[1:2][0];").expression
        self.assertIsInstance(node, ast.Index)
        self.assertIsInstance(node.object, ast.Slice)
        self.assertEqual(node.object.start.value, 1)
        self.assertEqual(node.object.end.value, 2)

    def test_assignment_lvalues(self):
        for text in ("x = 1;", "a[i] = 1;", "p.x = 1;"):
            self.assertIsInstance(parse_one(text), ast.ExprStmt)
        with self.assertRaises(ParseError):
            parse("1 = 2;")

    def test_range_for_all_brackets(self):
        for interval in ("[0, 10]", "[0, 10)", "(0, 10]", "(0, 10)"):
            node = parse_one(f"for (let i in {interval}) {{ }}")
            self.assertIsInstance(node, ast.ForRange)
            self.assertEqual(node.name, "i")
        node = parse_one("for (let i in (0, 20]) { print(i); }")
        self.assertFalse(node.interval.left_inclusive)
        self.assertTrue(node.interval.right_inclusive)

    def test_c_style_for(self):
        node = parse_one("for (let i = 0; i < 3; i = i + 1) { }")
        self.assertIsInstance(node, ast.ForC)
        self.assertIsInstance(node.init, ast.Let)
        self.assertIsInstance(node.update, ast.Assign)
        self.assertEqual(node.update.value.op, "+")

    def test_fun_struct_and_calls(self):
        program = parse("struct Point { x, y } fun add(a, b) { return a + b; }")
        self.assertIsInstance(program.statements[0], ast.Struct)
        fun = program.statements[1]
        self.assertEqual(fun.params, ["a", "b"])

    def test_errors(self):
        for text in (
            "let x = 1",          # 缺分号
            "fun f(a, a) { }",    # 参数重复
            "struct S { x, x }",  # 字段重复
            "struct E { }",       # 空 struct
            "for (let i in 0, 10) { }",  # 区间缺左括号
        ):
            with self.assertRaises(ParseError):
                parse(text)

    def test_if_else_chain(self):
        node = parse_one("if (a) { } else if (b) { } else { }")
        self.assertIsNotNone(node.else_body)
        self.assertIsInstance(node.else_body[0], ast.If)

    def test_design_example_parses(self):
        source = """
        struct Point { x, y }
        fun dist2(p) { return p.x * p.x + p.y * p.y; }
        let p = Point(3, 4);
        print("dist2 =", dist2(p));
        for (let i in (0, 20]) {
            if (i % 5 == 0) { print(i); }
        }
        let a = [1, 2, 3, 4];
        let tail = a[1:4];
        """
        program = parse(source)
        self.assertEqual(len(program.statements), 7)


if __name__ == "__main__":
    unittest.main()
