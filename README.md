# GB 语言

一门解释型通用脚本语言（个人 demo）。完整设计见 [`docs/design.md`](docs/design.md)，本文件只帮你快速上手。

## 运行环境

- Python 3（无第三方依赖）
- 运行程序（在项目根目录）：

  ```bash
  python -m gb examples/example.gb
  ```

  GB 源文件后缀约定为 `.gb`。

## 5 分钟语法速览

```
// 注释以 // 开始；语句以分号结束

let n = 10;                 // 变量（必须有初值，块级作用域）
let pi = 3.14;
let s = "hello";
let a = [1, 2, 3];          // 数组
let p = Point(3, 4);        // struct 实例（见下）

print(a[0]);                // 下标从 0 开始；a[0:2] 是切片 [1, 2]
print(s[1:4]);              // 字符串也可下标和切片：ell

if (n > 5) { print("big"); } else { print("small"); }

while (n > 0) { n = n - 1; }

for (let i = 0; i < 3; i = i + 1) { print(i); }   // C 风格 for
for (let i in [1, 5]) { print(i); }               // 区间 for：1..5
for (let x in [10, 20, 30]) { print(x); }         // 数组遍历 for（快照遍历）
// 两种 for 的循环变量都可省略 let，改为逐轮写入外层已有变量：
//   let i = 0; for (i in [1, 5]) { }   循环后 i == 5（变量须已 let 过）
// 四种区间：[1,5] 1..5 | [1,5) 1..4 | (0,5] 1..5 | (0,5) 1..4

fun add(a, b) { return a + b; }   // 函数（声明提升：支持前向调用、递归与相互递归）

struct Point { x, y }             // 纯数据结构，自动生成 Point(x, y)
fun dist2(p) { return p.x * p.x + p.y * p.y; }

print("len =", len(a));           // 内建：print input len int float str push pop
let name = input("name? ");       // 读取一行输入；遇 EOF 返回 null
```

运算要点：`/` 永远得到浮点数（`3 / 2 == 1.5`）；`%` 同 Python（余数随除数）；只有 `false` 和 `null` 为假（`0`、`""`、空数组都为真）；没有 `++`、`+=`，自增写成 `i = i + 1`；`and`/`or` 短路且结果恒为布尔；浮点字面量、`float()` 转换或运算结果为 inf/nan 时报运行时错误「浮点溢出」（int 无溢出，与字符串互转也不受宿主位数限制）。

## 自带示例

```bash
python -m gb examples/example.gb      # 功能巡礼：struct、区间 for、切片
python -m gb examples/fizzbuzz.gb     # FizzBuzz
python -m gb examples/fibonacci.gb    # 数组 + push + 区间 for
python -m gb examples/bubblesort.gb   # 交互式：输入长度与元素，输出排序结果（需要 stdin）
```

## 自己动手（建议练习）

1. **打招呼**：用 `input` 读入名字，输出 `hello, 名字`。
2. **素数表**：写 `fun isPrime(n)`，打印 `[1, 30]` 中的全部素数（提示：`while` 试除到 `d * d > n`）。
3. **成绩判定**：自定义 `struct Score { name, value }`，用数组装几条成绩，遍历并打印 value ≥ 60 的名字。

## 报错怎么看

- 词法/语法/运行时错误都输出到 stderr，**带行列号和出错源码行**，退出码非 0，例如：

  ```
  运行时错误（第 2 行，第 7 列）：下标越界
  print(a[5]);
        ^
  ```

  语法错误还会指出实际遇到的 token（文件末尾时显示「文件末尾」）。

- 运行时错误发生在函数调用中时，会在下方附加最近至多 5 帧调用栈（由近及远）：

  ```
  运行时错误（第 1 行，第 22 列）：除数为零
  fun inner() { return 1 / 0; }
                     ^
    在 inner（第 2 行，第 22 列）调用
    在 outer（第 3 行，第 7 列）调用
  ```

- 若看到「内部错误（宿主异常）：类型: 消息」，说明解释器自身有缺陷；设置环境变量 `GB_DEBUG=1` 可保留完整 traceback 便于定位。`Ctrl+C` 中断会静默退出（退出码 130）。
- 常见坑：漏分号；给未 `let` 的变量赋值；用浮点数当下标；切片端点为负（`a[0:-1]` 报错，越界正值才会被钳制）；省略 `let` 的区间 for 变量必须是外层已声明的变量。
- `not` 只作用于紧跟的操作数：`not a == b` 等价于 `(not a) == b`（与 Python 不同）；比较不能连写，`1 < 2 < 3` 会按 `(1 < 2) < 3` 报类型错误。
- 浮点按宿主显示：`str` 可能输出 `1e+16` 这类科学计数法，而 `float("1e+16")` 按严格字面量规则报错——`str` 的浮点输出不保证能被 `float` 回读。
- 数组字面量可写尾逗号（`[1, 2, ]` 合法），但函数调用的实参列表不行（`f(1, 2, )` 是语法错误）。
- 数组遍历是**快照遍历**：`for (let x in a)` 循环前对 `a` 浅拷贝一份，循环体内的 `push`/`pop`/清空都不影响本轮遍历。注意 `in [a, b]` 两元素形状**且后面直接跟 for 头的 `)`** 时是区间——`for (let x in [1, 2])` 是区间 1..2，要遍历两元素数组须先赋给变量；后接后缀/运算符（如 `[1, 2][0:1]`、`[1, 2] + 3`）则按一般表达式。
- 禁止循环引用：`let a = []; push(a, a);` 之后对 `a` 做 `print`/`str`/`==`/大小比较会报「存在循环引用」。
- `int`/`float` 解析字符串时只认 GB 数值字面量（可带前导 `-`）：`int("１２")`、`int("1_0")`、`int(" 12 ")`、`float("nan")`、`float("1e3")` 都是运行时错误。
- 源文件必须是 UTF-8 编码，可带 BOM（GBK 文件会在入口报「源文件不是有效的 UTF-8」）；stdin 也按 UTF-8 解码（否则报「输入不是有效的 UTF-8」）；`int(inf)`、`int(nan)`、把超大整数转 `float` 都是运行时错误。
- `fun`/`struct` 声明会被提升到所在作用域开头，因此可以前向调用和相互递归；但 `let` 不提升。内建函数名（如 `len`）可用同名声明遮蔽，不能裸赋值改写。

## 开发与测试

```bash
python -m unittest discover -s tests    # 运行全部测试
```

源码结构：`gb/lexer.py`（词法）→ `gb/ast.py`（语法树）→ `gb/parser.py`（语法）→ `gb/interpreter.py`（求值）→ `gb/builtins.py`（内建），入口 `gb/__main__.py`。
