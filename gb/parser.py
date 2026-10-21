"""GB 语法分析器：Token 列表 -> AST。"""

from gb.lexer import tokenize
from gb import ast


def show_token(tok):
    """错误信息中 token 的显示文本。"""
    if tok.type == "EOF":
        return "文件末尾"
    return f'"{tok.value}"'


class ParseError(Exception):
    def __init__(self, token, message):
        super().__init__(message)
        self.message = message
        self.line = token.line
        self.col = token.col
        self.got = show_token(token)

    def __str__(self):
        return (f"语法错误（第 {self.line} 行，第 {self.col} 列）："
                f"{self.message}，遇到 {self.got}")


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self._pos = 0

    # ---------- Token 辅助 ----------

    def _current(self):
        return self.tokens[min(self._pos, len(self.tokens) - 1)]

    def _peek(self, offset=0):
        i = min(self._pos + offset, len(self.tokens) - 1)
        return self.tokens[i]

    def _check(self, type):
        return self._current().type == type

    def _advance(self):
        tok = self._current()
        if tok.type != "EOF":
            self._pos += 1
        return tok

    def _match(self, *types):
        if self._current().type in types:
            return self._advance()
        return None

    # 期望不符合时的用户可见名称：标点/关键字按词面，token 类型用中文
    _EXPECTED_DISPLAY = {"IDENT": "标识符", "NUMBER": "数值",
                         "STRING": "字符串"}

    def _expect(self, type):
        if self._check(type):
            return self._advance()
        expected = self._EXPECTED_DISPLAY.get(type, f'"{type}"')
        raise ParseError(self._current(), f"此处应为{expected}")

    # ---------- 入口 ----------

    def parse(self):
        statements = []
        while not self._check("EOF"):
            statements.append(self._statement())
        return ast.Module(statements)

    # ---------- 语句 ----------

    def _statement(self):
        t = self._current().type
        if t == "{":
            return self._block_statement()
        if t == "let":
            return self._let_decl()
        if t == "fun":
            return self._fun_decl()
        if t == "struct":
            return self._struct_decl()
        if t == "return":
            return self._return_statement()
        if t == "if":
            return self._if_statement()
        if t == "while":
            return self._while_statement()
        if t == "for":
            return self._for_statement()
        if t == "break":
            tok = self._advance()
            self._expect(";")
            return ast.Break(tok.line, tok.col)
        if t == "continue":
            tok = self._advance()
            self._expect(";")
            return ast.Continue(tok.line, tok.col)
        return self._expr_statement()

    def _block_body(self):
        """消费 '{' ... '}'，返回块内语句列表。"""
        self._expect("{")
        statements = []
        while not self._check("}"):
            if self._check("EOF"):
                raise ParseError(self._current(), '缺少 "}"')
            statements.append(self._statement())
        self._expect("}")
        return statements

    def _block_statement(self):
        tok = self._current()
        return ast.Block(self._block_body(), tok.line, tok.col)

    def _let_decl(self):
        tok = self._expect("let")
        name = self._expect("IDENT").value
        self._expect("=")
        value = self._expression()
        self._expect(";")
        return ast.Let(name, value, tok.line, tok.col)

    def _fun_decl(self):
        tok = self._expect("fun")
        name = self._expect("IDENT").value
        self._expect("(")
        params = []
        if not self._check(")"):
            while True:
                param_tok = self._expect("IDENT")
                param = param_tok.value
                if param in params:
                    raise ParseError(param_tok, f"参数 {param} 重复")
                params.append(param)
                if not self._match(","):
                    break
        self._expect(")")
        body = self._block_body()
        return ast.Fun(name, params, body, tok.line, tok.col)

    def _struct_decl(self):
        tok = self._expect("struct")
        name = self._expect("IDENT").value
        self._expect("{")
        fields = []
        while not self._check("}"):
            field_tok = self._expect("IDENT")
            field = field_tok.value
            if field in fields:
                raise ParseError(field_tok, f"字段 {field} 重复")
            fields.append(field)
            if self._match(","):
                continue
            break
        if not fields:
            raise ParseError(self._current(), "struct 至少需要一个字段")
        self._expect("}")
        return ast.Struct(name, fields, tok.line, tok.col)

    def _return_statement(self):
        tok = self._expect("return")
        value = None if self._check(";") else self._expression()
        self._expect(";")
        return ast.Return(value, tok.line, tok.col)

    def _if_statement(self):
        tok = self._expect("if")
        condition = self._expression()
        then_body = self._block_body()
        else_body = None
        if self._match("else"):
            if self._check("if"):
                else_body = [self._if_statement()]
            else:
                else_body = self._block_body()
        return ast.If(condition, then_body, else_body, tok.line, tok.col)

    def _while_statement(self):
        tok = self._expect("while")
        condition = self._expression()
        body = self._block_body()
        return ast.While(condition, body, tok.line, tok.col)

    def _for_statement(self):
        tok = self._expect("for")
        self._expect("(")
        # 区间 for：(let)? IDENT in
        is_let = self._check("let")
        offset = 1 if is_let else 0
        if (self._peek(offset).type == "IDENT"
                and self._peek(offset + 1).type == "in"):
            name_tok = self._peek(offset)
            if is_let:
                self._advance()  # let
            name = self._expect("IDENT").value
            self._expect("in")
            interval = self._interval()
            self._expect(")")
            body = self._block_body()
            return ast.ForRange(name, interval, body, is_let,
                                tok.line, tok.col,
                                name_tok.line, name_tok.col)

        # C 风格 for
        if self._match(";"):
            init = None
        elif self._check("let"):
            init = self._let_decl()  # 自带分号
        else:
            init = self._expr_statement()
        condition = None if self._check(";") else self._expression()
        self._expect(";")
        update = None if self._check(")") else self._expression()
        self._expect(")")
        body = self._block_body()
        return ast.ForC(init, condition, update, body, tok.line, tok.col)

    def _interval(self):
        open_tok = self._current()
        if open_tok.type == "[":
            left_inclusive = True
        elif open_tok.type == "(":
            left_inclusive = False
        else:
            raise ParseError(open_tok, "区间应以 [ 或 ( 开始")
        self._advance()
        start = self._expression()
        self._expect(",")
        end = self._expression()
        close = self._advance()
        if close.type == "]":
            right_inclusive = True
        elif close.type == ")":
            right_inclusive = False
        else:
            raise ParseError(close, "区间应以 ] 或 ) 结束")
        return ast.Interval(start, end, left_inclusive, right_inclusive,
                            open_tok.line, open_tok.col)

    def _expr_statement(self):
        expr = self._expression()
        self._expect(";")
        return ast.ExprStmt(expr, expr.line, expr.col)

    # ---------- 表达式（优先级从低到高） ----------

    def _expression(self):
        return self._assignment()

    def _assignment(self):
        expr = self._or()
        if self._match("="):
            value = self._assignment()
            if not isinstance(expr, (ast.Var, ast.Index, ast.Get)):
                raise ParseError(self._current(), "赋值目标非法")
            return ast.Assign(expr, value, expr.line, expr.col)
        return expr

    def _or(self):
        expr = self._and()
        while self._match("or"):
            right = self._and()
            expr = ast.Logical("or", expr, right, expr.line, expr.col)
        return expr

    def _and(self):
        expr = self._equality()
        while self._match("and"):
            right = self._equality()
            expr = ast.Logical("and", expr, right, expr.line, expr.col)
        return expr

    def _binary(self, next_level, ops):
        expr = next_level()
        while self._current().type in ops:
            op_tok = self._advance()
            right = next_level()
            expr = ast.Binary(op_tok.type, expr, right, expr.line, expr.col)
        return expr

    def _equality(self):
        return self._binary(self._comparison, ("==", "!="))

    def _comparison(self):
        return self._binary(self._additive, ("<", "<=", ">", ">="))

    def _additive(self):
        return self._binary(self._multiplicative, ("+", "-"))

    def _multiplicative(self):
        return self._binary(self._unary, ("*", "/", "%"))

    def _unary(self):
        if self._check("-") or self._check("not"):
            op = self._advance()
            return ast.Unary(op.type, self._unary(), op.line, op.col)
        return self._postfix()

    def _postfix(self):
        expr = self._primary()
        while True:
            if self._match("("):
                args = []
                if not self._check(")"):
                    while True:
                        args.append(self._expression())
                        if not self._match(","):
                            break
                self._expect(")")
                expr = ast.Call(expr, args, expr.line, expr.col)
            elif self._match("["):
                start = self._expression()
                if self._match(":"):
                    end = self._expression()
                    self._expect("]")
                    expr = ast.Slice(expr, start, end, expr.line, expr.col)
                else:
                    self._expect("]")
                    expr = ast.Index(expr, start, expr.line, expr.col)
            elif self._match("."):
                name = self._expect("IDENT").value
                expr = ast.Get(expr, name, expr.line, expr.col)
            else:
                return expr

    def _primary(self):
        tok = self._current()
        t = tok.type
        if t == "NUMBER":
            self._advance()
            return ast.Number(tok.value, tok.line, tok.col)
        if t == "STRING":
            self._advance()
            return ast.String(tok.value, tok.line, tok.col)
        if t == "true":
            self._advance()
            return ast.Bool(True, tok.line, tok.col)
        if t == "false":
            self._advance()
            return ast.Bool(False, tok.line, tok.col)
        if t == "null":
            self._advance()
            return ast.Null(tok.line, tok.col)
        if t == "IDENT":
            self._advance()
            return ast.Var(tok.value, tok.line, tok.col)
        if t == "[":
            self._advance()
            elements = []
            if not self._check("]"):
                while True:
                    elements.append(self._expression())
                    if self._match(","):
                        if self._check("]"):
                            break
                        continue
                    break
            self._expect("]")
            return ast.Array(elements, tok.line, tok.col)
        if t == "(":
            self._advance()
            expr = self._expression()
            self._expect(")")
            return expr
        raise ParseError(tok, "此处应为表达式")


def parse(source):
    return Parser(tokenize(source)).parse()
