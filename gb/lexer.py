"""GB 词法分析器：源码文本 -> Token 列表。"""

KEYWORDS = {
    "let", "fun", "return", "if", "else", "while", "for", "in",
    "break", "continue", "struct", "true", "false", "null",
    "and", "or", "not",
}

_ESCAPES = {"n": "\n", "t": "\t", "\\": "\\", '"': '"'}


class LexerError(Exception):
    def __init__(self, line, col, message):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col


class Token:
    __slots__ = ("type", "value", "line", "col")

    def __init__(self, type, value, line, col):
        self.type = type    # 关键字/运算符时 type 即其字面文本
        self.value = value  # NUMBER: int/float；STRING: str；IDENT: 名称；其余同 type
        self.line = line
        self.col = col      # 首字符列号，从 1 开始（按 Unicode 码点计）

    def __repr__(self):
        return f"Token({self.type!r}, {self.value!r}, line={self.line}, col={self.col})"


def _is_ident_start(c):
    return "a" <= c <= "z" or "A" <= c <= "Z" or c == "_"


def _is_ident_part(c):
    return _is_ident_start(c) or "0" <= c <= "9"


def _is_digit(c):
    return "0" <= c <= "9"


def tokenize(source):
    tokens = []
    n = len(source)
    i = 0
    line = 1
    col = 1

    while i < n:
        c = source[i]

        if c == " " or c == "\t" or c == "\r":
            i += 1
            col += 1
        elif c == "\n":
            line += 1
            col = 1
            i += 1
        elif c == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                i += 1
                col += 1
        elif _is_ident_start(c):
            start, start_col = i, col
            while i < n and _is_ident_part(source[i]):
                i += 1
                col += 1
            word = source[start:i]
            ttype = word if word in KEYWORDS else "IDENT"
            tokens.append(Token(ttype, word, line, start_col))
        elif _is_digit(c):
            start, start_col = i, col
            while i < n and _is_digit(source[i]):
                i += 1
                col += 1
            is_float = False
            # 浮点要求小数点后必须有数字
            if i + 1 < n and source[i] == "." and _is_digit(source[i + 1]):
                is_float = True
                i += 2
                col += 2
                while i < n and _is_digit(source[i]):
                    i += 1
                    col += 1
            text = source[start:i]
            value = float(text) if is_float else int(text)
            tokens.append(Token("NUMBER", value, line, start_col))
        elif c == '"':
            start_col = col
            i += 1
            col += 1
            chars = []
            while i < n and source[i] != '"':
                ch = source[i]
                if ch == "\n":
                    raise LexerError(line, col, "字符串未终止")
                if ch == "\\":
                    i += 1
                    col += 1
                    if i >= n:
                        raise LexerError(line, col, "字符串未终止")
                    esc = source[i]
                    if esc not in _ESCAPES:
                        raise LexerError(line, col, f"非法转义 \\{esc}")
                    chars.append(_ESCAPES[esc])
                else:
                    chars.append(ch)
                i += 1
                col += 1
            if i >= n:
                raise LexerError(line, col, "字符串未终止")
            i += 1  # 吃掉右引号
            col += 1
            tokens.append(Token("STRING", "".join(chars), line, start_col))
        else:
            two = source[i:i + 2]
            if two in ("==", "!=", "<=", ">="):
                tokens.append(Token(two, two, line, col))
                i += 2
                col += 2
            elif c in "+-*/%=<>(){}[],;:.":
                tokens.append(Token(c, c, line, col))
                i += 1
                col += 1
            elif c == "!":
                raise LexerError(line, col,
                                 "非法字符 '!'（逻辑非请使用 not）")
            else:
                raise LexerError(line, col, f"非法字符 {c!r}")

    tokens.append(Token("EOF", None, line, col))
    return tokens
