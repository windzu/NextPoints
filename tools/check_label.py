import json
import os
import sys
import numpy as np
from typing import List, Optional, Dict, Union

from app.models.annotation_model import WorldAnnotation, AnnotationItem, PSR


def get_labels():
    nuscenes_labels_dict = {
        "vehicle": {
            "cycle": ["bicycle", "motorcycle", "tricycle", "cycle_group", "cycle"],
            "car": ["car"],
            "truck": ["van", "pickup", "cargo", "trailer", "truck"],
            "bus": ["micro_bus", "mini_bus", "bus"],
            "construction": ["construction"],
        },
        "human": {"pedestrian": ["pedestrian"]},
        "animal": {"animal": ["animal"]},
        "static_object": {
            "barrier": ["barrier"],
            "trafficcone": ["trafficcone"],
            "stone": ["stone"],
            "chair": ["chair"],
        },
    }

    sus_labels_dict = {
        "vehicle": {
            "cycle": [
                "Bicycle",
                "Scooter",
                "Motorcycle",
                "Tricycle",
                "BicycleGroup",
                "Rider",
            ],
            "car": ["Car"],
            "truck": ["Van", "Truck"],
            "bus": ["Bus"],
            "construction": ["ConstructionCart"],
        },
        "human": {"pedestrian": ["Pedestrian"]},
        "animal": {"animal": ["Animal"]},
        "static_object": {
            "barrier": ["TrafficBarrier"],
            "trafficcone": ["Cone"],
            "trash_can": ["TrashCan"],
        },
    }

    labels_dict = sus_labels_dict

    labels_list = []
    for k in labels_dict:
        for kk in labels_dict[k]:
            labels_list.extend(labels_dict[k][kk])



    return labels_list


class LabelChecker:
    """check scene labels

    check items:
    - object type : not in the predefined list
    - object id : absent
    - object size : too small or too large
    - object direction : too large rotation delta
    - object type consistency : different object types in the same object id
    - duplicate : duplicate object id in the same frame


    Args:
        path (str): scene path
    """

    def __init__(self, annotations: List[WorldAnnotation]):
        self.annotations = annotations

        self.build_labels()
        self.def_labels = get_labels()
        self.messages = []

    def clear_messages(self):
        self.messages = []

    def show_messages(self):
        for m in self.messages:
            print(m["frame_id"], m["obj_id"], m["desc"])

    def push_message(self, frame, obj_id, desc):
        self.messages.append({"frame_id": frame, "obj_id": obj_id, "desc": desc})

    def build_labels(self):
        self.frame_ids = []
        self.labels = {}
        self.obj_ids = {}

        for annotation in self.annotations:
            frame_id = annotation.frame
            if not frame_id:
                continue
            if frame_id not in self.frame_ids:
                self.frame_ids.append(frame_id)
            if not self.labels.get(frame_id):
                self.labels[frame_id] = []

            for item in annotation.annotation:
                obj_id = item.obj_id
                if not self.obj_ids.get(obj_id):
                    self.obj_ids[obj_id] = []
                self.obj_ids[obj_id].append([frame_id, item.model_dump()])

                self.labels[frame_id].append(item.model_dump())

    # templates
    def check_one_label(self, func):
        for f in self.labels:
            for o in self.labels[f]:
                func(f, o)

    def check_one_frame(self, func):
        for f in self.labels:
            func(f, self.labels[f])

    def check_one_obj(self, func):
        for id in self.obj_ids:
            func(id, self.obj_ids[id])

    def check_obj_type(self, frame_id, o):
        if not o["obj_type"] in self.def_labels:
            self.push_message(
                frame_id,
                o["obj_id"],
                "object type {} not recognizable".format(o["obj_type"]),
            )

    def check_obj_id(self, frame_id, o):
        if not o["obj_id"]:
            self.push_message(frame_id, "", "object {} id absent".format(o["obj_type"]))

    def check_frame_duplicate_id(self, frame_id, objs):
        obj_id_cnt = {}
        for o in objs:
            if obj_id_cnt.get(o["obj_id"]):
                obj_id_cnt[o["obj_id"]] += 1
            else:
                obj_id_cnt[o["obj_id"]] = 1

        for id in obj_id_cnt:
            if obj_id_cnt[id] > 1:
                self.push_message(frame_id, id, "duplicate object id")

    def check_obj_size(self, obj_id, label_list):
        if label_list[0][1]["obj_type"] == "Pedestrian":
            return

        mean = {}
        for axis in ["x", "y", "z"]:
            vs = list(map(lambda l: float(l[1]["psr"]["scale"][axis]), label_list))
            mean[axis] = np.array(vs).mean()

        for l in label_list:
            frame_id = l[0]
            label = l[1]

            for axis in ["x", "y", "z"]:
                ratio = label["psr"]["scale"][axis] / mean[axis]
                if ratio < 0.95:
                    self.push_message(
                        frame_id,
                        obj_id,
                        "dimension {} too small: {}, mean {}".format(
                            axis, label["psr"]["scale"][axis], mean[axis]
                        ),
                    )
                    # return
                elif ratio > 1.05:
                    self.push_message(
                        frame_id,
                        obj_id,
                        "dimension {} too large: {}, mean {}".format(
                            axis, label["psr"]["scale"][axis], mean[axis]
                        ),
                    )
                    # return

    def check_obj_direction(self, obj_id, label_list):

        for i in range(1, len(label_list)):
            l = label_list[i]
            pl = label_list[i - 1]
            frame_id = l[0]
            label = l[1]
            plabel = pl[1]

            for axis in ["x", "y", "z"]:
                rotation_delta = (
                    label["psr"]["rotation"][axis] - plabel["psr"]["rotation"][axis]
                )
                pi = 3.141592543
                if rotation_delta > pi:
                    rotation_delta = 2 * pi - rotation_delta
                elif rotation_delta < -pi:
                    rotation_delta = 2 * pi + rotation_delta

                if rotation_delta > 30 / 180 * pi or rotation_delta < -30 / 180 * pi:
                    self.push_message(
                        frame_id, obj_id, "rotation {} delta too large".format(axis)
                    )
                    # return

    def check_obj_type_consistency(self, obj_id, label_list):
        for i in range(1, len(label_list)):

            l = label_list[i]
            pl = label_list[i - 1]
            frame_id = l[0]
            label = l[1]
            plabel = pl[1]

            if label["obj_type"] != plabel["obj_type"]:
                self.push_message(
                    frame_id,
                    obj_id,
                    "different object types: {}, previous {}".format(
                        label["obj_type"], plabel["obj_type"]
                    ),
                )
                # return
        pass

    def check(self):
        self.clear_messages()

        self.check_one_label(lambda f, o: self.check_obj_type(f, o))
        self.check_one_label(lambda f, o: self.check_obj_id(f, o))

        self.check_one_frame(lambda f, o: self.check_frame_duplicate_id(f, o))

        self.check_one_obj(lambda id, o: self.check_obj_size(id, o))
        self.check_one_obj(lambda id, o: self.check_obj_direction(id, o))
        self.check_one_obj(lambda id, o: self.check_obj_type_consistency(id, o))



