import { Debug } from "./debug.js";
import { logger } from "./log.js";
import { World } from "./world.js";

class Data {
    cfg;
    projectList = [];
    meta = {};
    worldList = [];
    webglScene = null;
    webglMainScene = null;
    world = null;
    refEgoPose = {};
    offsetList = [[0, 0, 0]];
    lastSeedOffset = [0, 0, 0];
    offsetsAliveCount = 0;
    worldGap = 1000.0;
    MaxWorldNumber = 80;
    createWorldIndex = 0;
    dbg = new Debug();

    constructor(cfg) {
        this.cfg = cfg;
    }

    async readProjectList(statusFilter = '') {
        try {
            const url = new URL('/api/projects/list_projects', window.location.origin);
            if (statusFilter) url.searchParams.set('status_filter', statusFilter);

            const response = await fetch(url);
            if (!response.ok) throw new Error(`Failed: ${response.status}`);

            const projects = await response.json();
            this.projectList = projects;
            return projects;
        } catch (err) {
            console.error("Error reading project list:", err);
            throw err;
        }
    }

    async init() {
        const projects = await this.readProjectList();
        if (!projects || projects.length === 0) {
            console.warn("No projects available");
            return;
        }
        this.currentProject = projects[0];
    }

    getMetaBySceneName = (sceneName) => this.meta[sceneName];

    getProjectByName = (projectName) => this.projectList?.find(p => p.name === projectName) ?? null;

    allocateOffset = () => {
        if (this.offsetsAliveCount === 0) {
            this.offsetList = [[0, 0, 0]];
            this.lastSeedOffset = [0, 0, 0];
        }

        if (this.offsetList.length === 0) {
            let [x, y] = this.lastSeedOffset;

            if (x === y) {
                x += 1;
                y = 0;
            } else {
                y += 1;
            }

            this.lastSeedOffset = [x, y, 0];
            const newOffsets = [
                [x, y, 0], [-x, y, 0], [x, -y, 0], [-x, -y, 0],
                [y, x, 0], [-y, x, 0], [y, -x, 0], [-y, -x, 0]
            ];

            newOffsets.forEach(offset => {
                if (!this.offsetList.includes(offset)) this.offsetList.push(offset);
            });
        }

        this.offsetsAliveCount++;
        return this.offsetList.pop();
    };

    returnOffset = (offset) => {
        this.offsetList.push(offset);
        this.offsetsAliveCount--;
    };

    findWorld = (scene, frameIndex) =>
        this.worldList.find(w => w.frameInfo.scene === scene && w.frameInfo.frame_index === frameIndex) ?? null;

    _createWorld = (sceneName, frameId, onPreloadFinished) => {
        const [x, y, z] = this.allocateOffset();
        const world = new World(this, sceneName, frameId, [this.worldGap * x, this.worldGap * y, this.worldGap * z], onPreloadFinished);
        world.offsetIndex = [x, y, z];

        this.createWorldIndex++;
        this.worldList.push(world);
        return world;
    };

    async getWorld(sceneName, frameId, onPreloadFinished) {
        if (!this.meta[sceneName]) {
            await this.readSceneMetaData(sceneName);
        }

        if (!this.meta[sceneName]) {
            logger.log("load project failed", sceneName);
            return null;
        }

        const existing = this.worldList.find(w => w.frameInfo.scene === sceneName && w.frameInfo.frame === frameId);
        return existing ?? this._createWorld(sceneName, frameId, onPreloadFinished);
    }

    deleteDistantWorlds = (currentWorld) => {
        const currentIndex = currentWorld.frameInfo.frame_index;

        const removable = (w) => {
            const tooFar = Math.abs(w.frameInfo.frame_index - currentIndex) > this.MaxWorldNumber;
            const isSafe = !w.annotation.modified && w.everythingDone;
            return tooFar && isSafe;
        };

        const toDelete = this.worldList.filter(removable);
        toDelete.forEach(w => {
            this.returnOffset(w.offsetIndex);
            w.deleteAll();
        });

        this.worldList = this.worldList.filter(w => !removable(w));
    };

    deleteOtherWorldsExcept = (keepScene) => {
        this.worldList.forEach(w => {
            if (w.frameInfo.scene !== keepScene) {
                this.returnOffset(w.offsetIndex);
                w.deleteAll();
                this.removeRefEgoPoseOfScene(w.frameInfo.scene);
            }
        });
        this.worldList = this.worldList.filter(w => w.frameInfo.scene === keepScene);
    };

    getRefEgoPose = (sceneName, currentPose) => {
        return this.refEgoPose[sceneName] ?? (this.refEgoPose[sceneName] = currentPose);
    };

    get_current_world_scene_meta = () => {
        if (!this.world || !this.world.frameInfo) {
            console.warn("No active world to get scene metadata.");
            return null;
        }
        return this.getMetaBySceneName(this.world.frameInfo.scene);
    };

    removeRefEgoPoseOfScene = (sceneName) => {
        delete this.refEgoPose[sceneName];
    };

    forcePreloadScene = (sceneName, currentWorld) => {
        const meta = currentWorld.sceneMeta;
        const currentIndex = currentWorld.frameInfo.frame_index;
        const start = Math.max(0, currentIndex - this.MaxWorldNumber / 2);
        const end = Math.min(meta.frames.length, start + this.MaxWorldNumber);
        this._doPreload(sceneName, start, end);
        logger.log(`${end - start} frames created`);
    };

    preloadScene = (sceneName, currentWorld) => {
        this.deleteOtherWorldsExcept(sceneName);
        this.deleteDistantWorlds(currentWorld);
        if (!this.cfg.enablePreload) return;
        this.forcePreloadScene(sceneName, currentWorld);
    };

    _doPreload = (sceneName, startIndex, endIndex) => {
        const meta = this.getMetaBySceneName(sceneName);

        // 检查 meta 是否存在
        if (!meta) {
            console.error(`Scene meta not found for: ${sceneName}`);
            return;
        }

        // 检查 frames 是否存在
        if (!meta.frames) {
            console.error(`Scene meta frames not found for: ${sceneName}`, meta);
            return;
        }

        const pending = meta.frames.slice(startIndex, endIndex).filter(f =>
            !this.worldList.find(w => w.frameInfo.scene === sceneName && w.frameInfo.frame === f)
        );

        logger.log(`preload ${meta.scene || sceneName} ${pending}`);
        pending.forEach(f => this._createWorld(sceneName, f));
    };

    reloadAllAnnotation = (done) => {
        this.worldList.forEach(w => w.reloadAnnotation(done));
    };

    onAnnotationUpdatedByOthers = (scene, frames) => {
        frames.forEach(f => {
            const w = this.worldList.find(w => w.frameInfo.scene === scene && w.frameInfo.frame === f);
            if (w) w.annotation.reloadAnnotation();
        });
    };

    set_webglScene = (scene, mainScene) => {
        this.webglScene = scene;
        this.webglMainScene = mainScene;
    };

    scale_point_size = (v) => {
        this.cfg.point_size *= v;
        this.worldList.forEach(w => w.lidar.set_point_size(this.cfg.point_size));
    };

    scale_point_brightness = (v) => {
        this.cfg.point_brightness *= v;
        this.worldList.forEach(w => w.lidar.recolor_all_points());
    };

    set_box_opacity = (opacity) => {
        this.cfg.box_opacity = opacity;
        this.worldList.forEach(w => w.annotation.set_box_opacity(opacity));
    };

    toggle_background = () => {
        this.cfg.show_background = !this.cfg.show_background;
        if (this.cfg.show_background) {
            this.world.lidar.cancel_highlight();
        } else {
            this.world.lidar.hide_background();
        }
    };

    set_obj_color_scheme = (scheme) => {
        pointsGlobalConfig.color_obj = scheme;
        this.worldList.forEach(w => {
            if (scheme === "no") {
                w.lidar.color_points();
            } else {
                w.lidar.color_objects();
            }
            w.lidar.update_points_color();
            w.annotation.color_boxes();
        });
    };

    activate_world = (world, onFinished, dontDestroyOld = false) => {
        const old = this.world;
        this.world = world;
        world.activate(this.webglMainScene, () => {
            if (!dontDestroyOld && old) old.unload();
        }, onFinished);
    };

    async readSceneMetaData(sceneName) {
        console.log("read scene metadata", sceneName);
        const res = await fetch(`/api/projects/${sceneName}/metadata`);
        if (!res.ok) throw new Error(`HTTP error: ${res.status}`);

        const data = await res.json();

        // 1) 强校验 main_channel
        const main = data.main_channel;
        if (!main) throw new Error(`[metadata] main_channel missing for scene=${sceneName}`);

        // 2) 构造 frameDetails（仅以 timestamp_ns 为键），并强制注入 pointcloud_url
        const frames = (data.frames ?? []).map(f => {
            if (!f?.lidars || typeof f.lidars[main] !== "string" || !f.lidars[main]) {
                throw new Error(
                    `[metadata] missing lidar for main_channel="${main}" at ts=${f?.timestamp_ns} in scene=${sceneName}`
                );
            }
            return { ...f, pointcloud_url: f.lidars[main] };
        });

        const frameDetails = Object.fromEntries(frames.map(f => [f.timestamp_ns, f]));

        // 3) 构造 sceneMetadata（去冗余）
        const sceneMetadata = {
            scene: sceneName,
            main_channel: main,
            frames: frames.map(f => f.timestamp_ns),
            frameDetails,
            camera: [], // 如需相机再填；与本需求无关可留空
            boxtype: "psr",
            point_transform_matrix: [1, 0, 0, 0, 1, 0, 0, 0, 1],
            calib: { camera: {} }, // 与点云无关，保持骨架
            summary: {
                frame_count: data.frame_count,
                start_timestamp_ns: data.start_timestamp_ns,
                end_timestamp_ns: data.end_timestamp_ns,
                duration_seconds: data.duration_seconds
            }
        };

        // 3) 解析 calibration：仅按你的定义读取
        const calibrations = data.calibration ?? {};
        for (const [channel, calib] of Object.entries(calibrations)) {
            const cfg = calib?.camera_config;
            if (!cfg) continue; // 只收相机

            const name = cfg.name || channel;

            // --- 内参矩阵 intrinsic（3x3）
            // intrinsic = [[fx, skew, cx],
            //      [0 ,  fy , cy],
            //      [0 ,  0  , 1 ]]
            const intrinsic = [
                cfg.intrinsic.fx, cfg.intrinsic.skew ?? 0, cfg.intrinsic.cx,
                0, cfg.intrinsic.fy, cfg.intrinsic.cy,
                0, 0, 1
            ];

            // --- 畸变参数（按给定结构打包，前端自定义使用方式）
            const distortion = {
                k1: cfg.distortion_coefficients.k1,
                k2: cfg.distortion_coefficients.k2,
                p1: cfg.distortion_coefficients.p1,
                p2: cfg.distortion_coefficients.p2,
                k3: cfg.distortion_coefficients.k3 ?? 0,
                k4: cfg.distortion_coefficients.k4 ?? 0,
                k5: cfg.distortion_coefficients.k5 ?? 0
            };

            // --- 外参，从 calib.pose 计算（支持 quat / euler，两者其一即可）
            const extrinsic = this._poseToExtrinsic(calib.pose);

            sceneMetadata.camera.push(channel);
            sceneMetadata.calib.camera[channel] = {
                channel,
                name,                     // 相机名称
                width: cfg.width,
                height: cfg.height,
                model: cfg.model,          // "pinhole" / "fisheye" / "omnidirectional"
                intrinsic,                 // 3x3 展平
                distortion,                // 原样打包
                extrinsic,                 // 4x4 展平
            };
        }

        this.meta[sceneName] = sceneMetadata;
        return sceneMetadata;
    }

    /**
     * 将 Pose 转为 4x4 外参（展平为长度16数组，行主序）
     * 期望 Pose 结构：{ parent_frame_id, child_frame_id, transform: { translation:{x,y,z}, rotation:{...} } }
     * rotation 支持：
     *  - 四元数: {w,x,y,z}
     */
    _poseToExtrinsic(pose) {
        if (!pose?.transform) return null;
        const t = pose.transform.translation ?? { x: 0, y: 0, z: 0 };
        const r = pose.transform.rotation ?? {};

        // 构出 3x3 R
        let R;
        if (typeof r.w === "number" && typeof r.x === "number") {
            // quaternion -> R
            const { w, x, y, z } = r;
            const xx = x * x, yy = y * y, zz = z * z, ww = w * w;
            const xy = x * y, xz = x * z, yz = y * z, wx = w * x, wy = w * y, wz = w * z;
            R = [
                1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy),
                2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx),
                2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy)
            ];
        } else {
            console.warn("Unsupported rotation format, expected quaternion ", r);
            return null;
        }

        // 4x4: [R|t; 0 0 0 1]
        return [
            R[0], R[1], R[2], t.x ?? 0,
            R[3], R[4], R[5], t.y ?? 0,
            R[6], R[7], R[8], t.z ?? 0,
            0, 0, 0, 1
        ];
    }

}

export { Data };
