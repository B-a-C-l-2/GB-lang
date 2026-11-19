"""固定输入驱动 GB 应用，仅观察输出和退出码。"""
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]

def run(data):
    p = subprocess.run([sys.executable, '-B', '-m', 'gb', 'apps/grades/main.gb'],
        cwd=ROOT, input=data, capture_output=True, text=True, encoding='utf-8', timeout=10)
    assert p.returncode == 0 and p.stderr == '', (p.returncode, p.stderr)
    assert p.stdout.endswith('再见\n')
    return p.stdout

# 增、查、改、排、统计、姓名检索、取消删除、确认删除、空表。
data = '\n'.join(['1','2','Bob','50','60','70','1','1','Alice','80','90','100',
    '1','1','2','3','99','3','1','4','2','100','100','100','6','7','8','Alice',
    '5','2','n','5','2','y','5','1','y','2','7','0']) + '\n'
out = run(data)
for expected in ['学号已存在','未找到学生','修改成功','平均总分 285.0',
    '全科及格人数 2','匹配人数 1','已取消','删除成功','暂无记录']:
    assert expected in out, expected
rank = out[out.index('总分降序'):]
assert rank.index('2 Bob 100 100 100 300') < rank.index('1 Alice 80 90 100 270')
# 格式、范围、空姓名与 EOF；每个输入前缀都应安全退出。
invalid = 'bad\n9\n1\n0\n1\n\nTest\n101\n90\n80\n70\n2\n0\n'
out = run(invalid)
assert '输入不能为空' in out and '请输入范围内整数' in out
assert '1 Test 90 80 70 240' in out
for prefix in ['', '1\n', '1\n1\n', '1\n1\nA\n', '1\n1\nA\n90\n']:
    out = run(prefix)
    assert '录入成功' not in out
print('PASS: application workflow, validation, ranking, EOF (7 sessions)')
