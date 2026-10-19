"""GB 命令行入口：python -m gb <file.gb>"""

import sys

from gb.lexer import LexerError
from gb.parser import parse, ParseError
from gb.interpreter import Interpreter, make_global_env
from gb.builtins import GbError


def _format_error(kind, message, source, line, col, got=None):
    """错误首行 + 源码行 + ^ 指示；无位置（line 为 0）时省略后两者。"""
    head = f"{kind}错误"
    if line:
        head += f"（第 {line} 行，第 {col} 列）"
    text = f"{head}：{message}"
    if got is not None:
        text += f"，遇到 {got}"
    if not line:
        return text
    lines = source.splitlines()
    if 1 <= line <= len(lines):
        src_line = lines[line - 1]
        # 列按码点计；Tab/宽字符可能错位（见 design.md 已知限制）
        pointer = " " * (col - 1) + "^"
        text += "\n" + src_line + "\n" + pointer
    return text


def main(argv):
    if len(argv) != 2:
        print("用法：python -m gb <file.gb>", file=sys.stderr)
        return 1

    try:
        with open(argv[1], encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        print(f"无法读取文件：{e}", file=sys.stderr)
        return 1

    try:
        module = parse(source)
    except LexerError as e:
        print(_format_error("词法", e.message, source, e.line, e.col),
              file=sys.stderr)
        return 1
    except ParseError as e:
        print(_format_error("语法", e.message, source, e.line, e.col, e.got),
              file=sys.stderr)
        return 1

    interpreter = Interpreter(make_global_env())
    try:
        interpreter.run(module)
    except GbError as e:
        print(_format_error("运行时", e.message, source, e.line, e.col),
              file=sys.stderr)
        return 1
    except RecursionError:
        print("运行时错误：调用栈过深（可能存在无限递归）", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    # Windows 控制台默认 GBK，统一为 UTF-8 输入输出
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv))
