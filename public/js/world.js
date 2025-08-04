import * as THREE from './lib/three.module.js';


import { Annotation } from "./annotation.js";
import { EgoPose } from "./ego_pose.js";
import { Lidar } from "./lidar.js";
import { logger } from "./log.js";

class FrameInfo {
    constructor(data, sceneMeta, sceneName, frame) {
        this.data = data;
        this.sceneMeta = sceneMeta;
        this.sceneName = sceneName;
        this.frame = frame;
        this.pcd_ext = "";
        this.dir = "";
        this.frame_index = this.sceneMeta.frames.findIndex(x => x === frame);
        this.transform_matrix = this.sceneMeta.point_transform_matrix;
    }

    get_pcd_path() {
        return this.sceneMeta.frameDetails[this.frame].pointcloud_url;
    }

    get_anno_path() {
        return `data/${this.sceneName}/label/${this.frame}.json`;
    }

    anno_to_boxes(text) {
        return JSON.parse(text);
    }

    transform_point(m, x, y, z) {
        return [
            x * m[0] + y * m[1] + z * m[2],
            x * m[3] + y * m[4] + z * m[5],
            x * m[6] + y * m[7] + z * m[8]
        ];
    }


    xyz_to_psr(ann_input) {
        const ann = (ann_input.length === 24) ? ann_input : ann_input.filter((_, i) => (i + 1) % 4 !== 0);

        const pos = { x: 0, y: 0, z: 0 };
        for (let i = 0; i < 8; i++) {
            pos.x += ann[i * 3];
            pos.y += ann[i * 3 + 1];
            pos.z += ann[i * 3 + 2];
        }
        pos.x /= 8; pos.y /= 8; pos.z /= 8;

        const scale = {
            x: Math.hypot(ann[0] - ann[3], ann[1] - ann[4]),
            y: Math.hypot(ann[0] - ann[9], ann[1] - ann[10]),
            z: ann[14] - ann[2]
        };

        const angle = Math.atan2(ann[4] + ann[7] - 2 * pos.y, ann[3] + ann[6] - 2 * pos.x);

        return {
            position: pos,
            scale,
            rotation: { x: 0, y: 0, z: angle }
        };
    }
}

class Images {
    constructor(sceneMeta, sceneName, frame) {
        this.sceneMeta = sceneMeta;
        this.sceneName = sceneName;
        this.frame = frame;
        this.names = sceneMeta.camera || [];
        this.loaded_flag = {};
        this.content = {};
        this.on_all_loaded = null;
    }

    loaded() {
        return this.names.every(name => this.loaded_flag[name]);
    }

    getImageByName(name) {
        return this.content[name];
    }

    load(on_all_loaded, active_name) {
        this.on_all_loaded = on_all_loaded;
        if (!this.names) return;

        this.names.forEach(cam => {
            const img = new Image();
            this.content[cam] = img;

            img.onload = () => {
                this.loaded_flag[cam] = true;
                this.on_image_loaded();
            };

            img.onerror = () => {
                this.loaded_flag[cam] = true;
                console.warn(`Image load failed: ${cam}`);
                this.on_image_loaded();
            };

            const imageUrl = this.sceneMeta.frameDetails?.[this.frame]?.images?.[cam];
            img.src = imageUrl;
        });
    }

    on_image_loaded() {
        if (this.loaded() && this.on_all_loaded) {
            this.on_all_loaded();
        }
    }
}

class World {
    constructor(data, sceneName, frame, coordinatesOffset, on_preload_finished) {
        this.data = data;
        this.sceneMeta = this.data.getMetaBySceneName(sceneName);
        this.frameInfo = new FrameInfo(this.data, this.sceneMeta, sceneName, frame);

        this.coordinatesOffset = coordinatesOffset;
        this.on_preload_finished = on_preload_finished;
        this.create_time = Date.now();
        this.webglGroup = new THREE.Group();
        this.webglGroup.name = "world";

        this.cameras = new Images(this.sceneMeta, sceneName, frame);
        this.lidar = new Lidar(this.sceneMeta, this, this.frameInfo);
        this.annotation = new Annotation(this.sceneMeta, this, this.frameInfo);
        this.egoPose = new EgoPose(this.sceneMeta, this, this.frameInfo);

        this.active = false;
        this.everythingDone = false;
        this.destroyed = false;

        this.scene = null;
        this.destroy_old_world = null;
        this.on_finished = null;

        this.preload(this.on_preload_finished);
    }

    preloaded() {
        return this.lidar.preloaded &&
            this.annotation.preloaded &&
            this.egoPose.preloaded;
    }

    preload(on_preload_finished) {
        const callback = () => this.on_subitem_preload_finished(on_preload_finished);
        this.lidar.preload(callback);
        this.annotation.preload(callback);
        this.cameras.load(callback);
        this.egoPose.preload(callback);
    }

    on_subitem_preload_finished(callback) {
        if (this.preloaded()) {
            logger.log(`finished preloading ${this.frameInfo.scene} ${this.frameInfo.frame}`);
            this.calcTransformMatrix();
            callback?.(this);
            if (this.active) this.go();
        }
    }

    calcTransformMatrix() {
        const identity = new THREE.Matrix4().identity();
        const offset = new THREE.Matrix4().setPosition(...this.coordinatesOffset);

        if (this.egoPose.egoPose) {
            const pose = this.egoPose.egoPose;
            const refPose = this.data.getRefEgoPose(this.frameInfo.scene, pose);

            const posDelta = {
                x: pose.translation[0] - refPose.translation[0],
                y: pose.translation[1] - refPose.translation[1],
                z: pose.translation[2] - refPose.translation[2]
            };

            const rotation = new THREE.Quaternion(
                pose.rotation[1], pose.rotation[2], pose.rotation[3], pose.rotation[0]
            );

            const trans_lidar_ego = identity;
            const trans_ego_utm = new THREE.Matrix4().makeRotationFromQuaternion(rotation).setPosition(posDelta.x, posDelta.y, posDelta.z);

            this.trans_lidar_utm = new THREE.Matrix4().multiplyMatrices(trans_ego_utm, trans_lidar_ego);
            this.trans_lidar_scene = (this.data.cfg.coordinateSystem === "utm")
                ? new THREE.Matrix4().multiplyMatrices(offset, this.trans_lidar_utm)
                : offset;

            this.trans_utm_lidar = new THREE.Matrix4().copy(this.trans_lidar_utm).invert();
            this.trans_scene_lidar = new THREE.Matrix4().copy(this.trans_lidar_scene).invert();
        } else {
            this.trans_lidar_utm = identity;
            this.trans_lidar_scene = offset;
            this.trans_utm_lidar = identity.clone();
            this.trans_scene_lidar = offset.clone().invert();
        }

        this.webglGroup.matrix.copy(this.trans_lidar_scene);
        this.webglGroup.matrixAutoUpdate = false;
    }

    activate(scene, destroy_old_world, on_finished) {
        this.scene = scene;
        this.active = true;
        this.destroy_old_world = destroy_old_world;
        this.on_finished = on_finished;
        if (this.preloaded()) {
            this.go();
        }
    }

    go() {
        if (this.everythingDone) {
            this.on_finished?.();
            return;
        }

        if (this.preloaded()) {
            this.destroy_old_world?.();
            if (this.destroyed) {
                this.unload();
                return;
            }

            this.scene.add(this.webglGroup);
            this.lidar.go(this.scene);
            this.annotation.go(this.scene);

            this.finish_time = Date.now();
            this.on_finished?.();
            this.everythingDone = true;
        }
    }

    unload() {
        if (this.everythingDone) {
            this.lidar.unload();
            this.annotation.unload();
            this.scene.remove(this.webglGroup);
            this.active = false;
            this.everythingDone = false;
        }
    }

    deleteAll() {
        logger.log(`delete world ${this.frameInfo.scene},${this.frameInfo.frame}`);
        if (this.everythingDone) this.unload();
        if (this.destroyed) return;
        this.lidar.deleteAll();
        this.annotation.deleteAll();
        this.destroyed = true;
    }
}

export { FrameInfo, Images, World };

