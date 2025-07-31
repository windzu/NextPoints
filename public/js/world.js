import * as THREE from './lib/three.module.js';


import { Annotation } from "./annotation.js";
import { AuxLidarManager } from "./aux_lidar.js";
import { EgoPose } from "./ego_pose.js";
import { Lidar } from "./lidar.js";
import { logger } from "./log.js";
import { RadarManager } from "./radar.js";

function FrameInfo(data, sceneMeta, sceneName, frame) {

    this.data = data;
    this.sceneMeta = sceneMeta;
    this.dir = "";
    this.scene = sceneName;
    this.frame = frame;
    this.pcd_ext = "";
    this.frame_index = this.sceneMeta.frames.findIndex(function (x) { return x == frame; }),
        this.transform_matrix = this.sceneMeta.point_transform_matrix,
        this.annotation_format = this.sceneMeta.boxtype, //xyz(24 number), csr(center, scale, rotation, 9 number)



        // this.set = function(scene, frame_index, frame, transform_matrix, annotation_format){
        //         this.scene = scene;
        //         this.frame = frame;
        //         this.frame_index = frame_index;
        //         this.transform_matrix = transform_matrix;
        //         this.annotation_format = annotation_format;
        // };


        this.get_pcd_path = function () {
            return 'data/' + this.scene + "/lidar/" + this.frame + this.sceneMeta.lidar_ext;
        };
    this.get_radar_path = function (name) {
        return `data/${this.scene}/radar/${name}/${this.frame}${this.sceneMeta.radar_ext}`;
    };
    this.get_aux_lidar_path = function (name) {
        return `data/${this.scene}/aux_lidar/${name}/${this.frame}${this.sceneMeta.radar_ext}`;
    }

    this.get_anno_path = function () {
        if (this.annotation_format == "psr") {
            return 'data/' + this.scene + "/label/" + this.frame + ".json";
        }
        else {
            return 'data/' + this.scene + "/bbox.xyz/" + this.frame + ".bbox.txt";
        }

    };

    this.anno_to_boxes = function (text) {
        var _self = this;
        if (this.annotation_format == "psr") {

            var boxes = JSON.parse(text);


            return boxes;
        }
        else
            return this.python_xyz_to_psr(text);

    };
    this.transform_point = function (m, x, y, z) {
        var rx = x * m[0] + y * m[1] + z * m[2];
        var ry = x * m[3] + y * m[4] + z * m[5];
        var rz = x * m[6] + y * m[7] + z * m[8];

        return [rx, ry, rz];
    };

    /*
    input is coordinates of 8 vertices
    bottom-left-front, bottom-right-front, bottom-right-back, bottom-left-back
    top-left-front,    top-right-front,    top-right-back,    top-left-back

    this format is what SECOND/PointRcnn save their results.
    */
    this.python_xyz_to_psr = function (text) {
        var _self = this;

        var points_array = text.split('\n').filter(function (x) { return x; }).map(function (x) { return x.split(' ').map(function (x) { return parseFloat(x); }) })


        var boxes = points_array.map(function (ps) {
            for (var i = 0; i < 8; i++) {
                var p = _self.transform_point(_self.transform_matrix, ps[3 * i + 0], ps[3 * i + 1], ps[3 * i + 2]);
                ps[i * 3 + 0] = p[0];
                ps[i * 3 + 1] = p[1];
                ps[i * 3 + 2] = p[2];
            }
            return ps;
        });

        var boxes_ann = boxes.map(this.xyz_to_psr);

        return boxes_ann; //, boxes];
    };

    this.xyz_to_psr = function (ann_input) {
        var ann = [];
        if (ann_input.length == 24)
            ann = ann_input;
        else
            for (var i = 0; i < ann_input.length; i++) {
                if ((i + 1) % 4 != 0) {
                    ann.push(ann_input[i]);
                }
            }

        var pos = { x: 0, y: 0, z: 0 };
        for (var i = 0; i < 8; i++) {
            pos.x += ann[i * 3];
            pos.y += ann[i * 3 + 1];
            pos.z += ann[i * 3 + 2];
        }
        pos.x /= 8;
        pos.y /= 8;
        pos.z /= 8;

        var scale = {
            x: Math.sqrt((ann[0] - ann[3]) * (ann[0] - ann[3]) + (ann[1] - ann[4]) * (ann[1] - ann[4])),
            y: Math.sqrt((ann[0] - ann[9]) * (ann[0] - ann[9]) + (ann[1] - ann[10]) * (ann[1] - ann[10])),
            z: ann[14] - ann[2],
        };

        /*
        1. atan2(y,x), not x,y
        2. point order in xy plane
            0   1
            3   2
        */

        var angle = Math.atan2(ann[4] + ann[7] - 2 * pos.y, ann[3] + ann[6] - 2 * pos.x);

        return {
            position: pos,
            scale: scale,
            rotation: { x: 0, y: 0, z: angle },
        }
    };
}

function Images(sceneMeta, sceneName, frame) {
    this.loaded = function () {
        for (var n in this.names) {
            if (!this.loaded_flag[this.names[n]])
                return false;
        }

        return true;
    };

    this.names = sceneMeta.camera; //["image","left","right"],
    this.loaded_flag = {};
    // this.active_name = "";
    // this.active_image = function(){
    //     return this.content[this.active_name];
    // };
    this.getImageByName = function (name) {
        return this.content[name];
    };

    // this.activate = function(name){
    //     this.active_name = name;
    // };

    this.content = {};
    this.on_all_loaded = null;

    this.load = function (on_all_loaded, active_name) {
        this.on_all_loaded = on_all_loaded;

        // if global camera not set, use first camera as default.
        // if (active_name.length > 0)
        //     this.active_name = active_name;
        // else if (this.names && this.names.length>0)
        //     this.active_name = this.names[0];

        var _self = this;

        if (this.names) {
            this.names.forEach(function (cam) {
                _self.content[cam] = new Image();
                _self.content[cam].onload = function () {
                    _self.loaded_flag[cam] = true;
                    _self.on_image_loaded();
                };
                _self.content[cam].onerror = function () {
                    _self.loaded_flag[cam] = true;
                    _self.on_image_loaded();
                };

                _self.content[cam].src = 'data/' + sceneName + '/camera/' + cam + '/' + frame + sceneMeta.camera_ext;
                // console.log("image set")
            });
        }
    },

        this.on_image_loaded = function () {
            if (this.loaded()) {
                this.on_all_loaded();
            }
        }
}



function World(data, sceneName, frame, coordinatesOffset, on_preload_finished) {
    this.data = data;
    this.sceneMeta = this.data.getMetaBySceneName(sceneName);
    this.frameInfo = new FrameInfo(this.data, this.sceneMeta, sceneName, frame);


    this.coordinatesOffset = coordinatesOffset;


    this.toString = function () {
        return this.frameInfo.scene + "," + this.frameInfo.frame;
    }
    //points_backup: null, //for restore from highlight

    this.cameras = new Images(this.sceneMeta, sceneName, frame);
    this.radars = new RadarManager(this.sceneMeta, this, this.frameInfo);
    this.lidar = new Lidar(this.sceneMeta, this, this.frameInfo);
    this.annotation = new Annotation(this.sceneMeta, this, this.frameInfo);
    this.aux_lidars = new AuxLidarManager(this.sceneMeta, this, this.frameInfo);
    this.egoPose = new EgoPose(this.sceneMeta, this, this.FrameInfo);

    // todo: state of world could be put in  a variable
    // but still need mulitple flags.

    this.points_loaded = false,

        this.preloaded = function () {
            return this.lidar.preloaded &&
                this.annotation.preloaded &&
                //this.cameras.loaded() &&
                this.aux_lidars.preloaded() &&
                this.radars.preloaded() &&
                this.egoPose.preloaded;
        };

    this.create_time = 0;
    this.finish_time = 0;
    this.on_preload_finished = null;

    this.on_subitem_preload_finished = function (on_preload_finished) {
        if (this.preloaded()) {

            logger.log(`finished preloading ${this.frameInfo.scene} ${this.frameInfo.frame}`);

            this.calcTransformMatrix();


            if (this.on_preload_finished) {
                this.on_preload_finished(this);
            }

            if (this.active) {
                this.go();
            }
        }
    };


    this.calcTransformMatrix = function () {
        if (this.egoPose.egoPose) {

            let thisPose = this.egoPose.egoPose;

            // 使用的是当前帧的姿态, 但是这个姿态是相对于参考帧的姿态的变换(局部定位)
            let refPose = this.data.getRefEgoPose(this.frameInfo.scene, thisPose);

            let thisRot = {
                w: thisPose.rotation[0],
                x: thisPose.rotation[1],
                y: thisPose.rotation[2],
                z: thisPose.rotation[3],
            };

            let posDelta = {
                x: thisPose.translation[0] - refPose.translation[0],
                y: thisPose.translation[1] - refPose.translation[1],
                z: thisPose.translation[2] - refPose.translation[2],
            };



            // lidar to ego
            // Note : 这里应该使用的是lidar到ego的标定参数, 但是我们的点云是已经变换到ego坐标系的, 所以这里的变换矩阵是单位矩阵
            let trans_lidar_ego = new THREE.Matrix4().identity();

            // ego to utm(global)
            // Note : get let trans_ego_utm from quaternion and position instead of euler angles
            let trans_ego_utm = new THREE.Matrix4().makeRotationFromQuaternion(new THREE.Quaternion(thisRot.x, thisRot.y, thisRot.z, thisRot.w)).setPosition(posDelta.x, posDelta.y, posDelta.z);

            // utm to scene
            // Note : 这里的scene 指代的是在正常 utm 坐标的基础之上 ,为了避免点云重叠而设置的偏移量
            let trans_utm_scene = new THREE.Matrix4().identity().setPosition(this.coordinatesOffset[0], this.coordinatesOffset[1], this.coordinatesOffset[2]);

            // lidar to utm
            this.trans_lidar_utm = new THREE.Matrix4().multiplyMatrices(trans_ego_utm, trans_lidar_ego);

            // lidar to scene
            // Note : 这里计算最终的变换矩阵, 从lidar坐标系到scene坐标系
            // 如果坐标系是utm, 那么就是 lidar -> utm -> scene
            // 如果坐标系不是utm, 那么就是 utm -> scene(没有全局坐标,只有人为设置的offset)
            if (this.data.cfg.coordinateSystem == "utm")
                this.trans_lidar_scene = new THREE.Matrix4().multiplyMatrices(trans_utm_scene, this.trans_lidar_utm);
            else
                this.trans_lidar_scene = trans_utm_scene;  // only offset.

            this.trans_utm_lidar = new THREE.Matrix4().copy(this.trans_lidar_utm).invert();
            this.trans_scene_lidar = new THREE.Matrix4().copy(this.trans_lidar_scene).invert();

        }
        else {
            let trans_utm_scene = new THREE.Matrix4().identity().setPosition(this.coordinatesOffset[0], this.coordinatesOffset[1], this.coordinatesOffset[2]);
            let id = new THREE.Matrix4().identity();

            this.trans_lidar_utm = id;
            this.trans_lidar_scene = trans_utm_scene;

            this.trans_utm_lidar = new THREE.Matrix4().copy(this.trans_lidar_utm).invert();
            this.trans_scene_lidar = new THREE.Matrix4().copy(this.trans_lidar_scene).invert();
        }

        this.webglGroup.matrix.copy(this.trans_lidar_scene);
        this.webglGroup.matrixAutoUpdate = false;
    };

    // global scene 
    this.scenePosToLidar = function (pos) {
        let tp = new THREE.Vector4(pos.x, pos.y, pos.z, 1).applyMatrix4(this.trans_scene_lidar);

        return tp;
    }

    // global scene
    this.lidarPosToScene = function (pos) {
        let tp = new THREE.Vector3(pos.x, pos.y, pos.z).applyMatrix4(this.trans_lidar_scene);
        return tp;
    }

    // global scene
    this.lidarPosToUtm = function (pos) {
        let tp = new THREE.Vector3(pos.x, pos.y, pos.z).applyMatrix4(this.trans_lidar_utm);

        return tp;
    }



    this.sceneRotToLidar = function (rotEuler) {
        if (!rotEuler.isEuler) {
            rotEuler = new THREE.Euler(rotEuler.x, rotEuler.y, rotEuler.z, "XYZ");
        }

        let rotG = new THREE.Quaternion().setFromEuler(rotEuler);
        let GlobalToLocalRot = new THREE.Quaternion().setFromRotationMatrix(this.trans_scene_lidar);

        let retQ = rotG.multiply(GlobalToLocalRot);

        let retEuler = new THREE.Euler().setFromQuaternion(retQ, rotEuler.order);

        return retEuler;
    }

    this.lidarRotToScene = function (rotEuler) {
        if (!rotEuler.isEuler) {
            rotEuler = new THREE.Euler(rotEuler.x, rotEuler.y, rotEuler.z, "XYZ");
        }

        let rotL = new THREE.Quaternion().setFromEuler(rotEuler);
        let localToGlobalRot = new THREE.Quaternion().setFromRotationMatrix(this.trans_lidar_scene)

        let retQ = rotL.multiply(localToGlobalRot);

        let retEuler = new THREE.Euler().setFromQuaternion(retQ, rotEuler.order);

        return retEuler;
    }

    this.lidarRotToUtm = function (rotEuler) {
        if (!rotEuler.isEuler) {
            rotEuler = new THREE.Euler(rotEuler.x, rotEuler.y, rotEuler.z, "XYZ");
        }

        let rotL = new THREE.Quaternion().setFromEuler(rotEuler);
        let localToGlobalRot = new THREE.Quaternion().setFromRotationMatrix(this.trans_lidar_utm)

        let retQ = rotL.multiply(localToGlobalRot);

        let retEuler = new THREE.Euler().setFromQuaternion(retQ, rotEuler.order);

        return retEuler;
    }

    this.utmRotToLidar = function (rotEuler) {
        if (!rotEuler.isEuler) {
            rotEuler = new THREE.Euler(rotEuler.x, rotEuler.y, rotEuler.z, "XYZ");
        }

        let rot = new THREE.Quaternion().setFromEuler(rotEuler);
        let trans = new THREE.Quaternion().setFromRotationMatrix(this.trans_utm_lidar);

        let retQ = rot.multiply(trans);

        let retEuler = new THREE.Euler().setFromQuaternion(retQ, rotEuler.order);

        return retEuler;
    }


    this.preload = function (on_preload_finished) {
        this.create_time = new Date().getTime();
        // console.log(this.create_time, sceneName, frame, "start");

        this.webglGroup = new THREE.Group();
        this.webglGroup.name = "world";


        let _preload_cb = () => this.on_subitem_preload_finished(on_preload_finished);

        this.lidar.preload(_preload_cb);
        this.annotation.preload(_preload_cb)
        this.radars.preload(_preload_cb);
        this.cameras.load(_preload_cb, this.data.active_camera_name);
        this.aux_lidars.preload(_preload_cb);
        this.egoPose.preload(_preload_cb);
    };

    this.scene = null,
        this.destroy_old_world = null, //todo, this can be a boolean
        this.on_finished = null,
        this.activate = function (scene, destroy_old_world, on_finished) {
            this.scene = scene;
            this.active = true;
            this.destroy_old_world = destroy_old_world;
            this.on_finished = on_finished;
            if (this.preloaded()) {
                this.go();
            }
        };

    this.active = false,
        this.everythingDone = false;

    this.go = function () {

        if (this.everythingDone) {
            //console.error("re-activate world?");

            //however we still call on_finished
            if (this.on_finished) {
                this.on_finished();
            }
            return;
        }

        if (this.preloaded()) {

            //this.points.material.size = data.cfg.point_size;

            if (this.destroy_old_world) {
                this.destroy_old_world();
            }

            if (this.destroyed) {
                // console.log("go after destroyed.");
                this.unload();
                return;
            }

            this.scene.add(this.webglGroup);

            this.lidar.go(this.scene);
            this.annotation.go(this.scene);
            this.radars.go(this.scene);
            this.aux_lidars.go(this.scene);


            this.finish_time = new Date().getTime();
            // console.log(this.finish_time, sceneName, frame, "loaded in ", this.finish_time - this.create_time, "ms");


            // render is called in on_finished() callback
            if (this.on_finished) {
                this.on_finished();
            }

            this.everythingDone = true;
        }
    };


    this.add_line = function (start, end, color) {
        var line = this.new_line(start, end, color);
        this.scene.add(line);
    };



    this.new_line = function (start, end, color) {

        var vertex = start.concat(end);
        this.world.data.dbg.alloc();
        var line = new THREE.BufferGeometry();
        line.addAttribute('position', new THREE.Float32BufferAttribute(vertex, 3));

        if (!color) {
            color = 0x00ff00;
        }

        var material = new THREE.LineBasicMaterial({ color: color, linewidth: 1, opacity: this.data.cfg.box_opacity, transparent: true });
        return new THREE.LineSegments(line, material);
    };



    this.destroyed = false;

    // todo, Image resource to be released?

    this.unload = function () {
        if (this.everythingDone) {
            //unload all from scene, but don't destroy elements
            this.lidar.unload();
            this.radars.unload();
            this.aux_lidars.unload();
            this.annotation.unload();

            this.scene.remove(this.webglGroup);

            this.active = false;
            this.everythingDone = false;
        }
    };



    this.deleteAll = function () {
        var _self = this;

        logger.log(`delete world ${this.frameInfo.scene},${this.frameInfo.frame}`);

        if (this.everythingDone) {
            this.unload();
        }

        // todo, check if all objects are removed from webgl scene.
        if (this.destroyed) {
            // console.log("destroy destroyed world!");
        }

        this.lidar.deleteAll();
        this.radars.deleteAll();
        this.aux_lidars.deleteAll();
        this.annotation.deleteAll();

        this.destroyed = true;
        // console.log(this.frameInfo.scene, this.frameInfo.frame, "destroyed");
        // remove me from buffer
    };

    this.preload(on_preload_finished);
}

export { World };

