#!/usr/bin/env python3
"""
批量创建软链接脚本
将输入目录中每个场景的sus文件夹链接到输出目录中
"""

import argparse
import os
import sys
from pathlib import Path


def find_scenes(input_dir):
    """
    查找输入目录中的所有场景

    Args:
        input_dir (Path): 输入目录路径

    Returns:
        list: 场景目录列表
    """
    scenes = []

    if not input_dir.exists():
        print(f"错误: 输入目录 '{input_dir}' 不存在")
        return scenes

    if not input_dir.is_dir():
        print(f"错误: '{input_dir}' 不是一个目录")
        return scenes

    try:
        for item in input_dir.iterdir():
            if item.is_dir():
                # 检查是否包含sus子目录
                sus_dir = item / "sus"
                if sus_dir.exists() and sus_dir.is_dir():
                    scenes.append(item)
                else:
                    print(f"警告: 场景 '{item.name}' 中未找到 'sus' 目录，跳过")
    except PermissionError as e:
        print(f"权限错误: {e}")
    except Exception as e:
        print(f"搜索场景时发生错误: {e}")

    return scenes


def create_symlinks(scenes, output_dir, dry_run=False, force=False):
    """
    为所有场景创建软链接

    Args:
        scenes (list): 场景目录列表
        output_dir (Path): 输出目录路径
        dry_run (bool): 是否为试运行模式
        force (bool): 是否强制覆盖已存在的链接

    Returns:
        tuple: (成功创建数量, 失败数量, 跳过数量)
    """
    success_count = 0
    error_count = 0
    skip_count = 0

    if not scenes:
        print("未找到任何包含 'sus' 目录的场景")
        return success_count, error_count, skip_count

    # 确保输出目录存在
    if not dry_run:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"无法创建输出目录 '{output_dir}': {e}")
            return success_count, error_count, skip_count

    print(f"找到 {len(scenes)} 个场景:")

    for i, scene_dir in enumerate(scenes, 1):
        scene_name = scene_dir.name
        sus_source = scene_dir / "sus"
        link_target = output_dir / scene_name

        print(f"  [{i}/{len(scenes)}] 场景: {scene_name}")
        print(f"    源目录: {sus_source}")
        print(f"    链接目标: {link_target}")

        # 检查源目录是否存在
        if not sus_source.exists():
            print(f"    ✗ 源目录不存在，跳过")
            skip_count += 1
            continue

        # 检查目标是否已存在
        if link_target.exists():
            if link_target.is_symlink():
                existing_target = (
                    link_target.readlink()
                    if hasattr(link_target, "readlink")
                    else os.readlink(str(link_target))
                )
                print(f"    ! 软链接已存在，指向: {existing_target}")
                if not force:
                    print(f"    - 跳过 (使用 --force 强制覆盖)")
                    skip_count += 1
                    continue
                else:
                    print(f"    - 强制覆盖现有链接")
                    if not dry_run:
                        try:
                            link_target.unlink()
                        except Exception as e:
                            print(f"    ✗ 删除现有链接失败: {e}")
                            error_count += 1
                            continue
            else:
                print(f"    ✗ 目标位置已存在非链接文件/目录，跳过")
                skip_count += 1
                continue

        # 创建软链接
        if not dry_run:
            try:
                # 使用绝对路径创建软链接
                link_target.symlink_to(sus_source.resolve())
                print(f"    ✓ 软链接创建成功")
                success_count += 1
            except PermissionError:
                print(f"    ✗ 权限不足")
                error_count += 1
            except FileExistsError:
                print(f"    ✗ 目标已存在")
                error_count += 1
            except Exception as e:
                print(f"    ✗ 创建失败: {e}")
                error_count += 1
        else:
            print(f"    [试运行] 将创建软链接")

    return success_count, error_count, skip_count


def main():
    parser = argparse.ArgumentParser(
        description="批量创建场景sus目录的软链接",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python create_data_symlinks.py /path/to/input /path/to/output
  python create_data_symlinks.py /path/to/input /path/to/output --dry-run
  python create_data_symlinks.py /path/to/input /path/to/output --force
  python create_data_symlinks.py /path/to/input /path/to/output --verbose

输入目录结构示例:
├── 6854-7_YC200B01-M1-0007
│   ├── nuscenes
│   ├── rosbag
│   └── sus
└── 8551-4_YC1000S6-O1-0003
    ├── nuscenes
    ├── rosbag
    └── sus

输出结果:
├── 6854-7_YC200B01-M1-0007 -> /path/to/input/6854-7_YC200B01-M1-0007/sus
└── 8551-4_YC1000S6-O1-0003 -> /path/to/input/8551-4_YC1000S6-O1-0003/sus
        """,
    )

    parser.add_argument("input_dir", help="输入目录路径（包含场景目录）")

    parser.add_argument("output_dir", help="输出目录路径（创建软链接的目标位置）")

    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="试运行模式，只显示将要创建的链接，不实际创建",
    )

    parser.add_argument(
        "-f", "--force", action="store_true", help="强制覆盖已存在的软链接"
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="详细输出")

    args = parser.parse_args()

    # 转换为Path对象并解析为绝对路径
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    if args.verbose:
        print(f"输入目录: {input_dir}")
        print(f"输出目录: {output_dir}")
        print(f"试运行模式: {'是' if args.dry_run else '否'}")
        print(f"强制覆盖: {'是' if args.force else '否'}")
        print("-" * 60)

    # 验证输入目录
    if not input_dir.exists():
        print(f"错误: 输入目录 '{input_dir}' 不存在")
        return 1

    if not input_dir.is_dir():
        print(f"错误: '{input_dir}' 不是一个目录")
        return 1

    # 检查输出目录是否是输入目录的子目录（避免循环链接）
    try:
        if output_dir.resolve().is_relative_to(input_dir.resolve()):
            print(f"错误: 输出目录不能是输入目录的子目录")
            return 1
    except AttributeError:
        # Python < 3.9 兼容性
        if str(output_dir.resolve()).startswith(str(input_dir.resolve())):
            print(f"错误: 输出目录不能是输入目录的子目录")
            return 1

    # 查找场景
    print("正在搜索场景...")
    scenes = find_scenes(input_dir)

    if not scenes:
        print("未找到任何包含 'sus' 目录的场景")
        return 0

    # 显示找到的场景
    if args.verbose:
        print(f"找到的场景:")
        for scene in scenes:
            print(f"  - {scene.name}")
        print("-" * 60)

    # 安全确认
    if not args.dry_run and len(scenes) > 0:
        print(f"\n即将为 {len(scenes)} 个场景创建软链接到 '{output_dir}'")
        response = input("确认继续? (y/N): ").strip().lower()
        if response not in ["y", "yes"]:
            print("操作已取消")
            return 0

    # 创建软链接
    success_count, error_count, skip_count = create_symlinks(
        scenes, output_dir, dry_run=args.dry_run, force=args.force
    )

    # 输出结果
    print("-" * 60)
    if args.dry_run:
        print(f"试运行完成:")
        print(f"  - 找到场景: {len(scenes)} 个")
        print(f"  - 将创建链接: {len(scenes) - skip_count} 个")
        print(f"  - 将跳过: {skip_count} 个")
    else:
        print(f"软链接创建完成:")
        print(f"  - 成功创建: {success_count} 个")
        print(f"  - 创建失败: {error_count} 个")
        print(f"  - 跳过: {skip_count} 个")

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
