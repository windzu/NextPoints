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
        // debug
        console.log("read scene metadata", sceneName);
        try {
            const response = await fetch(`/api/projects/${sceneName}/metadata`);
            if (!response.ok) throw new Error(`HTTP error: ${response.status}`);

            const data = await response.json();
            const frames = data.frames.map(f => f.timestamp_ns);
            const frameDetails = Object.fromEntries(data.frames.map(f => [f.timestamp_ns, f]));

            const sceneMetadata = {
                scene: sceneName,
                frames,
                frameDetails,
                camera: [],
                boxtype: "psr",
                point_transform_matrix: [1, 0, 0, 0, 1, 0, 0, 0, 1],
                calib: { camera: {} }
            };

            if (data.calibration) {
                for (const [sensorId, calib] of Object.entries(data.calibration)) {
                    if (calib.camera_config) {
                        sceneMetadata.camera.push(sensorId);
                        sceneMetadata.calib.camera[sensorId] = {
                            ...calib,
                            intrinsic: calib.camera_config.intrinsic,
                            extrinsic: this._createExtrinsicMatrix(calib.translation, calib.rotation)
                        };
                    }
                }
            }

            this.meta[sceneName] = sceneMetadata;
            return sceneMetadata;
        } catch (err) {
            console.error("Failed to read scene metadata:", err);
            throw err;
        }
    }

    _createExtrinsicMatrix = (translation = [0, 0, 0]) => [
        [1, 0, 0, translation[0]],
        [0, 1, 0, translation[1]],
        [0, 0, 1, translation[2]],
        [0, 0, 0, 1],
    ];
}

export { Data };
