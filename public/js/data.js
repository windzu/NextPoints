

import { Debug } from "./debug.js";
import { logger } from "./log.js";
import { World } from "./world.js";

class Data {

    constructor(cfg) {
        this.cfg = cfg;

    }

    async readSceneList(path) {
        const queryString = new URLSearchParams({ path: path }).toString();
        const urlWithParams = queryString ? `/get_all_scene_desc?${queryString}` : '/get_all_scene_desc';


        return fetch(urlWithParams)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                } else {
                    return response.json();
                }
            })
            .then(ret => {
                // sceneDescList is a dict where key is sceneName and value is None
                this.sceneDescList = ret;
                return ret;
            })
            .catch(reject => {
                console.log("error read scene list!");
            });
    }

    async init(path) {
        await this.readSceneList(path);
    }

    // multiple world support
    // place world by a offset so they don't overlap
    dbg = new Debug();

    worldGap = 1000.0;
    worldList = [];
    MaxWorldNumber = 80;
    createWorldIndex = 0; // this index shall not repeat, so it increases permanently

    async getWorld(sceneName, frame, on_preload_finished) {
        // find in list

        if (!this.meta[sceneName]) {
            await this.readSceneMetaData(sceneName)
        }

        if (!this.meta[sceneName]) {
            logger.log("load scene failed", sceneName);
            return null;
        }

        let world = this.worldList.find((w) => {
            return w.frameInfo.scene == sceneName && w.frameInfo.frame == frame;
        })
        if (world) // found!
            return world;


        world = this._createWorld(sceneName, frame, on_preload_finished);

        return world;
    };

    _createWorld(sceneName, frame, on_preload_finished) {

        // 这里生成一系列 offset ,用于在 new world 时分配
        // offset 的创建是有规律的，不会重复
        // 生成 offset 的原因是在前端页面中只有一个 3d 画布, 但却同时加载了多帧点云, 以及在多帧编辑的界面中
        // 我们会同时有多个 world, 他们的点云数据是不同的，但是他们的 3d 画布是一样的 , 而所有点云的原始数据默认是以原点为中心的
        // 所以此时多个 world 的点云数据会重叠在一起，为了避免这种情况，我们在创建每个world时候就为其分配一个 offset
        // 这个 offset 用于将每个点云从原点移开，这样就不会重叠了
        // 所以这个 offset 需要非常大，并且不会重复 , 以保证不会重叠 , 在这里采用的是类似一个螺旋线的方式生成 offset ,并在此基础上*1000 以保证足够大
        // 这样最终的效果是每个点云会被分配到一个 1000*1000*1000的立方体中，这样就不会重叠了

        let [x, y, z] = this.allocateOffset();
        let world = new World(this, sceneName, frame, [this.worldGap * x, this.worldGap * y, this.worldGap * z], on_preload_finished);
        world.offsetIndex = [x, y, z];
        this.createWorldIndex++;
        this.worldList.push(world);

        return world;

    };


    findWorld(sceneName, frameIndex) {
        let world = this.worldList.find((w) => {
            return w.frameInfo.scene == sceneName && w.frameInfo.frame_index == frameIndex;
        })
        if (world) // found!
            return world;
        else
            return null;
    };

    offsetList = [[0, 0, 0]];
    lastSeedOffset = [0, 0, 0];
    offsetsAliveCount = 0;
    allocateOffset() {

        // we need to make sure the first frame loaded in a scene 
        // got to locate in [0,0,0]

        if (this.offsetsAliveCount == 0) {
            //reset offsets.
            this.offsetList = [[0, 0, 0]];
            this.lastSeedOffset = [0, 0, 0];
        }



        if (this.offsetList.length == 0) {
            let [x, y, z] = this.lastSeedOffset;

            if (x == y) {
                x = x + 1;
                y = 0;
            }
            else {
                y = y + 1;
            }

            this.lastSeedOffset = [x, y, 0];

            this.offsetList.push([x, y, 0]);

            if (x != 0) this.offsetList.push([-x, y, 0]);
            if (y != 0) this.offsetList.push([x, -y, 0]);
            if (x * y != 0) this.offsetList.push([-x, -y, 0]);

            if (x != y) {
                this.offsetList.push([y, x, 0]);

                if (y != 0) this.offsetList.push([-y, x, 0]);
                if (x != 0) this.offsetList.push([y, -x, 0]);
                if (x * y != 0) this.offsetList.push([-y, -x, 0]);
            }
        }

        let ret = this.offsetList.pop();
        this.offsetsAliveCount++;

        return ret;
    };

    returnOffset(offset) {
        this.offsetList.push(offset);
        this.offsetsAliveCount--;
    };

    deleteDistantWorlds(world) {
        let currentWorldIndex = world.frameInfo.frame_index;

        let disposable = (w) => {
            let distant = Math.abs(w.frameInfo.frame_index - currentWorldIndex) > this.MaxWorldNumber;
            let active = w.everythingDone;
            if (w.annotation.modified) {
                console.log("deleting world not saved. stop.");
            }

            return distant && !active && !w.annotation.modified;
        }

        let distantWorldList = this.worldList.filter(w => disposable(w));

        distantWorldList.forEach(w => {
            this.returnOffset(w.offsetIndex);
            w.deleteAll();
        });


        this.worldList = this.worldList.filter(w => !disposable(w));

    };

    deleteOtherWorldsExcept = function (keepScene) {
        // release resources if scene changed
        this.worldList.forEach(w => {
            if (w.frameInfo.scene != keepScene) {
                this.returnOffset(w.offsetIndex);
                w.deleteAll();

                this.removeRefEgoPoseOfScene(w.frameInfo.scene);
            }
        })
        this.worldList = this.worldList.filter(w => w.frameInfo.scene == keepScene);
    };


    refEgoPose = {};
    getRefEgoPose(sceneName, currentPose) {
        if (this.refEgoPose[sceneName]) {
            return this.refEgoPose[sceneName];
        }
        else {
            this.refEgoPose[sceneName] = currentPose;
            return currentPose;
        }
    }

    removeRefEgoPoseOfScene(sceneName) {
        if (this.refEgoPose[sceneName])
            delete this.refEgoPose[sceneName];
    }

    forcePreloadScene(sceneName, currentWorld) {
        //this.deleteOtherWorldsExcept(sceneName);
        let meta = currentWorld.sceneMeta;

        let currentWorldIndex = currentWorld.frameInfo.frame_index;
        let startIndex = Math.max(0, currentWorldIndex - this.MaxWorldNumber / 2);
        let endIndex = Math.min(meta.frames.length, startIndex + this.MaxWorldNumber);

        this._doPreload(sceneName, startIndex, endIndex);

        logger.log(`${endIndex - startIndex} frames created`);
    }

    preloadScene(sceneName, currentWorld) {

        // clean other scenes.
        this.deleteOtherWorldsExcept(sceneName);
        this.deleteDistantWorlds(currentWorld);

        if (!this.cfg.enablePreload)
            return;

        this.forcePreloadScene(sceneName, currentWorld);

    };

    _doPreload(sceneName, startIndex, endIndex) {
        let meta = this.getMetaBySceneName(sceneName);

        let numLoaded = 0;
        let _need_create = (frame) => {
            let world = this.worldList.find((w) => {
                return w.frameInfo.scene == sceneName && w.frameInfo.frame == frame;
            })

            return !world;
        }

        let _do_create = (frame) => {
            this._createWorld(sceneName, frame);
            numLoaded++;
        };

        let pendingFrames = meta.frames.slice(startIndex, endIndex).filter(_need_create);

        logger.log(`preload ${meta.scene} ${pendingFrames}`);
        // if (numLoaded > 0){
        //     meta.frames.slice(endIndex, Math.min(endIndex+5, meta.frames.length)).forEach(_do_create);
        //     meta.frames.slice(Math.max(0, startIndex-5), startIndex).forEach(_do_create);
        // }

        pendingFrames.forEach(_do_create);
    }


    reloadAllAnnotation = function (done) {
        this.worldList.forEach(w => w.reloadAnnotation(done));
    };

    onAnnotationUpdatedByOthers(scene, frames) {
        frames.forEach(f => {
            let world = this.worldList.find(w => (w.frameInfo.scene == scene && w.frameInfo.frame == f));
            if (world)
                world.annotation.reloadAnnotation();
        })
    };

    webglScene = null;
    set_webglScene = function (scene, mainScene) {
        this.webglScene = scene;
        this.webglMainScene = mainScene;
    };

    scale_point_size(v) {
        this.cfg.point_size *= v;
        // if (this.world){
        //     this.world.lidar.set_point_size(this.cfg.point_size);
        // }

        this.worldList.forEach(w => {
            w.lidar.set_point_size(this.cfg.point_size);
        });
    };

    scale_point_brightness(v) {
        this.cfg.point_brightness *= v;

        // if (this.world){
        //     this.world.lidar.recolor_all_points();
        // }

        this.worldList.forEach(w => {
            w.lidar.recolor_all_points();
        })
    };

    set_box_opacity(opacity) {
        this.cfg.box_opacity = opacity;

        this.worldList.forEach(w => {
            w.annotation.set_box_opacity(this.cfg.box_opacity);
        });
    };

    toggle_background() {
        this.cfg.show_background = !this.cfg.show_background;

        if (this.cfg.show_background) {
            this.world.lidar.cancel_highlight();
        }
        else {
            this.world.lidar.hide_background();
        }
    };

    set_obj_color_scheme(scheme) {


        pointsGlobalConfig.color_obj = scheme;

        // toto: move to world
        this.worldList.forEach(w => {
            if (pointsGlobalConfig.color_obj == "no") {
                w.lidar.color_points();
            }
            else {
                w.lidar.color_objects();
            }

            w.lidar.update_points_color();

            w.annotation.color_boxes();
        })
    };

    world = null;

    activate_world = function (world, on_finished, dontDestroyOldWorld) {

        if (dontDestroyOldWorld) {
            world.activate(this.webglScene, null, on_finished);
        }
        else {
            var old_world = this.world;   // current world, should we get current world later?
            this.world = world;  // swich when everything is ready. otherwise data.world is half-baked, causing mysterious problems.

            world.activate(this.webglMainScene,
                function () {
                    if (old_world)
                        old_world.unload();
                },
                on_finished);
        }
    };


    meta = {};  //meta data

    getMetaBySceneName = (sceneName) => {
        return this.meta[sceneName];
    };


    get_current_world_scene_meta() {
        return this.getMetaBySceneName(this.world.frameInfo.scene);
    };


    readSceneMetaData(sceneName) {
        let self = this;
        return new Promise(function (resolve, reject) {
            let xhr = new XMLHttpRequest();

            xhr.onreadystatechange = function () {
                if (this.readyState != 4)
                    return;

                if (this.status == 200) {
                    let sceneMeta = JSON.parse(this.responseText);
                    self.meta[sceneName] = sceneMeta;
                    resolve(sceneMeta);
                }

            };

            xhr.open('GET', `/scenemeta?scene=${sceneName}`, true);
            xhr.send();
        });
    }
};


export { Data };

