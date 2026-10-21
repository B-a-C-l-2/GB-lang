"""GB 命令行入口：python -m gb <file.gb>"""

import sys
import unicodedata

from gb.lexer import LexerError
from gb.parser import parse, ParseError
from gb.interpreter import Interpreter, make_global_env
from gb.builtins import GbError


def _pointer_line(src_line, col):
    """v0.3：^ 按终端显示宽度对齐——出错列前的窄字符计 1 空格，
    东亚宽字符计 2 空格，Tab 展开到下一个 8 列制表位。
    （首行列号仍按字符数统计，Tab 计 1 列。）"""
    parts = []
    width = 0
    for ch in src_line[:col - 1]:
        if ch == "\t":
            n = 8 - width % 8
            parts.append(" " * n)
            width += n
        elif unicodedata.east_asian_width(ch) in ("W", "F"):
            parts.append("  ")
            width += 2
        else:
            parts.append(" ")
            width += 1
    return "".join(parts) + "^"


def _format_frames(frames):
    """v0.3：由近及远打印最近至多 5 帧调用栈；无帧时返回空串。"""
    if not frames:
        return ""
    lines = [f"  在 {name}（第 {line} 行，第 {col} 列）调用"
             for name, line, col in reversed(frames[-5:])]
    return "\n" + "\n".join(lines)


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
        text += "\n" + src_line + "\n" + _pointer_line(src_line, col)
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
    except UnicodeDecodeError as e:
        # v0.4.1：非 UTF-8 源文件（如 GBK），文件级错误无行列号
        print(f"源文件不是有效的 UTF-8：{e}", file=sys.stderr)
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
    except RecursionError:
        # v0.3.1：解析阶段深层嵌套（约百层括号/数组）耗尽 Python 调用栈，
        # 与运行时「调用栈过深」一样属无位置错误，不输出 traceback
        print("语法错误：嵌套过深（可能存在过深的括号或数组嵌套）",
              file=sys.stderr)
        return 1

    interpreter = Interpreter(make_global_env())
    try:
        interpreter.run(module)
    except GbError as e:
        text = _format_error("运行时", e.message, source, e.line, e.col)
        text += _format_frames(getattr(e, "gb_frames", None))
        print(text, file=sys.stderr)
        return 1
    except RecursionError as e:
        text = "运行时错误：调用栈过深（可能是无限递归或过深的数据嵌套）"
        text += _format_frames(getattr(e, "gb_frames", None))
        print(text, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    # Windows 控制台默认 GBK，统一为 UTF-8 输入输出
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv))
