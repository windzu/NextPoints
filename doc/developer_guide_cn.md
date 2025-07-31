# 开发者指南

## 修改标注类别与属性

需要修改以下文件内容,分别是:

- 自定义标注类别 : `./public/js/obj_cfg.js` -> `ObjectCategory` -> `obj_type_map`,注意,必须保留`Unknown`类别
- 对标注结果的类别检查(可以不修改):`./tools/check_labels.py` -> `LabelChecker` -> `self.def_labels`
- `./tools/visualize-camera.py` -> `obj_color_map`

## 优化标注流程

在多帧标注中,点击`Auto`后,触发的流程如下

1. 触发`box_editor.js` 中的 `case 'cm-auto-annotate'`,从而触发 `autoAnnotateSelectedFrames`函数
2. 进而调用 `this.autoAnnotate`函数,在其中调用 `this.boxOp.interpolateAndAutoAdjustAsync`函数,即对应着`box_op.js`中的`interpolateAndAutoAdjustAsync`函数,该函数中实现了两个异步函数,具体如下
    - `autoAdjAsync` : 对标注结果进行自动调整
    - `onFinishOneBox` : 对标注结果进行更新
3. 进而调用 `ml.js`中的`interpolate_annotation`函数,实现对标注结果的插值

## 修改追踪器

点击`Auto`后触发的追踪器是`./public/js/ml.js` -> `interpolate_annotation: async function(anns, autoAdj, onFinishOneBox)`

## 读取 ego_pose
>
> 在原工程中实现了对`ego_pose`的读取,但是没有启用,也没有告知该如何使用,这里仔细记录一下

需要在data目录下放置ego_pose文件夹,其中每一帧数对应一个`filename.json`的pose文件,表示与该帧对应的点云数据在地图中的pose,格式如下:

```json
{
    "translation": [
        -40.84965292017664,
        -2332.0498781545975,
        12.604659656324236
    ],
    "rotation": [
        0.719291697305003,
        0.009853041229442371,
        0.0027628564760348254,
        -0.6946328083172516
    ]
}
```

加载`ego_pose`的代码在`./public/js/ego_pose.js` -> `load_ego_pose()`函数中,该函数通过发送GET请求,调用`./sence_reader.py`中的`read_ego_pose`函数,获取`ego_pose`数据

## 修改可视化中的范围圈

- 范围配置代码 : 修改的文件为 : `public/js/editor.js` -> `this.addRangeCircle= function()` , 目前里面默认有三个圈,半径分别是 30 50 100m,可以根据需要修改,具体见注释和代码,这个函数的代码其实是创建了一个`THREE.CircleGeometry`对象,并将其添加到了`scene`中
- 网页修改 : 在 `index.html` 中, 搜索`Hide circle ruler`即可找到对应的代码,修改即可
- 触发是否显示范围圈代码 : 在 `public/js/config_ui.js` 中,搜索 `#cfg-hide-circle-ruler-checkbox` 即可找到对应的代码,修改即可,其会调用 `editor.js` 中的 `this.showRangeCircle`函数

## 增加地面的渲染

- 绘制地面 : 在 `public/js/editor.js` 中,搜索 `addGround` 即可找到对应的代码,修改即可
- 在网页中显示是否选择显示地面的可选框 : 在 `index.html` 中,搜索 `Hide ground grid` 即可找到对应的代码,修改即可
- 触发是否显示地面的代码 : 在 `public/js/config_ui.js` 中,搜索 `#cfg-hide-ground-checkbox` 即可找到对应的代码,修改即可,其会调用 `editor.js` 中的 `this.showGround`函数

## 加入模型预标注

### 1. 修改前端部分

- index.html中加入模型预标注的按钮 : 在 index.html 中搜索 `run-model-button` 即可找到对应的代码
- header.js 中加入模型预标注按钮的触发函数 : 在 header.js 中搜索 `#run-model-button` 即可找到对应的代码 但是暂时无效... 还在排查

### 2. 加入推理后端
>
> 暂时先直接对所有数据进行推理+匹配,后续再进行交互的优化

- 使用 mmdet3d 进行推理 : 进入训练工程 , 运行相关脚本进行推理,将结果保存为 sus 格式
- 再使用离线追踪算法进行关联匹配,找到最优匹配及每个instance的最优size,将其应用至该instance的标注结果中

## 快捷键修改

- 增加 `c`对选中框旋转90度,搜索`z_rotate_pi_2`即可找到对应的代码
