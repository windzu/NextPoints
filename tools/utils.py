# tools/utils.py
from typing import List, Tuple
import numpy as np
from wind_pypcd import pypcd


def find_nearest_timestamp(target: int, candidates: List[int]) -> int:
    return min(candidates, key=lambda x: abs(x - target))


def fuse_pointclouds(
    lidar_objs: List[Tuple[str, bytes, List[dict]]], verbose: bool = False
) -> bytes:
    """融合多个点云，支持忽略指定的3D box区域

    Args:
        lidar_objs: [(channel_name, pcd_bytes, ignore_area_json)]
            - channel_name: 传感器通道名称
            - pcd_bytes: PCD文件的字节数据
            - ignore_area_json: 忽略区域列表，每个元素是包含3D box定义的字典
                {
                    "x": 0.0,      # box中心x坐标
                    "y": 4.5,      # box中心y坐标
                    "z": 0.0,      # box中心z坐标
                    "length": 30.0, # x方向长度（yaw=0时）
                    "width": 10.0,  # y方向宽度（yaw=0时）
                    "height": 10.0, # z方向高度
                    "yaw": 0.0      # 绕z轴旋转角度（弧度）
                }

    Returns:
        融合后的PCD文件字节数据

    Raises:
        ValueError: 输入参数无效时
    """
    # 参数验证
    if not isinstance(lidar_objs, list):
        raise ValueError("lidar_objs must be a list")

    if not lidar_objs:
        raise ValueError("lidar_objs cannot be empty")

    # 验证每个lidar对象的格式
    for i, obj in enumerate(lidar_objs):
        if not isinstance(obj, (tuple, list)) or len(obj) != 3:
            raise ValueError(f"lidar_objs[{i}] must be a tuple/list of length 3")

        channel_name, pcd_bytes, ignore_areas = obj

        if not isinstance(channel_name, str):
            raise ValueError(f"lidar_objs[{i}][0] (channel_name) must be a string")

        if not isinstance(pcd_bytes, bytes):
            raise ValueError(f"lidar_objs[{i}][1] (pcd_bytes) must be bytes")

        if not isinstance(ignore_areas, list):
            raise ValueError(f"lidar_objs[{i}][2] (ignore_areas) must be a list")

    point_clouds = []

    for channel_name, pcd_bytes, ignore_areas in lidar_objs:
        try:
            # 加载点云数据
            pc = pypcd.PointCloud.from_bytes(pcd_bytes)

            # 提取点云数据
            x, y, z, intensity = _extract_point_cloud_data(pc)

            # 过滤NaN值
            valid_mask = (
                np.isfinite(x)
                & np.isfinite(y)
                & np.isfinite(z)
                & np.isfinite(intensity)
            )

            if not np.any(valid_mask):
                print(f"Warning: No valid points found in {channel_name}")
                continue

            # 构建点云数组 [N, 4]
            points = np.column_stack(
                [x[valid_mask], y[valid_mask], z[valid_mask], intensity[valid_mask]]
            ).astype(np.float32)

            # 应用忽略区域过滤
            if ignore_areas:
                points = _filter_points_by_ignore_areas(points, ignore_areas)
                if verbose:
                    original_count = len(points)
                    filtered_count = original_count - len(points)
                    print(
                        f"Filtered {filtered_count} points from {channel_name} "
                        f"(kept {len(points)}/{original_count})"
                    )

            if len(points) > 0:
                point_clouds.append(points)
                if verbose:
                    print(f"Processed {channel_name}: {len(points)} points")
            else:
                print(
                    f"Warning: No points remaining after filtering for {channel_name}"
                )

        except Exception as e:
            print(f"Warning: Failed to process {channel_name}: {e}")
            continue

    if not point_clouds:
        raise ValueError("No valid point clouds to fuse")

    # 合并所有点云
    fused_points = np.vstack(point_clouds)

    # 转换为结构化数组
    structured_array = _numpy_array_to_structured_array(fused_points)
    fusion_pc = pypcd.PointCloud.from_array(structured_array)

    # 转换为字节数据
    fused_bytes = fusion_pc.to_bytes(compression="binary_compressed")

    return fused_bytes


def _extract_point_cloud_data(
    pc: pypcd.PointCloud,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """从PointCloud对象中提取坐标和强度数据

    Args:
        pc: PointCloud对象

    Returns:
        x, y, z, intensity arrays

    Raises:
        ValueError: 点云数据无效时
    """
    try:
        x = pc.pc_data["x"].flatten()
        y = pc.pc_data["y"].flatten()
        z = pc.pc_data["z"].flatten()
        intensity = pc.pc_data["intensity"].flatten()
    except KeyError as e:
        raise ValueError(f"Missing required field in point cloud: {e}")
    except Exception as e:
        raise ValueError(f"Failed to extract point cloud data: {e}")

    # 检查数据长度一致性
    if not (len(x) == len(y) == len(z) == len(intensity)):
        raise ValueError("Point cloud field arrays have inconsistent lengths")

    return x, y, z, intensity


def _filter_points_by_ignore_areas(
    points: np.ndarray, ignore_areas: List[dict]
) -> np.ndarray:
    """根据忽略区域过滤点云

    Args:
        points: 点云数组 [N, 4] (x, y, z, intensity)
        ignore_areas: 忽略区域列表

    Returns:
        过滤后的点云数组
    """
    if not ignore_areas:
        return points

    if points.shape[1] < 3:
        raise ValueError("points must have at least 3 columns (x, y, z)")

    # 初始化所有点都不在忽略区域内
    points_to_ignore = np.zeros(len(points), dtype=bool)

    # 检查每个忽略区域
    for box in ignore_areas:
        # 验证box参数
        required_keys = ["x", "y", "z", "length", "width", "height"]
        if not all(key in box for key in required_keys):
            raise ValueError(f"Box must contain keys: {required_keys}")

        # 检查哪些点在当前box内
        in_box = _point_in_3d_box(points, box)
        points_to_ignore |= in_box

    # 返回不在任何忽略区域内的点
    return points[~points_to_ignore]


def _point_in_3d_box(points: np.ndarray, box: dict) -> np.ndarray:
    """检查点是否在3D box内

    Args:
        points: 点云数组 [N, 3] (x, y, z)
        box: 3D box定义字典

    Returns:
        布尔数组，True表示点在box内
    """
    if points.shape[1] < 3:
        raise ValueError("points must have at least 3 columns (x, y, z)")

    # 提取box参数
    cx, cy, cz = box["x"], box["y"], box["z"]
    length, width, height = box["length"], box["width"], box["height"]
    yaw = box.get("yaw", 0.0)  # 默认yaw为0

    # 将点平移到box中心为原点的坐标系
    translated_points = points[:, :3] - np.array([cx, cy, cz])

    # 如果有旋转，需要反向旋转点到box的本地坐标系
    if yaw != 0.0:
        cos_yaw = np.cos(-yaw)  # 反向旋转
        sin_yaw = np.sin(-yaw)
        rotation_matrix = np.array(
            [[cos_yaw, -sin_yaw, 0], [sin_yaw, cos_yaw, 0], [0, 0, 1]]
        )
        translated_points = translated_points @ rotation_matrix.T

    # 检查点是否在box范围内
    half_length = length / 2.0
    half_width = width / 2.0
    half_height = height / 2.0

    inside_x = np.abs(translated_points[:, 0]) <= half_length
    inside_y = np.abs(translated_points[:, 1]) <= half_width
    inside_z = np.abs(translated_points[:, 2]) <= half_height

    return inside_x & inside_y & inside_z


def _numpy_array_to_structured_array(arr: np.ndarray) -> np.ndarray:
    """将常规的numpy数组转换为结构化数组

    Args:
        arr: 输入的numpy数组，每一列对应一个字段 [N, 4] (x, y, z, intensity)

    Returns:
        结构化数组

    Raises:
        ValueError: 输入数组格式不正确时
    """
    if not isinstance(arr, np.ndarray):
        raise ValueError("arr must be a numpy array")

    if arr.ndim != 2:
        raise ValueError("arr must be a 2D array")

    if arr.shape[1] != 4:
        raise ValueError("Expected a Nx4 numpy array")

    if arr.size == 0:
        raise ValueError("arr cannot be empty")

    dtype = [("x", "f4"), ("y", "f4"), ("z", "f4"), ("intensity", "f4")]
    structured_arr = np.zeros(arr.shape[0], dtype=dtype)

    structured_arr["x"] = arr[:, 0]
    structured_arr["y"] = arr[:, 1]
    structured_arr["z"] = arr[:, 2]
    structured_arr["intensity"] = arr[:, 3]

    return structured_arr


if __name__ == "__main__":
    # Test fuse_pointclouds
    lidar_left_pcd_path = "/workspace/data/13982_YC200C01-R1-0001/custom/lidar/lidar_left/1749006745300192896.pcd"
    lidar_right_pcd_path = "/workspace/data/13982_YC200C01-R1-0001/custom/lidar/lidar_right/1749006745300191424.pcd"
    lidar_left_bytes = open(lidar_left_pcd_path, "rb").read()
    lidar_right_bytes = open(lidar_right_pcd_path, "rb").read()

    lidar_objs = [
        ("lidar_left", lidar_left_bytes, []),  # No ignore areas for this example
        ("lidar_right", lidar_right_bytes, []),  # No ignore areas for this example
    ]
    try:
        fused_pcd_bytes = fuse_pointclouds(lidar_objs, verbose=True)
        save_path = "/workspace/data/fused_pointcloud.pcd"
        with open(save_path, "wb") as f:
            f.write(fused_pcd_bytes)
    except ValueError as e:
        print(f"Error during fusion: {e}")
