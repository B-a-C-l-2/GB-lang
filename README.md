# GB 语言

一门解释型通用脚本语言（个人 demo）。本文件只帮你快速上手；完整规则以 [`docs/design.md`](docs/design.md) 为准。

## 运行环境

- Python 3（无第三方依赖）
- 在项目根目录运行：

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

print("len =", len(a));           // 内建：print input len int float str push pop is_int is_float
let name = input("name? ");       // 读取一行输入；遇 EOF 返回 null
// 转换前探测：is_int(x) / is_float(x) 为 true，表示 int(x) / float(x) 不会报错
let raw = input("n? "); if (is_int(raw)) { print("翻倍 =", int(raw) * 2); }
```

运算要点：`/` 永远得到浮点数（`3 / 2 == 1.5`）；`%` 同 Python（余数随除数）；只有 `false` 和 `null` 为假（`0`、`""`、空数组都为真）；没有 `++`、`+=`，自增写成 `i = i + 1`；`and`/`or` 短路，且结果恒为布尔。

## 容易踩的几个点

- 漏分号；给没 `let` 过的变量赋值。
- 下标必须是 int，负下标是运行时错误；切片端点必须非负，正越界才自动钳制到长度。
- `for (let x in [1, 2])` 是区间 1..2，不是遍历两元素数组——要遍历请先赋给变量。
- 数组遍历是**快照遍历**：循环前浅拷贝一次，循环体里的 `push`/`pop`/清空不影响本轮。
- `not` 只作用于紧跟的操作数：`not a == b` 等价于 `(not a) == b`。
- 比较不能连写：`1 < 2 < 3` 会按 `(1 < 2) < 3` 报类型错误。

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

词法/语法/运行时错误都输出到 stderr，**带行列号和出错源码行**，退出码非 0：

```
运行时错误（第 2 行，第 7 列）：下标越界
print(a[5]);
      ^
```

语法错误还会指出实际遇到的 token（文件末尾时显示「文件末尾」）。运行时错误发生在函数调用中时，下方附最近至多 5 帧调用栈（由近及远）：

```
运行时错误（第 1 行，第 22 列）：除数为零
fun inner() { return 1 / 0; }
                   ^
 在 inner（第 2 行，第 22 列）调用
 在 outer（第 3 行，第 7 列）调用
```

`Ctrl+C` 中断会静默退出（退出码 130）。

## 开发与测试

```bash
python -m gb tests/selftest.gb          # 语言功能自测（黑盒，用 GB 写，断言数见输出）
python -m unittest discover -s tests    # 词法/语法/运行时错误与 CLI 端到端
```

`selftest.gb` 覆盖语言的全部公开功能：字面量与显示格式、作用域、算术与比较、逻辑短路、字符串、数组、切片、struct、四种循环、break/continue、函数与闭包、声明提升、内建函数、求值顺序。全部通过时退出码为 0，有失败时打印 `[FAIL]` 项并以退出码 1 结束。一条命令跑完全部测试：

```bash
python -m gb tests/selftest.gb && python -m unittest discover -s tests
```

与等价 Python 实现的性能对比（同一批工作负载，先比校验和再比耗时）：

```bash
python benchmarks/compare.py            # GB / Python 单次计算耗时与倍率
```

测量方法与结果记录在 [`benchmarks/README.md`](benchmarks/README.md)。

源码结构：`gb/lexer.py`（词法）→ `gb/ast.py`（语法树）→ `gb/parser.py`（语法）→ `gb/interpreter.py`（求值）→ `gb/builtins.py`（内建），入口 `gb/__main__.py`。
