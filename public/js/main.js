import { Config } from "./config.js";
import { Data } from './data.js';
import { Editor } from "./editor.js";


let pointsGlobalConfig = new Config();
window.pointsGlobalConfig = pointsGlobalConfig;


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
  maindiv.appendChild(main_ui); // input parameter is changed after `append`

  let editorCfg = pointsGlobalConfig;

  let dataCfg = pointsGlobalConfig;

  let data = new Data(dataCfg);

  let url_string = window.location.href
  let url = new URL(url_string);
  //language
  let path = url.searchParams.get("path");
  // await data.init(path);
  await data.init();

  let editor = new Editor(maindiv.lastElementChild, maindiv, editorCfg, data, "main-editor")
  window.editor = editor;
  editor.run();
  return editor;
}

async function start() {


  let mainEditor = await createMainEditor();


  let url_string = window.location.href
  let url = new URL(url_string);
  let project_id = url.searchParams.get("project_id");
  let frame_id = url.searchParams.get("frame_id");

  if (project_id && frame_id) {
    mainEditor.load_world(project_id, frame_id);
  }
}




start();
