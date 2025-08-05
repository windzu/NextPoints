// size is the dimension of the object in x/y/z axis, with unit meter.

class ObjectCategory {

    // new object type map
    obj_type_map = {
        // vehicle
        // - cycle
        bicycle: { color: '#ff8800', size: [1.6, 0.6, 1.2] },
        motorcycle: { color: '#ff8800', size: [1.6, 0.6, 1.2] },
        tricycle: { color: '#ff8800', size: [1.6, 0.6, 1.2] },
        cycle_group: { color: '#ff8800', size: [1.6, 2.0, 1.2] },
        rider: { color: '#ff8800', size: [1.6, 0.6, 1.6] },
        cycle: { color: '#ff8800', size: [1.6, 0.6, 1.2] },
        // - car
        car: { color: '#86af49', size: [4.5, 1.8, 1.5] },
        // - truck
        van: { color: '#00ff00', size: [4.5, 1.8, 1.5] },
        pickup: { color: '#00ff00', size: [4.5, 1.8, 1.5] },
        cargo: { color: '#00ff00', size: [4.5, 1.8, 1.5] },
        trailer: { color: '#00ff00', size: [4.5, 1.8, 1.5] },
        truck: { color: '#00ff00', size: [4.5, 1.8, 1.5] },
        // - bus
        micro_bus: { color: '#ffff00', size: [13, 3, 3.5] },
        mini_bus: { color: '#ffff00', size: [13, 3, 3.5] },
        bus: { color: '#ffff00', size: [13, 3, 3.5] },
        // - construction
        construction_vehicle: { color: '#ff0000', size: [1.2, 0.8, 1.0] },

        /////////////////////////////////////////////////////////////
        // human
        // - pedestrian
        pedestrian: { color: '#00ffff', size: [0.4, 0.5, 1.7] },

        /////////////////////////////////////////////////////////////
        // animal
        // - animal
        animal: { color: '#00aaff', size: [1.6, 0.6, 1.2] },

        /////////////////////////////////////////////////////////////

        // static_object
        // - barrier
        barrier: { color: '#00aaff', size: [1.6, 0.6, 1.2] },
        // - trafficcone
        traffic_cone: { color: '#00aaff', size: [1.6, 0.6, 1.2] },
        // - stone
        stone: { color: '#00aaff', size: [1.6, 0.6, 1.2] },
        // - chair
        chair: { color: '#00aaff', size: [1.6, 0.6, 1.2] },
        // - trash_can
        trash_can: { color: '#00aaff', size: [0.8, 0.8, 1.2] },

        Unknown: { color: '#008888', size: [4.5, 1.8, 1.5] },
    };

    constructor() {
    }

    popularCategories = ["rider", "car", "van", "truck", "bus", "pedestrian", "traffic_cone"];

    // make sure popularCategories come from obj_type_map
    initPopularCategories() {
        this.popularCategories = this.popularCategories.filter(i => {
            return this.obj_type_map[i] !== undefined;
        });
    }


    guess_obj_type_by_dimension(scale) {

        var max_score = 0;
        var max_name = 0;
        this.popularCategories.forEach(i => {
            var o = this.obj_type_map[i];
            var scorex = o.size[0] / scale.x;
            var scorey = o.size[1] / scale.y;
            var scorez = o.size[2] / scale.z;

            if (scorex > 1) scorex = 1 / scorex;
            if (scorey > 1) scorey = 1 / scorey;
            if (scorez > 1) scorez = 1 / scorez;

            if (scorex + scorey + scorez > max_score) {
                max_score = scorex + scorey + scorez;
                max_name = i;
            }
        });

        console.log("guess type", max_name);
        return max_name;
    }

    global_color_idx = 0;
    get_color_by_id(id) {
        let idx = parseInt(id);

        if (!idx) {
            idx = this.global_color_idx;
            this.global_color_idx += 1;
        }

        idx %= 33;
        idx = idx * 19 % 33;

        return {
            x: idx * 8 / 256.0,
            y: 1 - idx * 8 / 256.0,
            z: (idx < 16) ? (idx * 2 * 8 / 256.0) : ((32 - idx) * 2 * 8 / 256.0),
        };
    }

    get_color_by_category(category) {
        let target_color_hex = parseInt("0x" + this.get_obj_cfg_by_type(category).color.slice(1));

        return {
            x: (target_color_hex / 256 / 256) / 255.0,
            y: (target_color_hex / 256 % 256) / 255.0,
            z: (target_color_hex % 256) / 255.0,
        };
    }

    get_obj_cfg_by_type(name) {
        if (this.obj_type_map[name]) {
            return this.obj_type_map[name];
        }
        else {
            return this.obj_type_map["Unknown"];
        }
    }
}


let globalObjectCategory = new ObjectCategory();

export { globalObjectCategory };
