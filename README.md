# SUSTechPOINTS: Point Cloud 3D Bounding Box Annotation Tool For Autonomous Driving

### Main UI

![screenshot](./doc/imgs/main-ui.png)

### Automatic yaw angle (z-axis) prediction

![auto-rotate](./doc/imgs/auto-rotate.gif)

### batch-mode box editing

semi-auto-annotation

![batch-mode](./doc/imgs/auto-anno-car.gif)

## Features

- 9 DoF box editing
- Object type/ID/attributes editing
- Interactive/auto box fitting
- Batch-mode editing
- perspective/projective view editing
- Multiple camera images, with auto-camera-switching
- Binary/pcd files for point cloud data
- Jpg/png image files
- Objects/boxes/points coloring
- Focus mode to hide background to check details easily
- Stream play/stop
- Object ID generation

## Get started

[From Docker](./doc/install_from_docker.md)

[From Source(recommend)](./doc/install_from_source.md)

[uwsgi](./doc/deploy_server.md)

## Operations

[Operations](./doc/operations.md)

[Shortcuts(中文)](./doc/shortcuts_cn.md)

## Cite

If you find this work useful in your research, please consider cite:

```bash
@INPROCEEDINGS{9304562,
  author={Li, E and Wang, Shuaijun and Li, Chengyang and Li, Dachuan and Wu, Xiangbin and Hao, Qi},
  booktitle={2020 IEEE Intelligent Vehicles Symposium (IV)}, 
  title={SUSTech POINTS: A Portable 3D Point Cloud Interactive Annotation Platform System}, 
  year={2020},
  volume={},
  number={},
  pages={1108-1115},
  doi={10.1109/IV47402.2020.9304562}}
  
```
