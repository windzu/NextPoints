import { globalKeyDownManager } from "./keydown_manager.js";
import { logger } from "./log.js";

class ConfigUi {

    clickableItems = {
        "#cfg-increase-size": (event) => {
            this.editor.data.scale_point_size(1.2);
            this.editor.render();
            this.editor.boxEditorManager.render();
            return false;
        },

        "#cfg-decrease-size": (event) => {
            this.editor.data.scale_point_size(0.8);
            this.editor.render();
            this.editor.boxEditorManager.render();
            return false;
        },

        "#cfg-increase-brightness": (event) => {
            this.editor.data.scale_point_brightness(1.2);
            this.editor.render();
            this.editor.boxEditorManager.render();
            return false;
        },

        "#cfg-decrease-brightness": (event) => {
            this.editor.data.scale_point_brightness(0.8);
            this.editor.render();
            this.editor.boxEditorManager.render();
            return false;
        },

        "#cfg-take-screenshot": (event) => {
            this.editor.downloadWebglScreenShot();
            return true;
        },

        "#cfg-show-log": (event) => {
            logger.show();
            return true;
        },

        "#cfg-start-calib": (event) => {
            this.editor.calib.start_calibration();
            return true;
        },

        "#cfg-show-calib": (event) => {
            this.editor.calib.save_calibration();
            return true;
        },

        // "#cfg-reset-calib":(event)=>{
        //     this.editor.calib.reset_calibration();
        //     return true;
        // }

        "#cfg-crop-scene": (event) => {
            this.editor.cropScene.show();

            return true;
        },

        // New: Delete current project
        "#cfg-delete-current-project": async (event) => {
            const header = this.editor.header;
            const projectName = header.getSelectedProjectName?.();
            if (!projectName) {
                alert("Please select a project first.");
                return true;
            }

            // Confirm via InfoBox
            const message = `Delete project "${projectName}"? This removes it from the database but does not delete data in S3.`;
            let userChoice = await new Promise((resolve) => {
                this.editor.infoBox.show("Confirm", message, ["yes", "no"], (choice) => resolve(choice));
            });
            if (userChoice !== "yes") return true;

            try {
                const resp = await fetch(`/api/projects/${encodeURIComponent(projectName)}`, { method: "DELETE" });
                if (!resp.ok) {
                    const msg = await resp.text();
                    throw new Error(`HTTP ${resp.status}: ${msg}`);
                }
                // Clear UI state
                header.clearProjectSelection?.();
                if (this.editor.data.world) {
                    this.editor.clear();
                }
                // Refresh project list in header
                const list = await this.editor.data.readProjectList();
                header.updateProjectSelectors(list);
                alert(`Project ${projectName} deleted.`);
            } catch (err) {
                console.error("Delete project failed:", err);
                alert(`Delete failed: ${err.message}`);
            }
            return true;
        },

        // Create Project: open dialog and handle submission
        "#cfg-create-project": (event) => {
            this.openCreateProjectDialog();
            return true;
        },

        // New: Update project status menu item
        "#cfg-update-project-status": (event) => {
            // Do nothing on main item click to keep submenu open
            return false; // prevent menu auto-hide
        },

    };

    changeableItems = {

        "#cfg-theme-select": (event) => {
            let theme = event.currentTarget.value;

            //let scheme = document.documentElement.className;


            document.documentElement.className = "theme-" + theme;

            pointsGlobalConfig.setItem("theme", theme);

            this.editor.viewManager.setColorScheme();
            this.editor.render();
            this.editor.boxEditorManager.render();

            return false;
        },

        "#cfg-hide-box-checkbox": (event) => {
            let checked = event.currentTarget.checked;

            //let scheme = document.documentElement.className;

            if (checked)
                this.editor.data.set_box_opacity(0);
            else
                this.editor.data.set_box_opacity(1);

            this.editor.render();
            this.editor.boxEditorManager.render();


            return false;
        },


        "#cfg-hide-id-checkbox": (event) => {
            let checked = event.currentTarget.checked;
            this.editor.floatLabelManager.show_id(!checked);
            return false;
        },



        "#cfg-hide-category-checkbox": (event) => {
            let checked = event.currentTarget.checked;
            this.editor.floatLabelManager.show_category(!checked);
            return false;
        },

        "#cfg-hide-circle-ruler-checkbox": (event) => {
            let checked = event.currentTarget.checked;
            this.editor.showRangeCircle(!checked);
            return false;
        },

        "#cfg-hide-ground-checkbox": (event) => {
            let checked = event.currentTarget.checked;
            this.editor.showGround(!checked);
            return false;
        },

        "#cfg-auto-rotate-xy-checkbox": (event) => {
            let checked = event.currentTarget.checked;
            pointsGlobalConfig.setItem("enableAutoRotateXY", checked);
            return false;
        },

        '#cfg-auto-update-interpolated-boxes-checkbox': (event) => {
            let checked = event.currentTarget.checked;
            pointsGlobalConfig.setItem("autoUpdateInterpolatedBoxes", checked);
            return false;
        },

        "#cfg-color-points-select": (event) => {
            let value = event.currentTarget.value;
            pointsGlobalConfig.setItem("color_points", value);

            this.editor.data.worldList.forEach(w => {
                w.lidar.color_points();
                w.lidar.update_points_color();
            });
            this.editor.render();
            return false;
        },

        "#cfg-color-object-scheme": (event) => {
            let value = event.currentTarget.value;
            this.editor.data.set_obj_color_scheme(value);
            this.editor.render();
            this.editor.imageContextManager.render_2d_image();

            this.editor.floatLabelManager.set_color_scheme(value);
            this.editor.render2dLabels(this.editor.data.world);
            this.editor.boxEditorManager.render();

            return false;
        },

        "#cfg-batch-mode-inst-number": (event) => {
            let batchSize = parseInt(event.currentTarget.value);

            pointsGlobalConfig.setItem("batchModeInstNumber", batchSize);

            this.editor.boxEditorManager.setBatchSize(batchSize);
            return false;
        },

        "#cfg-coordinate-system-select": (event) => {
            let coord = event.currentTarget.value;
            pointsGlobalConfig.setItem("coordinateSystem", coord);

            this.editor.data.worldList.forEach(w => {
                w.calcTransformMatrix();
            });
            this.editor.render();
        },

        "#cfg-data-filter-points-checkbox": (event) => {
            let checked = event.currentTarget.checked;

            pointsGlobalConfig.setItem("enableFilterPoints", checked);
            return false;
        },

        "#cfg-data-filter-points-z": (event) => {
            let z = event.currentTarget.value;

            pointsGlobalConfig.setItem("filterPointsZ", z);
            return false;
        },


        "#cfg-data-preload-checkbox": (event) => {
            let checked = event.currentTarget.checked;
            pointsGlobalConfig.setItem("enablePreload", checked);
            return false;
        }

    };

    ignoreItems = [
        "#cfg-point-size",
        "#cfg-point-brightness",
        "#cfg-theme",
        "#cfg-color-object",
        "#cfg-menu-batch-mode-inst-number",
        "#cfg-hide-box",
        "#cfg-calib-camera-LiDAR",
        "#cfg-experimental",
        "#cfg-data",
        "#cfg-update-project-status",
        "#cfg-export", // new export submenu root
    ];

    subMenus = [
        "#cfg-experimental",
        "#cfg-data",
        "#cfg-update-project-status",
        "#cfg-export", // export submenu
    ];

    constructor(button, wrapper, editor) {
        this.button = button;
        this.wrapper = wrapper;
        this.editor = editor;
        this.editorCfg = editor.editorCfg;
        this.dataCfg = editor.data.cfg;
        this.menu = this.wrapper.querySelector("#config-menu");

        this.wrapper.onclick = () => {
            this.hide();
        }

        this.button.onclick = (event) => {
            this.show(event.currentTarget);
        }

        for (let item in this.clickableItems) {
            this.menu.querySelector(item).onclick = (event) => {
                let ret = this.clickableItems[item](event);
                if (ret) {
                    this.hide();
                }

                event.stopPropagation();
            }
        }

        for (let item in this.changeableItems) {
            this.menu.querySelector(item).onchange = (event) => {
                let ret = this.changeableItems[item](event);
                if (ret) {
                    this.hide();
                }

                event.stopPropagation();
            }
        }

        this.ignoreItems.forEach(item => {
            this.menu.querySelector(item).onclick = (event) => {
                {
                    event.stopPropagation();
                }
            }
        });

        this.subMenus.forEach(item => {
            this.menu.querySelector(item).onmouseenter = function (event) {
                if (this.timerId) {
                    clearTimeout(this.timerId);
                    this.timerId = null;
                }
                event.currentTarget.querySelector(item + "-submenu").style.display = "inherit";
            }

            this.menu.querySelector(item).onmouseleave = function (event) {
                let ui = event.currentTarget.querySelector(item + "-submenu");
                this.timerId = setTimeout(() => {
                    ui.style.display = "none";
                    this.timerId = null;
                },
                    200);
            }
        });

        this.menu.onclick = (event) => {
            event.stopPropagation();
        };



        // init ui
        this.menu.querySelector("#cfg-theme-select").value = pointsGlobalConfig.theme;
        this.menu.querySelector("#cfg-color-points-select").value = pointsGlobalConfig.color_points;
        this.menu.querySelector("#cfg-coordinate-system-select").value = pointsGlobalConfig.coordinateSystem;
        this.menu.querySelector("#cfg-batch-mode-inst-number").value = pointsGlobalConfig.batchModeInstNumber;
        this.menu.querySelector("#cfg-data-filter-points-checkbox").checked = pointsGlobalConfig.enableFilterPoints;
        this.menu.querySelector("#cfg-data-filter-points-z").value = pointsGlobalConfig.filterPointsZ;
        this.menu.querySelector("#cfg-hide-id-checkbox").value = pointsGlobalConfig.hideId;
        this.menu.querySelector("#cfg-hide-category-checkbox").value = pointsGlobalConfig.hideCategory;
        this.menu.querySelector("#cfg-data-preload-checkbox").checked = pointsGlobalConfig.enablePreload;
        this.menu.querySelector("#cfg-auto-rotate-xy-checkbox").checked = pointsGlobalConfig.enableAutoRotateXY;
        this.menu.querySelector("#cfg-auto-update-interpolated-boxes-checkbox").checked = pointsGlobalConfig.autoUpdateInterpolatedBoxes;

        // Bind status submenu items (after submenu logic)
        const statusSub = this.menu.querySelector('#cfg-update-project-status-submenu');
        if (statusSub) {
            statusSub.querySelectorAll('.status-option').forEach(opt => {
                opt.onclick = async (e) => {
                    e.stopPropagation();
                    const status = opt.getAttribute('data-status');
                    const header = this.editor.header;
                    const projectName = header.getSelectedProjectName?.();
                    if (!projectName) {
                        this.editor.infoBox.show('Notice', '请先选择一个项目 (Select a project first)');
                        return;
                    }
                    try {
                        const resp = await fetch(`/api/projects/update_project_status`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ project_name: projectName, status: status })
                        });
                        if (!resp.ok) {
                            const msg = await resp.text();
                            throw new Error(`HTTP ${resp.status}: ${msg}`);
                        }
                        const updated = await resp.json();
                        const list = await this.editor.data.readProjectList();
                        header.updateProjectSelectors?.(list);
                        const sel = header.projectSelectors?.[updated.status];
                        if (sel) {
                            for (const opt2 of sel.options) {
                                if (opt2.value === projectName) { sel.value = projectName; break; }
                            }
                            header.resetOtherProjectSelectors?.(sel);
                        }
                        this.editor.infoBox.show('Success', `状态已更新为 ${updated.status}`);
                        // auto hide submenu after selection
                        statusSub.style.display = 'none';
                    } catch (err) {
                        console.error('Update status failed', err);
                        this.editor.infoBox.show('Error', `更新失败: ${err.message}`);
                    }
                };
            });
        }

        // After other submenu bindings, bind export submenu option clicks
        const exportSub = this.menu.querySelector('#cfg-export-submenu');
        if (exportSub) {
            exportSub.querySelectorAll('.export-option').forEach(opt => {
                opt.onclick = async (e) => {
                    e.stopPropagation();
                    const target = opt.getAttribute('data-export-format');
                    const header = this.editor.header;
                    const projectName = header.getSelectedProjectName?.();
                    if (!projectName) {
                        this.editor.infoBox.show('Notice', '请先选择一个项目 (Select a project first)');
                        return;
                    }
                    if (target === 'kitti') {
                        this.editor.infoBox.show('Notice', 'KITTI export not implemented yet');
                        return;
                    }
                    // nuscenes export
                    try {
                        const body = { export_format: 'nuscenes_v1.0' };
                        const resp = await fetch(`/api/projects/${encodeURIComponent(projectName)}/export/nuscenes`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(body)
                        });
                        if (!resp.ok) {
                            const txt = await resp.text();
                            throw new Error(`HTTP ${resp.status}: ${txt}`);
                        }
                        const task = await resp.json();
                        this.editor.infoBox.show('Success', `NuScenes export task created: ${task.task_id}`);
                    } catch (err) {
                        console.error('Export failed', err);
                        this.editor.infoBox.show('Error', `Export failed: ${err.message}`);
                    }
                };
            });
        }
    }


    show(target) {
        this.wrapper.style.display = "inherit";

        this.menu.style.right = "0px";
        this.menu.style.top = target.offsetHeight + "px";

        globalKeyDownManager.register((event) => false, 'config');
    }

    hide() {
        globalKeyDownManager.deregister('config');
        this.wrapper.style.display = "none";
    }

    openCreateProjectDialog() {
        // Clone template
        const tpl = document.getElementById('create-project-dialog-template');
        if (!tpl) {
            alert('Create Project UI not found.');
            return;
        }
        const node = tpl.content.cloneNode(true);
        document.body.appendChild(node);

        const dialog = document.getElementById('create-project-dialog');
        // debug
        dialog.style.display = 'inherit';
        if (!dialog) return;

        const form = dialog.querySelector('#project-form');
        const btnCancel = dialog.querySelector('#cancel-btn');
        const btnExit = dialog.querySelector('#btn-exit');
        const btnTest = dialog.querySelector('#test-connection');
        const usePresigned = dialog.querySelector('#use-presigned-urls');
        const expirationGroup = dialog.querySelector('#expiration-group');

        const close = () => {
            dialog.remove();
        };

        btnCancel.onclick = close;
        btnExit.onclick = close;

        // Toggle expiration minutes visibility
        const syncExpirationVisibility = () => {
            expirationGroup.style.display = usePresigned.checked ? '' : 'none';
        };
        usePresigned.onchange = syncExpirationVisibility;
        syncExpirationVisibility();

        // Test Connection (optional): backend currently validates during creation
        btnTest.onclick = () => {
            alert('Connection will be validated during creation.');
        };

        form.onsubmit = async (e) => {
            e.preventDefault();

            const payload = {
                project_name: dialog.querySelector('#project-name').value.trim(),
                description: dialog.querySelector('#description').value.trim() || null,
                bucket_name: dialog.querySelector('#bucket-name').value.trim(),
                s3_endpoint: dialog.querySelector('#s3-endpoint').value.trim() || null,
                access_key_id: dialog.querySelector('#access-key').value.trim(),
                secret_access_key: dialog.querySelector('#secret-key').value,
                use_presigned_urls: usePresigned.checked,
                expiration_minutes: parseInt(dialog.querySelector('#expiration-minutes').value || '60', 10),
                region_name: 'us-east-1',
            };

            if (!payload.project_name || !payload.bucket_name || !payload.access_key_id || !payload.secret_access_key) {
                alert('Please fill in required fields.');
                return;
            }

            try {
                const resp = await fetch('/api/projects/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (!resp.ok) {
                    let msg;
                    try {
                        const err = await resp.json();
                        msg = err.detail || JSON.stringify(err);
                    } catch {
                        msg = await resp.text();
                    }
                    throw new Error(msg || `HTTP ${resp.status}`);
                }

                const created = await resp.json();
                // Refresh projects and select new one
                const list = await this.editor.data.readProjectList();
                this.editor.header.updateProjectSelectors(list);

                // Try to auto-load first frame of the new project
                try {
                    const meta = await this.editor.data.readSceneMetaData(payload.project_name);
                    const first = meta.frames && meta.frames[0];
                    if (first) {
                        this.editor.load_world(payload.project_name, first);
                    }
                } catch (e) {
                    console.warn('Project created but failed to load metadata:', e);
                }

                alert('Project created successfully.');
                close();
            } catch (err) {
                console.error('Create project failed:', err);
                alert(`Create failed: ${err.message}`);
            }
        };

        // Focus first input
        dialog.querySelector('#project-name')?.focus();
    }
}


export { ConfigUi };
