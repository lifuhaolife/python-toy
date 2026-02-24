"""
测试繁体转简体功能
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from asr_client import OptimizedASRClient

# 创建测试实例
asr = OptimizedASRClient()

# 测试用例
test_cases = [
    # (繁体，期望简体)
    ("你好嗎", "你好吗"),
    ("我們", "我们"),
    ("這是什麼", "这是什么"),
    ("說話", "说话"),
    ("時間", "时间"),
    ("會來", "会来"),
    ("現在", "现在"),
    ("點兒", "点儿"),
    ("讓請", "让请"),
    ("問道", "问道"),
    ("覺得", "觉得"),
    ("想要", "想要"),
    ("歡迎", "欢迎"),
    ("謝謝", "谢谢"),
    ("對於", "对于"),
    ("沒有", "没有"),
    ("邊裏", "边里"),
    ("著過", "着过"),
    ("已經", "已经"),
    ("嗎呢吧", "吗呢吧"),
]

print("=" * 60)
print("繁体转简体测试")
print("=" * 60)

passed = 0
failed = 0

for traditional, expected in test_cases:
    result = asr._traditional_to_simplified(traditional)
    status = "PASS" if result == expected else "FAIL"
    
    if result == expected:
        passed += 1
    else:
        failed += 1
    
    print(f"{status} {traditional} -> {result} (期望：{expected})")

print("\n" + "=" * 60)
print(f"测试结果：{passed} 通过，{failed} 失败")
print("=" * 60)

# 测试完整后处理
print("\n完整后处理测试:")
print("-" * 60)

full_test_cases = [
    "你好嗎？我們一起來玩吧！",
    "這是什麼東西啊？",
    "說話清楚一點兒，",
    "時間會證明一切的。。。。",
]

for text in full_test_cases:
    result = asr._postprocess_text(text)
    print(f"原始：{text}")
    print(f"处理：{result}")
    print()
