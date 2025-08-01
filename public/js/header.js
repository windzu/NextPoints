
import { saveWorldList } from "./save.js";

var Header = function (ui, data, cfg, onProjectChanged, onFrameChanged, onObjectSelected, onCameraChanged) {

    this.ui = ui;
    this.data = data;
    this.cfg = cfg;
    this.boxUi = ui.querySelector("#box");
    this.refObjUi = ui.querySelector("#ref-obj");

    // 获取四个项目状态选择器
    this.projectSelectors = {
        unstarted: ui.querySelector("#unstarted-projects"),
        in_progress: ui.querySelector("#in-progress-projects"),
        completed: ui.querySelector("#completed-projects"),
        reviewed: ui.querySelector("#reviewed-projects")
    };

    this.frameSelectorUi = ui.querySelector("#frame-selector");
    this.objectSelectorUi = ui.querySelector("#object-selector");
    this.cameraSelectorUi = ui.querySelector("#camera-selector");
    this.changedMarkUi = ui.querySelector("#changed-mark");

    this.onProjectChanged = onProjectChanged;
    this.onFrameChanged = onFrameChanged;
    this.onObjectSelected = onObjectSelected;
    this.onCameraChanged = onCameraChanged;


    if (cfg.disableFrameSelector) {
        this.frameSelectorUi.style.display = "none";
    }

    if (cfg.disableCameraSelector) {
        this.cameraSelectorUi.style.display = "none";
    }

    // 更新项目选择器的方法
    this.updateProjectSelectors = function (projectList) {
        // 按状态分类项目
        const projectsByStatus = {
            unstarted: [],
            in_progress: [],
            completed: [],
            reviewed: []
        };

        // 将项目按状态分类
        projectList.forEach(project => {
            if (projectsByStatus[project.status]) {
                projectsByStatus[project.status].push(project);
            }
        });

        // 更新每个状态的选择器
        Object.keys(this.projectSelectors).forEach(status => {
            const selector = this.projectSelectors[status];
            if (selector) {
                let optionsHtml = `<option value="">${status}</option>`;
                projectsByStatus[status].forEach(project => {
                    optionsHtml += `<option value="${project.id}">${project.name} (${project.frame_count} frames)</option>`;
                });
                selector.innerHTML = optionsHtml;
            }
        });
    }

    // 初始化项目列表
    this.updateProjectSelectors(this.data.projectList || []);

    // 重新加载项目列表的按钮事件
    this.ui.querySelector("#btn-reload-scene-list").onclick = (event) => {
        this.data.readProjectList().then((projectList) => {
            this.updateProjectSelectors(projectList);
        });
    }

    // 绑定项目选择器的事件
    Object.values(this.projectSelectors).forEach(selector => {
        if (selector) {
            selector.onchange = (e) => {
                if (e.target.value) {
                    this.onProjectChanged(e);
                }
            };
        }
    });

    this.setObject = function (id) {
        this.objectSelectorUi.value = id;
    }

    this.clear_box_info = function () {
        this.boxUi.innerHTML = '';
    };

    this.update_box_info = function (box) {
        var scale = box.scale;
        var pos = box.position;
        var rotation = box.rotation;
        var points_number = box.world.lidar.get_box_points_number(box);
        let distance = Math.sqrt(pos.x * pos.x + pos.y * pos.y).toFixed(2);

        this.boxUi.innerHTML = "<span>" + box.obj_type + "-" + box.obj_track_id +
            (box.annotator ? ("</span> | <span title='annotator'>" + box.annotator) : "") +
            "</span> | <span title='distance'>" + distance +
            "</span> | <span title='position'>" + pos.x.toFixed(2) + " " + pos.y.toFixed(2) + " " + pos.z.toFixed(2) +
            "</span> | <span title='scale'>" + scale.x.toFixed(2) + " " + scale.y.toFixed(2) + " " + scale.z.toFixed(2) +
            "</span> | <span title='rotation'>" +
            (rotation.x * 180 / Math.PI).toFixed(2) + " " + (rotation.y * 180 / Math.PI).toFixed(2) + " " + (rotation.z * 180 / Math.PI).toFixed(2) +
            "</span> | <span title = 'points'>" +
            points_number + "</span> ";
        if (box.follows) {
            this.boxUi.innerHTML += "| F:" + box.follows.obj_track_id;
        }
    },

        this.set_ref_obj = function (marked_object) {
            this.refObjUi.innerHTML = "| Ref: " + marked_object.scene + "/" + marked_object.frame + ": " + marked_object.ann.obj_type + "-" + marked_object.ann.obj_id;
        },

        this.set_frame_info = function (scene, frame, on_scene_changed) {

            if (this.sceneSelectorUi.value != scene) {
                this.sceneSelectorUi.value = scene;
                on_scene_changed(scene);
            }

            this.frameSelectorUi.value = frame;
        },

        this.clear_frame_info = function (scene, frame) {

        },

        this.updateModifiedStatus = function () {
            let frames = this.data.worldList.filter(w => w.annotation.modified);
            if (frames.length > 0) {
                this.ui.querySelector("#changed-mark").className = 'ui-button alarm-mark';
            }
            else {
                this.ui.querySelector("#changed-mark").className = 'ui-button';
            }
        }

    this.ui.querySelector("#changed-mark").onmouseenter = () => {

        let items = "";
        let frames = this.data.worldList.filter(w => w.annotation.modified).map(w => w.frameInfo);
        frames.forEach(f => {
            items += "<div class='modified-world-item'>" + f.frame + '</div>';
        });

        if (frames.length > 0) {
            this.ui.querySelector("#changed-world-list").innerHTML = items;
            this.ui.querySelector("#changed-world-list-wrapper").style.display = 'inherit';
        }
    }

    this.ui.querySelector("#changed-mark").onmouseleave = () => {
        this.ui.querySelector("#changed-world-list-wrapper").style.display = 'none';
    }

    this.ui.querySelector("#save-button").onclick = () => {
        saveWorldList(this.data.worldList);
    }

    // 添加Run Model按钮事件处理
    this.ui.querySelector("#run-model-button").onclick = () => {
        this.runModel();
    };

    this.runModel = function () {
        // 获取当前标注数据路径
        let currentScene = this.sceneSelectorUi.value;
        let currentFrame = this.frameSelectorUi.value;

        if (!currentScene || !currentFrame) {
            console.error("Please select scene and frame first");
            return;
        }

        // 显示全屏遮罩 + loading
        let overlay = document.createElement('div');
        overlay.id = 'model-inference-overlay';
        overlay.style.position = 'fixed';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
        overlay.style.zIndex = '9999';
        overlay.style.display = 'flex';
        overlay.style.flexDirection = 'column';
        overlay.style.justifyContent = 'center';
        overlay.style.alignItems = 'center';
        overlay.style.color = '#fff';
        overlay.style.fontSize = '20px';
        overlay.innerHTML = `<div>正在标注中... <span id="model-inference-timer">0</span> 秒</div>`;

        document.body.appendChild(overlay);

        // 计时器
        let seconds = 0;
        let timerInterval = setInterval(() => {
            seconds += 1;
            document.getElementById('model-inference-timer').innerText = seconds;
        }, 1000);

        // 显示加载状态
        let runButton = this.ui.querySelector("#run-model-button");
        runButton.style.opacity = "0.5";
        runButton.style.pointerEvents = "none";

        console.log("Running model on scene:", currentScene, "frame:", currentFrame);

        // 发送请求到本地后端，由后端转发到推理服务器
        fetch('/run_model', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                scene: currentScene,
                frame: currentFrame
            })
        })
            .then(response => response.json())
            .then(data => {
                console.log('Model result:', data);
                clearInterval(timerInterval); // 清除计时器
                document.body.removeChild(overlay); // 移除遮罩

                // 恢复按钮状态
                runButton.style.opacity = "1";
                runButton.style.pointerEvents = "auto";

                if (data.success) {
                    alert('标注完成！耗时 ' + seconds + ' 秒');
                    this.handleModelResult(data);

                    // === 自动刷新页面 ===
                    location.reload();
                } else {
                    console.error('Model inference failed:', data.error);
                    alert('模型推理失败: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error running model:', error);
                clearInterval(timerInterval); // 清除计时器
                document.body.removeChild(overlay); // 移除遮罩
                // 恢复按钮状态
                runButton.style.opacity = "1";
                runButton.style.pointerEvents = "auto";
                alert('网络请求失败: ' + error);
            });
    };

    this.handleModelResult = function (result) {
        // 根据模型结果更新标注
        if (result.success && result.annotations) {
            console.log("Received", result.annotations.length, "annotations from model");

            // 重新加载当前帧的标注以显示新结果
            this.viewManager.world.annotation.reloadAnnotation(() => {
                console.log("Annotations updated from model inference");
                // 可选：显示成功消息
                // alert('模型推理完成，已更新标注结果');
            });
        }
    };
};


export { Header };
