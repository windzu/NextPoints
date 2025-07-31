# Install from source

## Install

0. clone the project

   ```bash
   mkdir -p ~/App && cd ~/App
   git clone http://192.168.102.13/perception/autolabel/sustechpoints.git
   cd sustechpoints
   ```

1. Create env and install packages

     ```bash
     conda create -n sus python=3.8 -y
     conda activate sus
     pip3 install -r requirement.txt
     ```

### Start

Run the following command in shell, then go to <http://127.0.0.1:8081>

```bash
python main.py
```

## Object type configuration

Default object configuration is in [obj_cfg.js](src/public/js/../../../public/js/obj_cfg.js)

Adjust the contents to customize.

## Data preparation

```bash
   +- data
       +- scene1
          +- lidar
               +- 0000.pcd
               +- 0001.pcd
          +- camera
               +- front
                    +- 0000.jpg
                    +- 0001.jpg
               +- left
                    +- ...
          +- calib
               +- camera
                    +- front.json
                    +- left.json
               +- radar
                    +- front_points.json
                    +- front_tracks.json
          +- label
               +- 0000.json
               +- 0001.json
       +- scene2

```

- **label** is the directory to save the annotation result.
- **calib** is the calibration matrix from point cloud to image. it's **optional**, but if provided, the box is projected on the image so as to assist the annotation.
- check examples in `./data/example`
