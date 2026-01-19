"""
修复缩进错误脚本
将错误插入的导入语句移到文件顶部
"""

import re
import os

FILES_TO_FIX = [
    'application/welcome_application.py',
    'application/cold_group_king.py',
    'application/point_application.py',
    'application/carrot_market_application.py',
]

WRONG_IMPORT = "# 导入线程池包装器，避免数据库锁定\nfrom database.sync_wrapper import run_in_thread_sync"

def fix_file(filepath):
    """修复单个文件的缩进"""
    print(f"正在修复: {filepath}")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查是否有错误的导入
        if WRONG_IMPORT.split('\n')[0] not in content:
            print(f"  ✓ 无需修复")
            return

        # 移除错误位置的导入
        # 1. 移除单独的注释行和导入行
        lines = content.split('\n')
        new_lines = []

        # 首先收集需要添加到顶部的导入
        needs_import = False
        filtered_lines = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # 检查是否是错误插入的导入
            if line.strip() == "# 导入线程池包装器，避免数据库锁定":
                # 跳过注释行
                needs_import = True
                i += 1
                # 检查下一行是否是导入
                if i < len(lines) and 'from database.sync_wrapper import' in lines[i]:
                    i += 1  # 跳过导入行
                continue

            filtered_lines.append(line)
            i += 1

        # 在正确的位置添加导入（在所有import之后）
        if needs_import:
            # 找到最后一个import语句
            last_import_idx = -1
            for i, line in enumerate(filtered_lines):
                if line.strip().startswith('import ') or line.strip().startswith('from '):
                    last_import_idx = i

            if last_import_idx >= 0:
                # 在最后一个import后添加空行和导入
                filtered_lines.insert(last_import_idx + 1, '')
                filtered_lines.insert(last_import_idx + 2, '# 导入线程池包装器，避免数据库锁定')
                filtered_lines.insert(last_import_idx + 3, 'from database.sync_wrapper import run_in_thread_sync')

        # 写回文件
        new_content = '\n'.join(filtered_lines)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"  ✓ 修复完成")

    except Exception as e:
        print(f"  ✗ 修复失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    print("=" * 60)
    print("修复缩进错误")
    print("=" * 60)
    print()

    for filepath in FILES_TO_FIX:
        if os.path.exists(filepath):
            fix_file(filepath)
        else:
            print(f"文件不存在: {filepath}")

    print()
    print("=" * 60)
    print("修复完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
