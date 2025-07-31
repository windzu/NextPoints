import os
import json

this_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.join(this_dir, "data")


def get_all_scenes(path=None):
    if path is None or path == "" or path == "/" or path == "null" or path == ".":
        path = root_dir
        path = os.path.expanduser(path)

    scene_name_list = get_scene_name_list(path)
    return list(map(get_one_scene, scene_name_list))


def get_all_scene_desc(path=None):
    """获取所有场景的描述信息,需要满足如下几种传参情况

    1. 如果path为None,"","null",则默认为root_dir,即data文件夹,遍历data文件夹下的所有场景的描述信息并返回
    2. 如果path为一个路径有效的文件夹,则认为该文件夹为一个场景,返回该场景的描述信息
    3. 如果path为一个无效路径,则尝试在data文件夹下查找该路径对应的场景,返回该场景的描述信息

    Args:
        root (str, optional): scene_path or scene_name. Defaults to None.

    Returns:
        dict: scene desc dict include scene_name, scene_path
    """
    descs = {}
    # check path valid
    # path can be str or None
    if path is None or isinstance(path, str):
        pass
    else:
        print("path is not valid: ", path)
        return {}

    # case 1: path is None or empty
    if path is None or path == "" or path == "/" or path == "null" or path == ".":
        path = root_dir
        path = os.path.expanduser(path)
        scene_path_list = get_scene_path_list(path)
        for scene_path in scene_path_list:
            scene_name = os.path.basename(scene_path)
            descs[scene_name] = get_scene_desc(scene_path)
    # case 2: check path is a absolute path
    elif os.path.isabs(path):
        # case 2.1: path is a valid dir
        # - get real scene name
        # - get_scene_desc
        # - create soft link
        if os.path.isdir(path):
            # get scene_name
            # Note : get scene name from back to front
            # Note : scene_name can not named "sus"
            scene_name = os.path.basename(path)
            if scene_name == "sus":
                scene_name = os.path.basename(os.path.dirname(path))
            descs[scene_name] = get_scene_desc(path,scene_name)
            create_soft_link(path,scene_name)
        # case 2.2: path is an invalid dir
        else:
            print("path not exists: ", path)
            return {}
    # # case 2: path is a valid dir
    # elif os.path.isdir(path):
    #     scene_name = os.path.basename(path)
    #     descs[scene_name] = get_scene_desc(path)
    # case 3: path is an invalid dir
    else:
        if path[-1] == "/":
            path = path[:-1]
        scene_path = os.path.join(root_dir, path)
        if os.path.isdir(scene_path):
            scene_name = os.path.basename(scene_path)
            descs[scene_name] = get_scene_desc(scene_path)
        else:
            print("path not exists: ", path)
            return {}
        
    return descs


def get_scene_names(root_path=None):
    # check root dir valid
    if root_path is None:
        print("root_path is None")
        return []
    scenes = os.listdir(root_path)
    scenes = filter(
        lambda s: not os.path.exists(os.path.join(root_path, s, "disable")), scenes
    )
    scenes = list(scenes)
    scenes.sort()
    return scenes


def get_scene_name_list(root_path=None):
    scene_name_list = []
    # check root dir valid
    if root_path is None:
        print("root_path is None")
        return []
    scene_name_list = os.listdir(root_path)
    scene_name_list = filter(
        lambda s: not os.path.exists(os.path.join(root_path, s, "disable")),
        scene_name_list,
    )
    scene_name_list = list(scene_name_list)
    scene_name_list.sort()
    return scene_name_list


def get_scene_path_list(root_path=None):
    # check root dir valid
    if root_path is None:
        print("root_path is None")
        return []

    scene_path_list = []
    scenes = os.listdir(root_path)

    for scene in scenes:
        scene_path = os.path.join(root_path, scene)
        if os.path.isdir(scene_path):
            scene_path_list.append(scene_path)

    return scene_path_list


def get_scene_desc(scene_path,scene_name=None):
    """get scene desc and create soft link

    Args:
        scene_path (_type_): scene absolute path

    Returns:
        dict: scene desc dict include scene_name, scene_path
    """

    # get scene desc from desc.json
    desc = None
    if scene_name is None:
        scene_name = os.path.basename(scene_path)
    else:
        scene_name = scene_name
    if os.path.exists(os.path.join(scene_path, "desc.json")):
        with open(os.path.join(scene_path, "desc.json")) as f:
            desc = json.load(f)
            desc["scene_name"] = scene_name
            desc["scene_path"] = scene_path

    return desc


def create_soft_link(scene_path,target_scene_name=None):
    """create_soft_link to root_dir

    1. check scene name if exist in root_dir
    2. if not exist, create soft link
    3. if exist, remove and create soft link

    Args:
        scene_path (str): scene absolute path
    """
    # check scene path if exist
    if not os.path.exists(scene_path):
        print("scene_path is not valid: ", scene_path)
        return
    
    # get scene_name
    scene_name= os.path.basename(scene_path)
    if target_scene_name is not None:
        scene_name = target_scene_name

    target_path = os.path.join(root_dir, scene_name)

    # check scene_path if same as target_path
    if scene_path == target_path:
        return

    if os.path.exists(target_path):
        # echo warning and return
        print("scene_name exists: ", scene_name)
        return

    # Check if the link or file exists
    elif os.path.islink(target_path):
        os.remove(target_path)
        os.symlink(scene_path, target_path)
    else:
        os.symlink(scene_path, target_path)


def get_one_scene(scene_name):
    """get one scene info from root_dir

    Args:
        scene_name (str): scene name

    Returns:
        dict: scene info dict include scene_name, frames, lidar_ext, camera_ext, radar_ext, aux_lidar_ext, calib

        example:
        {
            "scene": "scene_name",
            "frames": ["frame1", "frame2", ...],
            "lidar_ext": "pcd",
            "camera_ext": "jpg",
            "radar_ext": "pcd",
            "aux_lidar_ext": "pcd",
            "calib": {
                "camera": {
                    "camera_name1": {...},
                    "camera_name2": {...},
                    ...
                },
                "radar": {
                    "radar_name1": {...},
                    "radar_name2": {...},
                    ...
                },
                "aux_lidar": {
                    "aux_lidar_name1": {...},
                    "aux_lidar_name2": {...},
                    ...
                }
            }
        }
    """
    # check scene path if exist
    scene_path = os.path.join(root_dir, scene_name)

    if not os.path.isdir(scene_path):
        print("scene_path is not valid: ", scene_path)
        return

    scene = {"scene": scene_name, "frames": []}
    frames = os.listdir(os.path.join(scene_path, "lidar"))
    frames.sort()

    scene["lidar_ext"] = "pcd"
    for f in frames:
        filename, fileext = os.path.splitext(f)
        scene["frames"].append(filename)
        scene["lidar_ext"] = fileext

    if os.path.exists(os.path.join(scene_path, "desc.json")):
        with open(os.path.join(scene_path, "desc.json")) as f:
            desc = json.load(f)
            scene["desc"] = desc

    calib = {}
    calib_camera = {}
    calib_radar = {}
    calib_aux_lidar = {}
    if os.path.exists(os.path.join(scene_path, "calib")):
        if os.path.exists(os.path.join(scene_path, "calib", "camera")):
            calibs = os.listdir(os.path.join(scene_path, "calib", "camera"))
            for c in calibs:
                calib_file = os.path.join(scene_path, "calib", "camera", c)
                calib_name, ext = os.path.splitext(c)
                if os.path.isfile(calib_file) and ext == ".json":
                    # print(calib_file)
                    with open(calib_file) as f:
                        cal = json.load(f)
                        calib_camera[calib_name] = cal

        if os.path.exists(os.path.join(scene_path, "calib", "radar")):
            calibs = os.listdir(os.path.join(scene_path, "calib", "radar"))
            for c in calibs:
                calib_file = os.path.join(scene_path, "calib", "radar", c)
                calib_name, _ = os.path.splitext(c)
                if os.path.isfile(calib_file):
                    # print(calib_file)
                    with open(calib_file) as f:
                        cal = json.load(f)
                        calib_radar[calib_name] = cal
        if os.path.exists(os.path.join(scene_path, "calib", "aux_lidar")):
            calibs = os.listdir(os.path.join(scene_path, "calib", "aux_lidar"))
            for c in calibs:
                calib_file = os.path.join(scene_path, "calib", "aux_lidar", c)
                calib_name, _ = os.path.splitext(c)
                if os.path.isfile(calib_file):
                    # print(calib_file)
                    with open(calib_file) as f:
                        cal = json.load(f)
                        calib_aux_lidar[calib_name] = cal

    # camera names
    camera = []
    camera_ext = ""
    cam_path = os.path.join(scene_path, "camera")
    if os.path.exists(cam_path):
        cams = os.listdir(cam_path)
        for c in cams:
            cam_file = os.path.join(scene_path, "camera", c)
            if os.path.isdir(cam_file):
                camera.append(c)

                if camera_ext == "":
                    # detect camera file ext
                    files = os.listdir(cam_file)
                    if len(files) >= 2:
                        _, camera_ext = os.path.splitext(files[0])

    if camera_ext == "":
        camera_ext = ".jpg"
    scene["camera_ext"] = camera_ext

    # radar names
    radar = []
    radar_ext = ""
    radar_path = os.path.join(scene_path, "radar")
    if os.path.exists(radar_path):
        radars = os.listdir(radar_path)
        for r in radars:
            radar_file = os.path.join(scene_path, "radar", r)
            if os.path.isdir(radar_file):
                radar.append(r)
                if radar_ext == "":
                    # detect camera file ext
                    files = os.listdir(radar_file)
                    if len(files) >= 2:
                        _, radar_ext = os.path.splitext(files[0])

    if radar_ext == "":
        radar_ext = ".pcd"
    scene["radar_ext"] = radar_ext

    # aux lidar names
    aux_lidar = []
    aux_lidar_ext = ""
    aux_lidar_path = os.path.join(scene_path, "aux_lidar")
    if os.path.exists(aux_lidar_path):
        lidars = os.listdir(aux_lidar_path)
        for r in lidars:
            lidar_file = os.path.join(scene_path, "aux_lidar", r)
            if os.path.isdir(lidar_file):
                aux_lidar.append(r)
                if radar_ext == "":
                    # detect camera file ext
                    files = os.listdir(radar_file)
                    if len(files) >= 2:
                        _, aux_lidar_ext = os.path.splitext(files[0])

    if aux_lidar_ext == "":
        aux_lidar_ext = ".pcd"
    scene["aux_lidar_ext"] = aux_lidar_ext

    # # ego_pose
    # ego_pose= {}
    # ego_pose_path = os.path.join(scene_dir, "ego_pose")
    # if os.path.exists(ego_pose_path):
    #     poses = os.listdir(ego_pose_path)
    #     for p in poses:
    #         p_file = os.path.join(ego_pose_path, p)
    #         with open(p_file)  as f:
    #                 pose = json.load(f)
    #                 ego_pose[os.path.splitext(p)[0]] = pose

    if True:  # not os.path.isdir(os.path.join(scene_dir, "bbox.xyz")):
        scene["boxtype"] = "psr"
        # if point_transform_matrix:
        #     scene["point_transform_matrix"] = point_transform_matrix
        if camera:
            scene["camera"] = camera
        if radar:
            scene["radar"] = radar
        if aux_lidar:
            scene["aux_lidar"] = aux_lidar
        if calib_camera:
            calib["camera"] = calib_camera
        if calib_radar:
            calib["radar"] = calib_radar
        if calib_aux_lidar:
            calib["aux_lidar"] = calib_aux_lidar
        # if ego_pose:
        #     scene["ego_pose"] = ego_pose

    scene["calib"] = calib

    return scene


def read_annotations(scene_name, frame):
    # check scene path if exist
    scene_path = os.path.join(root_dir, scene_name)
    if not os.path.exists(scene_path):
        print("scene_path is not valid: ", scene_name)
        return []

    filename = os.path.join(scene_path, "label", frame + ".json")
    if os.path.isfile(filename):
        with open(filename, "r") as f:
            ann = json.load(f)
            # print(ann)
            return ann
    else:
        return []


def read_ego_pose(scene_name, frame):
    # check scene path if exist
    scene_path = os.path.join(root_dir, scene_name)
    if not os.path.exists(scene_path):
        print("scene_path is not valid: ", scene_name)
        return []

    filename = os.path.join(scene_path, "ego_pose", frame + ".json")
    if os.path.isfile(filename):
        with open(filename, "r") as f:
            p = json.load(f)
            return p
    else:
        return None


def save_annotations(scene_name, frame, anno):
    # check scene path if exist
    scene_path = os.path.join(root_dir, scene_name)
    if not os.path.exists(scene_path):
        print("scene_path is not valid: ", scene_name)
        return []

    filename = os.path.join(scene_path, "label", frame + ".json")
    with open(filename, "w") as outfile:
        json.dump(anno, outfile)


if __name__ == "__main__":
    print(get_all_scenes())
