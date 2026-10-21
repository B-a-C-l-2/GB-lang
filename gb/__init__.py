"""GB 语言解释器。"""

import sys

# v0.4.3：int 精度随宿主、无溢出（design §5）。Python 3.11+ 默认限制
# int 与字符串互转最多 4300 位，会让大整数字面量、int() 与大整数
# print/str 泄漏裸 ValueError；解除该限制。
if hasattr(sys, "set_int_max_str_digits"):
    sys.set_int_max_str_digits(0)
