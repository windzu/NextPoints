

import { logger } from "./log.js";
// const hermite = require('hermite-spline');
const annMath = {

    sub: function (a, b) {    //pos, rot, scale

        let c = [];
        for (let i in a) {
            c[i] = a[i] - b[i];
        }

        return this.norm(c);
    },

    div: function (a, d) {  // d is scalar
        let c = [];
        for (let i in a) {
            c[i] = a[i] / d;
        }

        return c;
    },

    add: function (a, b) {
        let c = [];
        for (let i in a) {
            c[i] = a[i] + b[i];
        }


        return this.norm(c);
    },

    mul: function (a, d)  // d is scalar
    {
        let c = [];
        for (let i in a) {
            c[i] = a[i] * d;
        }

        return this.norm(c);
    },

    norm: function (c) {
        for (let i = 3; i < 6; i++) {
            if (c[i] > Math.PI) {
                c[i] -= Math.PI * 2;
            }
            else if (c[i] < - Math.PI) {
                c[i] += Math.PI * 2;
            }
        }

        return c;
    },

    normAngle: function (a) {
        if (a > Math.PI) {
            return a - Math.PI * 2;
        }
        else if (a < - Math.PI) {
            return a + Math.PI * 2;
        }

        return a;
    },

    eleMul: function (a, b) //element-wise multiplication
    {
        let c = [];
        for (let i in a) {
            c[i] = a[i] * b[i];
        }


        return c;
    }

};



var ml = {
    backend: tf.getBackend(),

    calibrate_axes: function (points) {
        console.log("backend of tensorflow:", tf.getBackend());
        console.log("number of points:", points.count);

        var center_points = {};
        for (var i = 0; i < points.count; i++) {
            if (points.array[i * 3] < 10 && points.array[i * 3] > -10 &&
                points.array[i * 3 + 1] < 10 && points.array[i * 3 + 1] > -10)  // x,y in [-10,10]
            {
                var key = (10 + Math.round(points.array[i * 3])) * 100 + (Math.round(points.array[i * 3 + 1]) + 10);
                if (center_points[key]) {

                    // save only  minimal index
                    if (points.array[i * 3 + 2] < points.array[center_points[key] * 3 + 2]) {
                        center_points[key] = i;
                    }

                } else {
                    center_points[key] = i;
                }
            }
        }

        var center_point_indices = [];
        for (var i in center_points) {
            center_point_indices.push(center_points[i]);
        }

        //console.log(center_point_indices);
        var points_2d = center_point_indices.map(i => [points.array[i * 3], points.array[i * 3 + 1], points.array[i * 3 + 2]]);
        var points_array = points_2d.flatMap(x => x);


        var sum = points_2d.reduce(function (s, x) {
            return [s[0] + x[0],
            s[1] + x[1],
            s[2] + x[2]];
        }, [0, 0, 0]);
        var count = points_2d.length;
        var mean = [sum[0] / count, sum[1] / count, sum[2] / count];

        var data_centered = points_2d.map(function (x) {
            return [
                x[0] - mean[0],
                x[1] - mean[1],
                x[2] - mean[2],
            ];
        })

        var normal_v = this.train(data_centered);



        data.world.add_line(mean, [-normal_v[0] * 10, -normal_v[1] * 10, normal_v[2] * 10]);
        data.world.lidar.reset_points(points_array);
        /*

        var trans_matrix = transpose(euler_angle_to_rotate_matrix_3by3({x:Math.atan2(normal_v[1], -1), y: 0, z: 0}));

        var transfromed_point_array = matmul(trans_matrix, points_array, 3);

        data.world.lidar.reset_points(transfromed_point_array);
        
        //data.world.lidar.set_spec_points_color(center_point_indices, {x:1,y:0,z:0});
        //data.world.lidar.update_points_color();
        */



        return center_point_indices;
    },

    train: function (data_centered)  // data is ?*3 array.
    {



        var XY = data_centered.map(function (x) { return x.slice(0, 2); });
        var Z = data_centered.map(function (x) { return x[2]; });


        var x = tf.tensor2d(XY);
        var para = tf.variable(tf.tensor2d([[Math.random(), Math.random()]]));

        const learningRate = 0.00001;
        const optimizer = tf.train.sgd(learningRate);
        para.print();
        for (var i = 0; i < 20; i++) {
            optimizer.minimize(function () {
                var dists = tf.matMul(para, x.transpose());
                var sqrdiff = tf.squaredDifference(dists, Z);
                var loss = tf.div(tf.sum(sqrdiff), sqrdiff.shape[0]);
                loss.print();
                return loss;
            });

            console.log(i);
            para.print();
        }

        var pv = para.dataSync();
        console.log("train result: ", pv);
        return [pv[0], pv[1], 1];
    }
    ,


    // data is N*2 matrix, 
    l_shape_fit: function (data) {

        // cos, sin
        // -sin, cos
        var A = tf.tensor2d(data);
        //A = tf.expandDims(A, [0]);

        var theta = [];
        var min = 0;
        var min_index = 0;
        for (var i = 0; i <= 90; i += 1) {
            var obj = cal_objetive(A, i);

            if (min == 0 || min > obj) {
                min_index = i;
                min = obj;
            }
        }

        console.log(min_index, min);
        return min;

        //end of func

        function cal_objetive(A, theta) {
            let r = theta * Math.PI / 180;
            let bases = tf.tensor2d([[Math.cos(r), -Math.sin(r)],
            [Math.sin(r), Math.cos(r)]]);

            let proj = tf.matMul(A, bases);  // n * 2
            let max = tf.max(proj, 0); // 1*2
            let min = tf.min(proj, 0); // 1*2
            var dist_to_min = tf.sum(tf.square(tf.sub(proj, min)), 0);
            var dist_to_max = tf.sum(tf.square(tf.sub(max, proj)), 0);

            // axis 0
            var dist0, dist1; // dist to axis 0, axis 1
            if (dist_to_min.gather(0).dataSync() < dist_to_max.gather(0).dataSync()) {
                dist0 = tf.sub(proj.gather([0], 1), min.gather(0));
            } else {
                dist0 = tf.sub(max.gather(0), proj.gather([0], 1));
            }

            if (dist_to_min.gather(1).dataSync() < dist_to_max.gather(1).dataSync()) {
                dist1 = tf.sub(proj.gather([1], 1), min.gather(1));
            } else {
                dist1 = tf.sub(max.gather(1), proj.gather([1], 1));
            }

            // concat dist0, dist1
            var min_dist = tf.concat([dist0, dist1], 1).min(1);
            return min_dist.sum().dataSync()[0];
        }

    }
    ,

    // 通过发送请求到服务器，后端调用相关函数(predict_rotation)预测点云的旋转角度
    predict_rotation: function (data) {
        const req = new Request("/predict_rotation");
        let init = {
            method: 'POST',
            body: JSON.stringify({ "points": data })
        };
        // we defined the xhr
        console.log("start predict rotatoin.", data.length, 'points')

        return fetch(req, init)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                } else {
                    console.log("predict rotatoin response received.")
                    return response.json();
                }
            })
            .catch(reject => {
                console.log("error predicting yaw angle!");
            });

    },

    // autoadj is async
    // input anns is a list of annotation, each annotation is a list of 9 elements (x,y,z,rx,ry,rz,sx,sy,sz)
    interpolate_annotation: async function (anns, autoAdj, onFinishOneBox) {
        // step 0: 静态目标判断,如果目标静止,则不进行插值操作,而是将所有空帧使用静止的目标位置
        // TODO(wind) : 通过完美帧来作为所有静态目标的参考帧
        let staticMovingThreshold = 0.1;
        let posRMSE = 0;
        let posMean = [0, 0];
        let notNullAnns = [];
        // get all not null anns
        for (let i = 0; i < anns.length; i++) {
            if (anns[i]) {
                notNullAnns.push(anns[i]);
            }
        }
        // get pos mean
        let posSum = [0, 0];
        for (let i = 0; i < notNullAnns.length; i++) {
            posSum[0] += notNullAnns[i][0];
            posSum[1] += notNullAnns[i][1];
        }
        posMean[0] = posSum[0] / notNullAnns.length;
        posMean[1] = posSum[1] / notNullAnns.length;

        // get pos RMSE
        posRMSE = 0;
        for (let i = 0; i < notNullAnns.length; i++) {
            posRMSE += Math.pow(notNullAnns[i][0] - posMean[0], 2) + Math.pow(notNullAnns[i][1] - posMean[1], 2);
        }
        posRMSE = Math.sqrt(posRMSE / notNullAnns.length);
        // if posRMSE < staticMovingThreshold, then the target is static
        if (posRMSE < staticMovingThreshold) {
            console.log(" posRMSE is ", posRMSE, " < ", staticMovingThreshold, " static target found,will use the first frame anno.");
            for (let i = 0; i < anns.length - 1; i++) {
                if (!anns[i]) {
                    anns[i] = notNullAnns[0];
                    if (onFinishOneBox) onFinishOneBox(i);
                }
            }
            return anns;
        } else {
            console.log(" posRMSE is ", posRMSE, " > ", staticMovingThreshold, " moving target found,will interpolate the frames.");
        }

        // 如果不是静态目标,则进行下面的操作
        // step 1: 找到所有的不连续且不为空的annotation,然后对两两annotation之间的空帧进行插值操作
        let pair_index = [];
        for (let i = 0; i < anns.length - 1; i++) {
            if (anns[i] && !anns[i + 1]) {
                let pair = [0, 0];
                for (let j = i + 2; j < anns.length; j++) {
                    if (anns[i] && anns[j]) {
                        pair[0] = i;
                        pair[1] = j;
                        pair_index.push(pair);
                        break;
                    }
                }
            }
        }
        console.log("pair_index: ", pair_index);
        // 对两两annotation之间的空帧进行插值操作
        for (let i = 0; i < pair_index.length; i++) {
            let start = pair_index[i][0];
            let end = pair_index[i][1];
            let interpolate_step = annMath.div(annMath.sub(anns[end], anns[start]), (end - start));
            for (let inserti = start + 1; inserti < end; inserti++) {
                let tempAnn = annMath.add(anns[inserti - 1], interpolate_step);
                // 如果提供了自动调整函数，则调用对插值后的结果进行调整
                if (autoAdj) {
                    try {
                        let adjustedAnn = await autoAdj(inserti, tempAnn);

                        // position 修正
                        // - z 修正
                        adjustedAnn[2] = tempAnn[2];

                        // yaw 角修正 防止跳变
                        let adjustedYaw = annMath.normAngle(adjustedAnn[5] - tempAnn[5]);
                        if (Math.abs(adjustedYaw) > Math.PI / 2) {
                            console.log("adjust angle by Math.PI.");
                            adjustedAnn[5] = annMath.normAngle(adjustedAnn[5] + Math.PI);
                        }

                        // 不允许旋转roll和pitch,强制设置为0
                        adjustedAnn[3] = 0; // roll
                        adjustedAnn[4] = 0; // pitch
                        // if (!pointsGlobalConfig.enableAutoRotateXY) {
                        //     adjustedAnn[3] = 0; // roll
                        //     adjustedAnn[4] = 0; // pitch
                        // }
                        tempAnn = adjustedAnn;
                    }
                    catch (e) {
                        console.log(e);
                    }
                }
                anns[inserti] = tempAnn;
                if (onFinishOneBox) onFinishOneBox(inserti);
            }
        }

        // step 2: 通过MaFilter,使用连续annotation进行构造及更新,对第一个连续的空白帧进行预测
        // 1. 找到第一个不为空的annotation,初始化滤波器
        // 2. 如果在第一个不为空的annotation之后紧接着遇到一段连续的不为空的annotation,则使用这些连续的annotation更新滤波器
        // 3. 对于第一段连续的为空的annotation,使用滤波器进行预测
        let i = 0;
        // 找到第一个不为空的annotation
        while (i < anns.length && !anns[i]) i++;

        if (i < anns.length) {
            // 用第一个不为空的annotation初始化滤波器 MaFilter
            let filter = new MaFilter(anns[i]);
            i++;

            // 如果在第一个不为空的annotation之后紧接着遇到一段连续的annotation,
            // 则使用这些连续的annotation更新滤波器
            while (i < anns.length && anns[i]) {
                filter.update(anns[i]);
                i++;
            }

            // 对于第一段连续的为空的annotation,使用滤波器进行预测
            // 如果提供了自动调整函数，则对预测结果进行调整
            while (i < anns.length && !anns[i]) {
                let tempAnn = filter.predict();

                if (autoAdj) {
                    try {
                        let adjustedAnn = await autoAdj(i, tempAnn);

                        // position 修正
                        // - z 修正
                        adjustedAnn[2] = tempAnn[2];

                        let adjustedYaw = annMath.normAngle(adjustedAnn[5] - tempAnn[5]);

                        if (Math.abs(adjustedYaw) > Math.PI / 2) {
                            console.log("adjust angle by Math.PI.");
                            adjustedAnn[5] = annMath.normAngle(adjustedAnn[5] + Math.PI);
                        }

                        tempAnn = adjustedAnn;

                        filter.update(tempAnn);
                    } catch (error) {
                        console.log(error);
                        filter.nextStep(tempAnn);
                    }

                }
                else {
                    filter.nextStep(tempAnn);
                }

                anns[i] = tempAnn;
                // we should update 
                if (onFinishOneBox)
                    onFinishOneBox(i);

                i++;
            }
        }


        // step 3: 与step 2类似,但是是反向预测空白帧
        // Note : 在反向过程中使用了来自step 2的预测结果作为了初始值和更新值,这可能会导致一些问题
        i = anns.length - 1;
        while (i >= 0 && !anns[i])
            i--;

        if (i >= 0) {
            let filter = new MaFilter(anns[i]);
            i--;

            while (i >= 0 && anns[i]) {
                filter.update(anns[i]);
                i--;
            }

            while (i >= 0 && !anns[i]) {
                let tempAnn = filter.predict();
                if (autoAdj) {
                    let adjustedAnn = await autoAdj(i, tempAnn).catch(e => {
                        logger.log(e);
                        return tempAnn;
                    });

                    // position 修正
                    // - z 修正
                    adjustedAnn[2] = tempAnn[2];

                    let adjustedYaw = annMath.normAngle(adjustedAnn[5] - tempAnn[5]);

                    if (Math.abs(adjustedYaw) > Math.PI / 2) {
                        console.log("adjust angle by Math.PI.");
                        adjustedAnn[5] = annMath.normAngle(adjustedAnn[5] + Math.PI);
                    }

                    tempAnn = adjustedAnn;


                    filter.update(tempAnn);
                }
                else {
                    filter.nextStep(tempAnn);
                }

                anns[i] = tempAnn;
                if (onFinishOneBox)
                    onFinishOneBox(i);
                i--;
            }
        }

        return anns;
    },


}


function MaFilter(initX) {   // moving average filter
    this.x = initX;  // pose
    this.step = 0;

    this.v = [0, 0, 0, 0, 0, 0, 0, 0, 0];  // velocity
    this.ones = [1, 1, 1, 1, 1, 1, 1, 1, 1];
    this.decay = [0.5, 0.5, 0.5,
        0.5, 0.5, 0.5,
        0.5, 0.5, 0.5];

    this.update = function (x) {
        if (this.step == 0) {
            this.v = annMath.sub(x, this.x);
        } else {
            this.v = annMath.add(annMath.eleMul(annMath.sub(x, this.x), this.decay),
                annMath.eleMul(this.v, annMath.sub(this.ones, this.decay)));
        }

        this.x = x;
        this.step++;
    };

    this.predict = function () {
        let pred = [...annMath.add(this.x, this.v).slice(0, 6), ...this.x.slice(6)];
        return pred;
    };

    this.nextStep = function (x) {
        this.x = x;
        this.step++;
    };

}

export { MaFilter, ml };
