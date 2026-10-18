"""GB 语法分析器：Token 列表 -> AST。"""

from gb.lexer import tokenize
from gb import ast


class ParseError(Exception):
    def __init__(self, token, message):
        super().__init__(f"语法错误（第 {token.line} 行）：{message}")
        self.line = token.line


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

    def _expect(self, type):
        if self._check(type):
            return self._advance()
        raise ParseError(self._current(), f"此处应为 {type}")

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
            self._advance()
            self._expect(";")
            return ast.Break()
        if t == "continue":
            self._advance()
            self._expect(";")
            return ast.Continue()
        return self._expr_statement()

    def _block_body(self):
        """假设 '{' 尚未消费，返回块内语句列表。"""
        self._expect("{")
        statements = []
        while not self._check("}"):
            if self._check("EOF"):
                raise ParseError(self._current(), "缺少 }")
            statements.append(self._statement())
        self._expect("}")
        return statements

    def _block_statement(self):
        return ast.Block(self._block_body())

    def _let_decl(self):
        self._expect("let")
        name = self._expect("IDENT").value
        self._expect("=")
        value = self._expression()
        self._expect(";")
        return ast.Let(name, value)

    def _fun_decl(self):
        self._expect("fun")
        name = self._expect("IDENT").value
        self._expect("(")
        params = []
        if not self._check(")"):
            while True:
                param = self._expect("IDENT").value
                if param in params:
                    raise ParseError(self._current(), f"参数 {param} 重复")
                params.append(param)
                if not self._match(","):
                    break
        self._expect(")")
        body = self._block_body()
        return ast.Fun(name, params, body)

    def _struct_decl(self):
        self._expect("struct")
        name = self._expect("IDENT").value
        self._expect("{")
        fields = []
        while not self._check("}"):
            field = self._expect("IDENT").value
            if field in fields:
                raise ParseError(self._current(), f"字段 {field} 重复")
            fields.append(field)
            if self._match(","):
                continue
            break
        if not fields:
            raise ParseError(self._current(), "struct 至少需要一个字段")
        self._expect("}")
        return ast.Struct(name, fields)

    def _return_statement(self):
        self._expect("return")
        value = None if self._check(";") else self._expression()
        self._expect(";")
        return ast.Return(value)

    def _if_statement(self):
        self._expect("if")
        condition = self._expression()
        then_body = self._block_body()
        else_body = None
        if self._match("else"):
            if self._check("if"):
                else_body = [self._if_statement()]
            else:
                else_body = self._block_body()
        return ast.If(condition, then_body, else_body)

    def _while_statement(self):
        self._expect("while")
        condition = self._expression()
        body = self._block_body()
        return ast.While(condition, body)

    def _for_statement(self):
        self._expect("for")
        self._expect("(")
        # 区间 for：let IDENT in
        if (self._check("let") and self._peek(1).type == "IDENT"
                and self._peek(2).type == "in"):
            self._advance()  # let
            name = self._expect("IDENT").value
            self._expect("in")
            interval = self._interval()
            self._expect(")")
            body = self._block_body()
            return ast.ForRange(name, interval, body)

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
        return ast.ForC(init, condition, update, body)

    def _interval(self):
        if self._check("["):
            left_inclusive = True
        elif self._check("("):
            left_inclusive = False
        else:
            raise ParseError(self._current(), "区间应以 [ 或 ( 开始")
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
        return ast.Interval(start, end, left_inclusive, right_inclusive)

    def _expr_statement(self):
        expr = self._expression()
        self._expect(";")
        return ast.ExprStmt(expr)

    # ---------- 表达式（优先级从低到高） ----------

    def _expression(self):
        return self._assignment()

    def _assignment(self):
        expr = self._or()
        if self._match("="):
            value = self._assignment()
            if not isinstance(expr, (ast.Var, ast.Index, ast.Get)):
                raise ParseError(self._current(), "赋值目标非法")
            return ast.Assign(expr, value)
        return expr

    def _or(self):
        expr = self._and()
        while self._match("or"):
            right = self._and()
            expr = ast.Logical("or", expr, right)
        return expr

    def _and(self):
        expr = self._equality()
        while self._match("and"):
            right = self._equality()
            expr = ast.Logical("and", expr, right)
        return expr

    def _binary(self, next_level, ops):
        expr = next_level()
        while self._current().type in ops:
            op = self._advance().type
            right = next_level()
            expr = ast.Binary(op, expr, right)
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
            op = self._advance().type
            return ast.Unary(op, self._unary())
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
                expr = ast.Call(expr, args)
            elif self._match("["):
                start = self._expression()
                if self._match(":"):
                    end = self._expression()
                    self._expect("]")
                    expr = ast.Slice(expr, start, end)
                else:
                    self._expect("]")
                    expr = ast.Index(expr, start)
            elif self._match("."):
                name = self._expect("IDENT").value
                expr = ast.Get(expr, name)
            else:
                return expr

    def _primary(self):
        tok = self._current()
        t = tok.type
        if t == "NUMBER":
            self._advance()
            return ast.Number(tok.value)
        if t == "STRING":
            self._advance()
            return ast.String(tok.value)
        if t == "true":
            self._advance()
            return ast.Bool(True)
        if t == "false":
            self._advance()
            return ast.Bool(False)
        if t == "null":
            self._advance()
            return ast.Null()
        if t == "IDENT":
            self._advance()
            return ast.Var(tok.value)
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
            return ast.Array(elements)
        if t == "(":
            self._advance()
            expr = self._expression()
            self._expect(")")
            return expr
        raise ParseError(tok, "此处应为表达式")


def parse(source):
    return Parser(tokenize(source)).parse()
