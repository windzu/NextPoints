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
        this.scene = sceneName;  // 添加 scene 属性以保持兼容性
        this.frame = frame;
        // this.dir = "";
        this.frame_index = this.sceneMeta.frames.findIndex(x => x === frame);
        this.transform_matrix = this.sceneMeta.point_transform_matrix;

        // 获取当前frame的详细信息，包括annotation和pose
        this.frameDetails = this.sceneMeta.frameDetails ? this.sceneMeta.frameDetails[this.frame] : null;
        this.annotation = this.frameDetails ? this.frameDetails.annotation : null;
        this.pose = this.frameDetails ? this.frameDetails.pose : null;
    }

    get_pcd_path() {
        // log
        logger.log(`get_pcd_path: ${this.sceneMeta.frameDetails[this.frame].pointcloud_url}`);
        return this.sceneMeta.frameDetails[this.frame].pointcloud_url;
    }

    anno_to_boxes(text) {
        let anno_json = JSON.parse(text);
        return anno_json;
    }

    transform_point(m, x, y, z) {
        return [
            x * m[0] + y * m[1] + z * m[2],
            x * m[3] + y * m[4] + z * m[5],
            x * m[6] + y * m[7] + z * m[8]
        ];
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

        this.scene = null;
        this.active = false;
        this.everythingDone = false;
        this.destroyed = false;
        this.destroy_old_world = null;
        this.on_finished = null;

        this.preload(this.on_preload_finished);
    }

    toString() {
        return `${this.frameInfo.scene},${this.frameInfo.frame}`;
    }

    preloaded() {
        return this.lidar.preloaded &&
            this.annotation.preloaded &&
            this.egoPose.preloaded
    }

    preload(callback) {
        const cb = () => this.on_subitem_preload_finished(callback);
        this.lidar.preload(cb);
        this.annotation.preload(cb);
        this.cameras.load(cb);
        this.egoPose.preload(cb);
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
                x: pose.transform.translation.x - refPose.transform.translation.x,
                y: pose.transform.translation.y - refPose.transform.translation.y,
                z: pose.transform.translation.z - refPose.transform.translation.z
            };

            const rotation = new THREE.Quaternion(
                pose.transform.rotation.x, pose.transform.rotation.y, pose.transform.rotation.z, pose.transform.rotation.w
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
            this.trans_lidar_utm = identity.clone();
            this.trans_lidar_scene = offset.clone();
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
        if (this.preloaded()) this.go();
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

    add_line(start, end, color) {
        const line = this.new_line(start, end, color);
        this.scene.add(line);
    }

    new_line(start, end, color = 0x00ff00) {
        const vertex = start.concat(end);
        this.data.dbg.alloc();
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertex, 3));
        const material = new THREE.LineBasicMaterial({ color, linewidth: 1, opacity: this.data.cfg.box_opacity, transparent: true });
        return new THREE.LineSegments(geometry, material);
    }

    scenePosToLidar(pos) {
        return new THREE.Vector4(pos.x, pos.y, pos.z, 1).applyMatrix4(this.trans_scene_lidar);
    }

    lidarPosToScene(pos) {
        return new THREE.Vector3(pos.x, pos.y, pos.z).applyMatrix4(this.trans_lidar_scene);
    }

    lidarPosToUtm(pos) {
        return new THREE.Vector3(pos.x, pos.y, pos.z).applyMatrix4(this.trans_lidar_utm);
    }

    static toQuat(rot) {
        if (!rot) return new THREE.Quaternion();           // identity
        if (rot.isQuaternion) return rot.clone();          // 已是四元数
        if (rot.isEuler) return new THREE.Quaternion().setFromEuler(rot);  // 从欧拉转
        if (Array.isArray(rot) && rot.length === 4) {      // 若是 [w,x,y,z]
            const [w, x, y, z] = rot;
            return new THREE.Quaternion(x ?? 0, y ?? 0, z ?? 0, w ?? 1);
        }
        // {x,y,z,w} 对象
        if ('x' in rot && 'y' in rot && 'z' in rot) {
            return new THREE.Quaternion(rot.x ?? 0, rot.y ?? 0, rot.z ?? 0, rot.w ?? 1);
        }
        throw new Error('Unsupported rotation format: ' + JSON.stringify(rot));
    }

    // scene → lidar
    sceneRotToLidarQuat(rot) {
        const qLocal = World.toQuat(rot);
        const qParent = (this.trans_scene_lidar?.isMatrix4)
            ? new THREE.Quaternion().setFromRotationMatrix(this.trans_scene_lidar)
            : new THREE.Quaternion(); // identity
        return qLocal.multiply(qParent).normalize(); // 保持原顺序：local * parent
    }

    sceneRotToLidar(rotEulerOrQuat) {
        const order = rotEulerOrQuat?.isEuler ? rotEulerOrQuat.order : "XYZ";
        const q = this.sceneRotToLidarQuat(rotEulerOrQuat);
        return new THREE.Euler().setFromQuaternion(q, order);
    }

    // lidar → scene
    lidarRotToSceneQuat(rot) {
        const qLocal = World.toQuat(rot);
        const qParent = (this.trans_lidar_scene?.isMatrix4)
            ? new THREE.Quaternion().setFromRotationMatrix(this.trans_lidar_scene)
            : new THREE.Quaternion(); // identity(父级未就绪时不引发异常)
        return qLocal.multiply(qParent).normalize(); // 注意顺序：local * parent
    }

    lidarRotToScene(rotEulerOrQuat) {
        const eulerOrder = rotEulerOrQuat?.isEuler ? rotEulerOrQuat.order : "XYZ";
        const q = this.lidarRotToSceneQuat(rotEulerOrQuat);
        return new THREE.Euler().setFromQuaternion(q, eulerOrder);
    }

    // lidar → UTM
    lidarRotToUtmQuat(rot) {
        const qLocal = World.toQuat(rot);
        const qParent = (this.trans_lidar_utm?.isMatrix4)
            ? new THREE.Quaternion().setFromRotationMatrix(this.trans_lidar_utm)
            : new THREE.Quaternion();
        return qLocal.multiply(qParent).normalize(); // local * parent
    }

    lidarRotToUtm(rotEulerOrQuat) {
        const order = rotEulerOrQuat?.isEuler ? rotEulerOrQuat.order : "XYZ";
        const q = this.lidarRotToUtmQuat(rotEulerOrQuat);
        return new THREE.Euler().setFromQuaternion(q, order);
    }

    // UTM → lidar
    utmRotToLidarQuat(rot) {
        const qLocal = World.toQuat(rot);
        const qParent = (this.trans_utm_lidar?.isMatrix4)
            ? new THREE.Quaternion().setFromRotationMatrix(this.trans_utm_lidar)
            : new THREE.Quaternion();
        return qLocal.multiply(qParent).normalize(); // local * parent
    }

    utmRotToLidar(rotEulerOrQuat) {
        const order = rotEulerOrQuat?.isEuler ? rotEulerOrQuat.order : "XYZ";
        const q = this.utmRotToLidarQuat(rotEulerOrQuat);
        return new THREE.Euler().setFromQuaternion(q, order);
    }
}

export { FrameInfo, Images, World };

