# Develop

## Customizing categories
>
> 自定义类别

需要修改两个文件内容,两者内容一一对应,分别是:

- `./public/js/obj_cfg.js` -> `ObjectCategory` -> `obj_type_map`
- `./tools/check_labels.py` -> `LabelChecker` -> `self.def_labels`

## 绝对路径访问

example:

```markdown
http://192.168.200.100:8081/?path=/home/dataset/wind_data/lidar_3d/raw/1514-0_YC800B01-N1-0001/sus
```

原本可以通过 `http://192.168.200.100:8081` 访问,但如果想要访问指定的路径,则需要在后面加上 `?path=xxx` 的参数,其中 `xxx` 为绝对路径.

Note: 这种对绝对路径的访问的实现方式也是通过创建软链接方式实现的,所以需要注意软链接的创建.

## scene_name 访问

例如访问 <http://192.168.200.100:10081/？scene_name=1514-0_YC800B01-N1-0001>
可以直接访问指定的场景
