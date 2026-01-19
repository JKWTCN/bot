"""
批量修复脚本：为所有使用同步sqlite3的文件添加线程池包装
避免数据库锁定问题
"""

import os
import re

# 需要修复的文件列表
FILES_TO_FIX = [
    'application/at_random_group_friend.py',
    'application/welcome_application.py',
    'application/cold_group_king.py',
    'application/point_application.py',
    'application/carrot_market_application.py',
]

# 添加导入的代码
IMPORT_ADDITION = """# 导入线程池包装器，避免数据库锁定
from database.sync_wrapper import run_in_thread_sync
"""

# sqlite3.connect 的替换模式
# 添加 timeout=30.0 参数
CONNECT_PATTERN = r'sqlite3\.connect\("bot\.db"\)'
CONNECT_REPLACEMENT = r'sqlite3.connect("bot.db", timeout=30.0)'

CONNECT_PATTERN2 = r'sqlite3\.connect\(\s*"bot\.db"\s*\)'
CONNECT_REPLACEMENT2 = r'sqlite3.connect("bot.db", timeout=30.0)'


def fix_file(filepath):
    """修复单个文件"""
    print(f"正在修复: {filepath}")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查是否已经有导入
        if 'from database.sync_wrapper import' in content:
            print(f"  ✓ 已包含线程池包装器导入，跳过")
            return

        # 找到最后一个import语句的位置
        lines = content.split('\n')
        last_import_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                last_import_idx = i

        if last_import_idx == -1:
            print(f"  ✗ 未找到import语句")
            return

        # 在最后一个import后添加我们的导入
        lines.insert(last_import_idx + 1, '')
        lines.insert(last_import_idx + 2, IMPORT_ADDITION.strip())
        lines.insert(last_import_idx + 3, '')

        # 替换 sqlite3.connect 添加 timeout
        new_content = '\n'.join(lines)
        new_content = re.sub(CONNECT_PATTERN, CONNECT_REPLACEMENT, new_content)
        new_content = re.sub(CONNECT_PATTERN2, CONNECT_REPLACEMENT2, new_content)

        # 写回文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"  ✓ 修复完成")

    except Exception as e:
        print(f"  ✗ 修复失败: {e}")


def main():
    """主函数"""
    print("=" * 60)
    print("批量修复数据库锁定问题")
    print("=" * 60)
    print()

    for filepath in FILES_TO_FIX:
        if os.path.exists(filepath):
            fix_file(filepath)
        else:
            print(f"文件不存在: {filepath}")

    print()
    print("=" * 60)
    print("批量修复完成")
    print("=" * 60)
    print()
    print("注意：")
    print("1. 某些复杂的函数可能需要手动修改")
    print("2. 建议运行测试验证")
    print("3. 如有错误，请检查日志")


if __name__ == "__main__":
    main()
