import json
import os

import cherrypy
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("./"))

import os

import legacy.scene_reader as scene_reader
from algos import pre_annotate
from tools import check_labels as check
from tools.model_inference import call_remote_inference

# 推理服务器配置
INFERENCE_SERVER_URL = "http://192.168.200.100:8000"  # 替换为实际的推理服务器地址
INFERENCE_ENDPOINT = "/predict"  # 推理服务的端点


class Root(object):
    @cherrypy.expose
    def index(self, scene="", frame="", path=""):
        tmpl = env.get_template("index.html")
        return tmpl.render()

    @cherrypy.expose
    def icon(self):
        tmpl = env.get_template("test_icon.html")
        return tmpl.render()

    @cherrypy.expose
    def ml(self):
        tmpl = env.get_template("test_ml.html")
        return tmpl.render()

    @cherrypy.expose
    def reg(self):
        tmpl = env.get_template("registration_demo.html")
        return tmpl.render()

    @cherrypy.expose
    def view(self, file):
        tmpl = env.get_template("view.html")
        return tmpl.render()

    @cherrypy.expose
    def saveworldlist(self):
        rawbody = cherrypy.request.body.readline().decode("UTF-8")
        data = json.loads(rawbody)

        for d in data:
            scene = d["scene"]
            frame = d["frame"]
            ann = d["annotation"]
            with open("./data/" + scene + "/label/" + frame + ".json", "w") as f:
                json.dump(ann, f, indent=2, sort_keys=True)

        return "ok"

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def cropscene(self):
        rawbody = cherrypy.request.body.readline().decode("UTF-8")
        data = json.loads(rawbody)

        rawdata = data["rawSceneId"]

        timestamp = rawdata.split("_")[0]

        print("generate scene")
        log_file = "temp/crop-scene-" + timestamp + ".log"

        cmd = (
            "python ./tools/dataset_preprocess/crop_scene.py generate "
            + rawdata[0:10]
            + "/"
            + timestamp
            + "_preprocessed/dataset_2hz "
            + "- "
            + data["startTime"]
            + " "
            + data["seconds"]
            + " "
            + '"'
            + data["desc"]
            + '"'
            + "> "
            + log_file
            + " 2>&1"
        )
        print(cmd)

        code = os.system(cmd)

        with open(log_file) as f:
            log = list(map(lambda s: s.strip(), f.readlines()))

        os.system("rm " + log_file)

        return {"code": code, "log": log}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def checkscene(self, scene):
        ck = check.LabelChecker(os.path.join("./data", scene))
        ck.check()
        print(ck.messages)
        return ck.messages


    @cherrypy.expose
    @cherrypy.tools.json_out()
    def auto_annotate(self, scene, frame):
        print("auto annotate ", scene, frame)
        return pre_annotate.annotate_file("./data/{}/lidar/{}.pcd".format(scene, frame))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def load_annotation(self, scene, frame):
        return scene_reader.read_annotations(scene, frame)

    # 读取每一帧的 ego pose ,文件在 scene/ego_pose/xxxx.json
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def load_ego_pose(self, scene, frame):
        return scene_reader.read_ego_pose(scene, frame)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def loadworldlist(self):
        rawbody = cherrypy.request.body.readline().decode("UTF-8")
        worldlist = json.loads(rawbody)

        anns = list(
            map(
                lambda w: {
                    "scene": w["scene"],
                    "frame": w["frame"],
                    "annotation": scene_reader.read_annotations(w["scene"], w["frame"]),
                },
                worldlist,
            )
        )

        return anns

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def datameta(self):
        return scene_reader.get_all_scenes()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def scenemeta(self, scene):
        # debug
        print("scenemeta", scene)
        return scene_reader.get_one_scene(scene)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_all_scene_desc(self, path=None):
        if path:
            # debug
            print("get_all_scene_desc with path")
            print(path)
            return scene_reader.get_all_scene_desc(path)
        else:
            # debug
            print("get_all_scene_desc with default path")
            return scene_reader.get_all_scene_desc()

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def run_model(self):
        """运行模型进行预标注 - 通过Web请求调用远程推理服务"""
        try:
            input_data = cherrypy.request.json
            scene_name = input_data.get("scene")

            print(f"Running model inference for scene: {scene_name}")

            # 调用远程推理服务
            inference_result = call_remote_inference(
                scene_name,
                INFERENCE_SERVER_URL,
                INFERENCE_ENDPOINT,
            )

            return inference_result

        except Exception as e:
            print(f"Error in run_model: {str(e)}")
            return {"success": False, "error": str(e)}


if __name__ == "__main__":
    cherrypy.quickstart(Root(), "/", config="server.conf")
else:
    application = cherrypy.Application(Root(), "/", config="server.conf")
