# GB 语言开发指南

本文面向使用 GB 编写程序的开发者，介绍从运行环境、编写应用到自动测试的流程。
详细语法见 [语言语法与使用规范](language-reference.md)；供编程 Agent 直接使用的简明指南是 [agent-guide.md](agent-guide.md)。

## 1. 环境与第一个程序

安装 Python 3，解释器仅使用标准库，无需安装第三方依赖。在项目根目录运行命令。
创建 UTF-8 文件 `hello.gb`：

```gb
let name = input("name? ");
if (name != null) {
    print("hello,", name);
}
```

```bash
python -m gb hello.gb
```

输入姓名并回车可看到问候。EOF 会使 input 返回 null，示例正常结束。
不要直接运行 `python gb/__main__.py`；使用 `python -m gb` 让包导入正确工作。

## 2. 写程序时需要掌握的规则

- 用 let 声明并初始化变量；语句用分号结束，语句块用花括号。
- 函数用 fun 定义，可递归；函数和 struct 在当前作用域入口注册，let 不提升。
- struct 保存固定字段的记录，数组保存多条记录；二者按引用传递。
- 没有 ++、+=，写 `i = i + 1`；没有字典、import 和异常捕获。
- 只有 false/null 为假，不能用 `if (len(a))` 判断数组非空，应写 `len(a) > 0`。
- 下标必须非负且不越界；切片 `[a:b]` 左闭右开，两端必须显式给出。
- 两元素数组先存变量再遍历，避免与区间语法混淆。

## 3. 完整的小应用示例

以下程序接受多条分数记录，输入空姓名结束，最后打印及格名单与平均分。
可以保存为 `scores.gb`，运行 `python -m gb scores.gb`。

```gb
struct Score { name, value }
let scores = [];

fun readScore() {
    while (true) {
        let raw = input("score (0-100): ");
        if (raw == null) { return null; }
        if (is_int(raw)) {
            let value = int(raw);
            if (value >= 0 and value <= 100) { return value; }
        }
        print("invalid score");
    }
}

while (true) {
    let name = input("name (empty to finish): ");
    if (name == null or name == "") { break; }
    let value = readScore();
    if (value == null) { break; }
    push(scores, Score(name, value));
}

if (len(scores) == 0) {
    print("no records");
} else {
    let sum = 0;
    for (let s in scores) {
        sum = sum + s.value;
        if (s.value >= 60) { print("pass:", s.name); }
    }
    print("average:", sum / len(scores));
}
```

输入 `Alice`、`80`、`Bob`、`50`，最后输入空姓名，将输出 Alice 及格和平均分 65.0。
这里先校验输入，再创建记录，避免 EOF 或非法输入留下不完整数据。
is_int 判断能否转换，不是检查原始类型：input 返回字符串，但数字字符串也能通过探测。

## 4. 组织一个较大的应用

推荐按“数据结构 → 输入校验 → 业务操作 → 菜单主循环”组织一个文件。
GB 没有 import，相关函数应放在同一源文件内。

1. 用 struct 定义记录，明确字段含义和有效范围。
2. 将重复的输入格式、范围和 EOF 判断抽为函数。
3. 将添加、查找、修改、删除等操作拆开；全部校验通过后再写入。
4. 菜单只负责分派，不混入所有业务细节。
5. 明确退出条件与数据生命周期。当前内建没有文件读写，内存数据退出后丢失。

数组删除任意位置可左移后续元素，最后 pop；排序可先 `a[0:len(a)]` 浅拷贝，
交换副本元素，避免改变原数组顺序。浅拷贝不会复制内部 struct，修改字段仍影响共享对象。
数组 for 遍历快照，适合稳定遍历；需要按索引修改时可用 C 风格 for。

完整参考应用：

```bash
python -m gb apps/grades/main.gb
```

应用支持录入、列表、学号查询、修改、确认删除、排名、统计和姓名查询。
说明见 [应用手册](../apps/grades/README.md)，协作过程见 [开发记录](../apps/grades/DEVELOPMENT.md)。

## 5. 编写自动黑盒测试

语言全部黑盒测试一个命令运行，不需要人工输入：

```bash
python -m gb tests/selftest.gb
```

自己的测试脚本也可以用 GB 编写。以下示例验证真实输入输出和错误退出：

```gb
let failed = 0;
fun check(name, actual, expected) {
    if (actual != expected) {
        failed = failed + 1;
        print("FAIL", name, "expected", expected, "actual", actual);
    }
}
let ok = run_gb("print(input());", "hello\n");
check("stdout", ok.stdout, "hello\n");
check("stderr", ok.stderr, "");
check("exit", ok.exit_code, 0);
let bad = run_gb("1 / 0;");
check("error exit", bad.exit_code, 1);
check("has diagnostic", len(bad.stderr) > 0, true);
if (failed > 0) {
    // 当前无 exit 内建，失败时触发运行时错误使测试命令非零退出。
    let stop = 1 / 0;
}
print("all passed");
```

run_gb 接受源码字符串和可选输入字符串；结果提供 stdout、stderr、exit_code。
语法错误放在子程序字符串内，不会破坏父测试脚本。输出预期应包含空格与换行。
该接口每次启动独立进程，5 秒超时会使接口报错，适用于短小功能测试。
GB 没有读文件内建；现有完整应用的文件级端到端测试使用外部运行器：

```bash
python apps/grades/test_app.py
```

额外的解释器 Python 回归测试：

```bash
python -m unittest discover -s tests
```

## 6. 诊断与排错

诊断通常包含错误类别、行列号、源码及 ^。先定位首个错误，再缩小程序复现。

| 现象 | 检查方向 |
|---|---|
| 语法错误，提示缺少分号或括号 | 语句结尾与括号配对；控制体需要花括号 |
| 变量未定义 | 是否先 let；变量是否只存在于内层块或循环 |
| 转换失败 | 先探测 is_int/is_float，检查是否有空白、空串或 EOF |
| 下标越界 | 保证 `i >= 0 and i < len(a)`；检查删除后长度 |
| 程序意外继续循环 | 0 和空字符串为真，应使用明确比较 |
| 参数数量错误 | 调用实参与函数形参或 struct 字段数是否一致 |

函数中的错误会附最近至多 5 帧调用栈。文件读取错误及部分深度错误可能没有行列号。
GB 没有 try/catch；正常退出码为 0，语言错误通常为 1，Ctrl+C 为 130。
遇到解释器内部异常可在 PowerShell 临时设置 `$env:GB_DEBUG='1'` 后复现；
排查后使用 `Remove-Item Env:GB_DEBUG` 清除，以免影响之后的运行。

## 7. 性能测试与开发记录

```bash
python benchmarks/compare.py --runs 3
```

工具先比较 GB 和 Python 工作负载的输出校验和，再比较耗时。GB 用差分估计，
Python 在进程内计时，重复取最小值。方法及结果见 [性能报告](../benchmarks/README.md)。
业务开发先保证正确性，不必为微基准数字引入复杂优化。

使用 Agent 辅助时，先给明确功能与验收输入，再按小步修改、运行、提交的流程迭代。
记录实际生成与修订、执行过的测试和已知限制，不把未运行的验证写为通过。
修改本仓库时遵循根目录 AGENT.md 的分支与提交规则；用 GB 编写应用无需阅读设计历史。
