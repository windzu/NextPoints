import { checkScene } from "./error_check.js";
import * as THREE from './lib/three.module.js';
import { logger } from "./log.js";




function reloadWorldList(worldList, done) {
    var xhr = new XMLHttpRequest();
    // we defined the xhr
    xhr.onreadystatechange = function () {
        if (this.readyState != 4) return;

        if (this.status == 200) {
            let anns = JSON.parse(this.responseText);

            // load annotations
            anns.forEach(a => {
                let world = worldList.find(w => {
                    return (w.frameInfo.scene == a.scene &&
                        w.frameInfo.frame == a.frame);
                });
                if (world) {
                    world.annotation.reapplyAnnotation(a.annotation);
                }
                else {
                    console.error("bug?");
                }

            });

            if (done)
                done();
        }
    };

    xhr.open('POST', "/loadworldlist", true);

    let para = worldList.map(w => {
        return {
            //todo: we could add an id, so as to associate world easily
            scene: w.frameInfo.scene,
            frame: w.frameInfo.frame,
        };
    });

    xhr.send(JSON.stringify(para));
}


var saveDelayTimer = null;
var pendingSaveList = [];

function saveWorldList(worldList) {
    worldList.forEach(w => {
        if (!pendingSaveList.includes(w))
            pendingSaveList.push(w);
    });

    if (saveDelayTimer) {
        clearTimeout(saveDelayTimer);
    }

    saveDelayTimer = setTimeout(() => {

        logger.log("save delay expired.");

        //pandingSaveList will be cleared soon.
        let scene = pendingSaveList[0].frameInfo.scene;


        doSaveWorldList(pendingSaveList, () => {
            editor.header.updateModifiedStatus();

            checkScene(scene);
        });

        //reset
        saveDelayTimer = null;
        pendingSaveList = [];


    },

        500);
}


function doSaveWorldList(worldList, done) {
    if (worldList.length > 0) {
        if (worldList[0].data.cfg.disableLabels) {
            console.log("labels not loaded, save action is prohibitted.")
            return;
        }
    }

    let ann = worldList.map(w => {
        return {
            scene: w.frameInfo.scene,
            frame: w.frameInfo.frame,
            annotation: w.annotation.toBoxAnnotations(),
        };
    })

    // convert ann[i].annotation[j].psr.rotation from euler {x,y,z} to qunt {x,y,z,w}
    ann.forEach(a => {
        a.annotation.forEach(box => {
            if (box.psr && box.psr.rotation) {
                // use three.js to convert
                let euler = new THREE.Euler(box.psr.rotation.x, box.psr.rotation.y, box.psr.rotation.z, 'XYZ');
                let quaternion = new THREE.Quaternion();
                quaternion.setFromEuler(euler);
                box.psr.rotation = { x: quaternion.x, y: quaternion.y, z: quaternion.z, w: quaternion.w };
            }
        });
    });

    var xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/projects/save_world_list", true);
    xhr.setRequestHeader('Content-Type', 'application/json');

    xhr.onreadystatechange = function () {
        if (this.readyState != 4) return;
        if (this.status == 200) {
            worldList.forEach(w => {
                w.annotation.resetModified();
            })

            logger.log(`saved: ${worldList[0].frameInfo.scene}: ${worldList.reduce((a, b) => a + " " + b.frameInfo.frame, "")}`);

            if (done) {
                done();
            }
        }
        else {
            window.editor.infoBox.show("Error", `save failed, status : ${this.status}`);
        }


        // end of state change: it can be after some time (async)
    };

    // debug
    console.log("[Save] Sending annotation data to server:", ann.slice(0, 2)); // 仅预览前两个，防止太长

    var b = JSON.stringify(ann);


    xhr.send(b);
}

export { reloadWorldList, saveWorldList };
