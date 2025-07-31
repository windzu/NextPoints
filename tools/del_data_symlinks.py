#!/usr/bin/env python3
"""
删除指定路径下所有软链接的脚本
支持递归删除和安全模式
"""

import argparse
import os
import sys
from pathlib import Path


def find_symlinks(directory, recursive=True):
    """
    查找目录中的所有软链接

    Args:
        directory (str): 要搜索的目录路径
        recursive (bool): 是否递归搜索子目录

    Returns:
        list: 软链接路径列表
    """
    symlinks = []
    directory = Path(directory)

    if not directory.exists():
        print(f"错误: 目录 '{directory}' 不存在")
        return symlinks

    if not directory.is_dir():
        print(f"错误: '{directory}' 不是一个目录")
        return symlinks

    try:
        if recursive:
            # 递归搜索所有文件和目录
            for item in directory.rglob("*"):
                if item.is_symlink():
                    symlinks.append(item)
        else:
            # 只搜索当前目录
            for item in directory.iterdir():
                if item.is_symlink():
                    symlinks.append(item)
    except PermissionError as e:
        print(f"权限错误: {e}")
    except Exception as e:
        print(f"搜索时发生错误: {e}")

    return symlinks


def delete_symlinks(symlinks, dry_run=False, interactive=False):
    """
    删除软链接

    Args:
        symlinks (list): 要删除的软链接列表
        dry_run (bool): 是否为试运行模式
        interactive (bool): 是否交互式确认

    Returns:
        tuple: (成功删除数量, 失败删除数量)
    """
    success_count = 0
    error_count = 0

    if not symlinks:
        print("未找到任何软链接")
        return success_count, error_count

    print(f"找到 {len(symlinks)} 个软链接:")

    for i, symlink in enumerate(symlinks, 1):
        print(f"  [{i}/{len(symlinks)}] {symlink}")

        # 交互式确认
        if interactive:
            response = input(f"是否删除 '{symlink}'? (y/N): ").strip().lower()
            if response not in ["y", "yes"]:
                print("  跳过")
                continue

        # 删除软链接
        if not dry_run:
            try:
                symlink.unlink()
                print(f"  ✓ 已删除")
                success_count += 1
            except PermissionError:
                print(f"  ✗ 权限不足")
                error_count += 1
            except FileNotFoundError:
                print(f"  ✗ 文件不存在")
                error_count += 1
            except Exception as e:
                print(f"  ✗ 删除失败: {e}")
                error_count += 1
        else:
            print(f"  [试运行] 将删除")

    return success_count, error_count


def main():
    parser = argparse.ArgumentParser(
        description="删除指定路径下的所有软链接",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python del_all_symbol_link.py /path/to/directory
  python del_all_symbol_link.py /path/to/directory --recursive
  python del_all_symbol_link.py /path/to/directory --dry-run
  python del_all_symbol_link.py /path/to/directory --interactive
  python del_all_symbol_link.py /path/to/directory --broken-only
        """,
    )

    parser.add_argument("directory", help="要搜索软链接的目录路径")

    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        default=True,
        help="递归搜索子目录 (默认启用)",
    )

    parser.add_argument("--no-recursive", action="store_true", help="不递归搜索子目录")

    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="试运行模式，只显示将要删除的文件，不实际删除",
    )

    parser.add_argument(
        "-i", "--interactive", action="store_true", help="交互式模式，逐个确认是否删除"
    )

    parser.add_argument(
        "-b",
        "--broken-only",
        action="store_true",
        help="只删除失效的软链接（目标不存在）",
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()

    # 处理递归参数
    recursive = args.recursive and not args.no_recursive

    # 确认目录
    directory = Path(args.directory).resolve()

    if args.verbose:
        print(f"搜索目录: {directory}")
        print(f"递归搜索: {'是' if recursive else '否'}")
        print(f"试运行模式: {'是' if args.dry_run else '否'}")
        print(f"交互模式: {'是' if args.interactive else '否'}")
        print(f"仅删除失效链接: {'是' if args.broken_only else '否'}")
        print("-" * 50)

    # 查找软链接
    print("正在搜索软链接...")
    symlinks = find_symlinks(directory, recursive=recursive)

    if not symlinks:
        print("未找到任何软链接")
        return 0

    # 过滤失效链接
    if args.broken_only:
        original_count = len(symlinks)
        symlinks = [link for link in symlinks if not link.resolve().exists()]
        print(f"过滤后剩余 {len(symlinks)} 个失效软链接（原有 {original_count} 个）")

    # 安全确认
    if not args.dry_run and not args.interactive and len(symlinks) > 0:
        print(f"\n警告: 即将删除 {len(symlinks)} 个软链接!")
        response = input("确认继续? (y/N): ").strip().lower()
        if response not in ["y", "yes"]:
            print("操作已取消")
            return 0

    # 删除软链接
    success_count, error_count = delete_symlinks(
        symlinks, dry_run=args.dry_run, interactive=args.interactive
    )

    # 输出结果
    print("-" * 50)
    if args.dry_run:
        print(f"试运行完成，找到 {len(symlinks)} 个软链接")
    else:
        print(f"删除完成: 成功 {success_count} 个，失败 {error_count} 个")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n操作被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"程序异常: {e}")
        sys.exit(1)
