"""GB 命令行入口：python -m gb <file.gb>"""

import sys

from gb.lexer import LexerError
from gb.parser import parse, ParseError
from gb.interpreter import Interpreter, make_global_env
from gb.builtins import GbError


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
    except (LexerError, ParseError) as e:
        print(e, file=sys.stderr)
        return 1

    interpreter = Interpreter(make_global_env())
    try:
        interpreter.run(module)
    except GbError as e:
        where = f"（第 {e.line} 行）" if e.line else ""
        print(f"运行时错误{where}：{e.message}", file=sys.stderr)
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
