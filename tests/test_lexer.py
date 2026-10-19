import unittest

from gb.lexer import tokenize, LexerError


def lex_types(text):
    return [(t.type, t.value) for t in tokenize(text)]


class TestLexer(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(lex_types("1 2.5 100"), [
            ("NUMBER", 1), ("NUMBER", 2.5), ("NUMBER", 100), ("EOF", None),
        ])

    def test_dot_requires_digit(self):
        # 1.foo：1 是整数，点号单独成 token
        self.assertEqual(lex_types("1.foo")[:3], [
            ("NUMBER", 1), (".", "."), ("IDENT", "foo"),
        ])

    def test_identifiers_and_keywords(self):
        self.assertEqual(lex_types("let x_1")[0:2], [
            ("let", "let"), ("IDENT", "x_1"),
        ])

    def test_string_escapes(self):
        tokens = tokenize(r'"a\nb\tc\\d\"e"')
        self.assertEqual(tokens[0].value, 'a\nb\tc\\d"e')

    def test_comment(self):
        tokens = tokenize("1 + 2 // 注释 \n 3")
        types = [t.type for t in tokens]
        self.assertEqual(types, ["NUMBER", "+", "NUMBER", "NUMBER", "EOF"])
        self.assertEqual(tokens[-2].line, 2)
        self.assertEqual(tokens[-2].col, 2)

    def test_columns(self):
        tokens = tokenize("let x = 1;\nx = 2;\n")
        by = [(t.type, t.line, t.col) for t in tokens if t.type != "EOF"]
        self.assertEqual(by, [
            ("let", 1, 1), ("IDENT", 1, 5), ("=", 1, 7),
            ("NUMBER", 1, 9), (";", 1, 10),
            ("IDENT", 2, 1), ("=", 2, 3), ("NUMBER", 2, 5),
            (";", 2, 6),
        ])

    def test_eof_col_at_end_of_last_line(self):
        tokens = tokenize("1 +")
        self.assertEqual(tokens[-1].type, "EOF")
        self.assertEqual((tokens[-1].line, tokens[-1].col), (1, 4))
        tokens = tokenize("")
        self.assertEqual((tokens[-1].line, tokens[-1].col), (1, 1))

    def test_error_has_column(self):
        try:
            tokenize("let @ = 1;")
        except LexerError as e:
            self.assertEqual((e.line, e.col), (1, 5))
        else:
            self.fail("应抛出 LexerError")

    def test_operators_and_slice_colon(self):
        tokens = tokenize("a[1:2] != b <= c == d")
        self.assertEqual(
            [t.type for t in tokens],
            ["IDENT", "[", "NUMBER", ":", "NUMBER", "]", "!=",
             "IDENT", "<=", "IDENT", "==", "IDENT", "EOF"],
        )

    def test_illegal_character(self):
        with self.assertRaises(LexerError):
            tokenize("let @ = 1;")

    def test_bare_bang(self):
        with self.assertRaises(LexerError):
            tokenize("!x")

    def test_unterminated_string(self):
        with self.assertRaises(LexerError):
            tokenize('"abc')

    def test_bad_escape(self):
        with self.assertRaises(LexerError):
            tokenize(r'"a\x"')


if __name__ == "__main__":
    unittest.main()
