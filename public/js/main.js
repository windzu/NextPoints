import { Config } from "./config.js";
import { Data } from './data.js';
import { Editor } from "./editor.js";
import { ProjectManager } from './project_manager.js'; // 新增导入

let pointsGlobalConfig = new Config();
window.pointsGlobalConfig = pointsGlobalConfig;

// 新增项目管理器
let projectManager;
window.projectManager = projectManager;

pointsGlobalConfig.load();

document.documentElement.className = "theme-" + pointsGlobalConfig.theme;

document.body.addEventListener('keydown', event => {
  if (event.ctrlKey && 'asdv'.indexOf(event.key) !== -1) {
    event.preventDefault()
  }
});

async function createMainEditor() {
  let template = document.querySelector('#editor-template');
  let maindiv = document.querySelector("#main-editor");
  let main_ui = template.content.cloneNode(true);
  maindiv.appendChild(main_ui);

  let editorCfg = pointsGlobalConfig;
  let dataCfg = pointsGlobalConfig;
  let data = new Data(dataCfg);

  let url_string = window.location.href
  let url = new URL(url_string);
  let path = url.searchParams.get("path");
  await data.init(path);

  let editor = new Editor(maindiv.lastElementChild, maindiv, editorCfg, data, "main-editor")
  window.editor = editor;

  // 初始化项目管理器
  projectManager = new ProjectManager();
  window.projectManager = projectManager;
  await projectManager.init();

  // 监听项目切换事件
  document.addEventListener('projectChanged', async function (event) {
    const project = event.detail.project;
    if (project) {
      console.log('Project changed to:', project.name);
      await loadProjectData(project, editor, data);
    } else {
      console.log('No project selected');
      clearProjectData(editor);
    }
  });

  editor.run();
  return editor;
}

async function loadProjectData(project, editor, data) {
  try {
    console.log('Loading project data for:', project.name);

    // 获取项目的帧数据
    const frames = await projectManager.getProjectFrames(project.id);

    // 更新帧选择器
    updateFrameSelector(frames, editor, data, project);

    // 如果有帧数据，默认选择第一帧
    if (frames.length > 0) {
      await loadFrame(frames[0], editor, data, project);
    }

  } catch (error) {
    console.error('Failed to load project data:', error);
  }
}

function updateFrameSelector(frames, editor, data, project) {
  const frameSelector = document.getElementById('frame-selector');
  if (!frameSelector) return;

  // 清空现有选项
  frameSelector.innerHTML = '<option value="">--frame--</option>';

  // 添加帧选项
  frames.forEach((frame, index) => {
    const option = document.createElement('option');
    option.value = frame.id;
    option.textContent = `Frame ${index + 1} (${new Date(frame.timestamp_ns / 1000000).toLocaleTimeString()})`;
    option.dataset.frameData = JSON.stringify(frame);
    frameSelector.appendChild(option);
  });

  // 移除之前的事件监听器，添加新的
  frameSelector.replaceWith(frameSelector.cloneNode(true));
  const newFrameSelector = document.getElementById('frame-selector');
  newFrameSelector.addEventListener('change', async function (e) {
    if (e.target.value) {
      const frameData = JSON.parse(e.target.selectedOptions[0].dataset.frameData);
      await loadFrame(frameData, editor, data, project);
    }
  });
}

async function loadFrame(frameData, editor, data, project) {
  try {
    console.log('Loading frame:', frameData);

    // 构建场景和帧的路径格式，兼容现有的Data类
    const sceneName = project.name;
    const frameIndex = frameData.id;

    // 设置S3配置到Data类
    if (data.setS3Config) {
      data.setS3Config({
        bucket_name: project.bucket_name,
        access_key_id: project.access_key_id,
        secret_access_key: project.secret_access_key,
        s3_endpoint: project.s3_endpoint,
        region_name: project.region_name,
        use_presigned_urls: project.use_presigned_urls
      });
    }

    // 如果有预签名URL，直接使用
    if (frameData.pointcloud_url) {
      // 直接加载点云URL
      await loadPointCloudFromUrl(frameData.pointcloud_url, editor);
    } else {
      // 使用现有的load_world方法，但需要适配S3
      await editor.load_world(sceneName, frameIndex);
    }

    // 加载图像数据
    if (frameData.image_urls) {
      loadImages(frameData.image_urls, editor);
    }

  } catch (error) {
    console.error('Failed to load frame:', error);
  }
}

async function loadPointCloudFromUrl(url, editor) {
  try {
    // 这里需要根据您现有的点云加载逻辑来实现
    // 可能需要修改Editor类来支持从URL加载点云
    console.log('Loading pointcloud from URL:', url);

    // 示例实现 - 您需要根据实际的点云加载逻辑调整
    if (editor.loadPointCloudFromUrl) {
      await editor.loadPointCloudFromUrl(url);
    } else {
      console.warn('Editor does not support loading pointcloud from URL yet');
    }

  } catch (error) {
    console.error('Failed to load pointcloud from URL:', error);
  }
}

function loadImages(imageUrls, editor) {
  try {
    console.log('Loading images:', imageUrls);

    // 更新相机选择器
    const cameraList = document.getElementById('camera-list');
    if (cameraList) {
      cameraList.innerHTML = '';

      Object.keys(imageUrls).forEach(cameraId => {
        const cameraBtn = document.createElement('button');
        cameraBtn.textContent = cameraId;
        cameraBtn.addEventListener('click', () => {
          displayImage(imageUrls[cameraId], cameraId);
        });
        cameraList.appendChild(cameraBtn);
      });
    }

  } catch (error) {
    console.error('Failed to load images:', error);
  }
}

function displayImage(imageUrl, cameraId) {
  // 根据您现有的图像显示逻辑实现
  console.log(`Displaying image for camera ${cameraId}:`, imageUrl);
}

function clearProjectData(editor) {
  // 清空帧选择器
  const frameSelector = document.getElementById('frame-selector');
  if (frameSelector) {
    frameSelector.innerHTML = '<option value="">--frame--</option>';
  }

  // 清空相机列表
  const cameraList = document.getElementById('camera-list');
  if (cameraList) {
    cameraList.innerHTML = '';
  }

  // 清空编辑器内容
  if (editor && editor.clear) {
    editor.clear();
  }
}

async function start() {
  let mainEditor = await createMainEditor();

  let url_string = window.location.href
  let url = new URL(url_string);
  let scene = url.searchParams.get("scene");
  let frame = url.searchParams.get("frame");

  // 如果URL中有scene和frame参数，优先使用（兼容现有功能）
  if (scene && frame) {
    mainEditor.load_world(scene, frame);
  }
  // 否则等待用户通过项目选择器选择项目
}

start();