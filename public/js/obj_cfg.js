// size is the dimension of the object in x/y/z axis, with unit meter.

class ObjectCategory
{

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
        bus:{color: '#ffff00',  size:[13, 3, 3.5]},
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
        barrier:{color: '#00aaff',  size:[1.6, 0.6, 1.2]},
        // - trafficcone
        traffic_cone:{color: '#00aaff',  size:[1.6, 0.6, 1.2]},
        // - stone
        stone:{color: '#00aaff',  size:[1.6, 0.6, 1.2]},
        // - chair
        chair: { color: '#00aaff', size: [1.6, 0.6, 1.2] },
        // - trash_can
        trash_can: { color: '#00aaff', size: [0.8, 0.8, 1.2] },

        Unknown: { color: '#008888', size: [4.5, 1.8, 1.5] },
    };

    

    // raw object type map
//     obj_type_map = {
//         //////////////////////////////////////////
//         // vehicle
//         //////////////////////////////////////////
//         // - cycle
//         Bicycle:        {color: '#ff8800',  size:[1.6, 0.6, 1.2], attr:["laying down"]},
//         // BicycleRider:   {color: '#88ff00',  size:[1.6, 0.6, 1.7], attr:["umbrella", "1 passenger", "2 passengers", "3 passengers"]},
//         Motorcycle:     {color: '#ff8800',  size:[1.6, 0.6, 1.2], attr:["umbrella"]},
//         // MotorcyleRider: {color: '#ff8800',  size:[1.6, 0.6, 1.6], attr:["umbrella", "1 passenger", "2 passengers", "3 passengers"]},
//         // ScooterRider:   {color: '#ff8800',  size:[1.6, 0.6, 1.6], attr:["umbrella", "1 passenger", "2 passengers", "3 passengers"]},
//         Scooter: { color: '#ff8800', size: [1.6, 0.6, 1.0] },
//         BicycleGroup: { color: '#ff8800', size: [1.6, 0.6, 1.2] },
//         Tricycle: { color: '#ff8800', size: [2.6, 1.0, 1.6] },
//         Rider: {color: '#ff8800',  size:[1.6, 0.6, 1.6], attr:["umbrella", "1 passenger", "2 passengers", "3 passengers"]},
//         
//         // - car
//         Car:            {color: '#86af49',  size:[4.5, 1.8, 1.5], attr:["door open", "trunk open"]},
//         // - truck
//         Van:            {color: '#00ff00',  size:[4.5, 1.8, 1.5], attr:["door open", "trunk open"]},
//         Truck:          {color: '#00ffff',  size:[10., 2.8, 3]},
//         // - bus
//         Bus: { color: '#ffff00', size: [13, 3, 3.5] },
//         // - construction
//         ConstructionCart: {color: '#ff0000',  size:[1.2, 0.8, 1.0]},
// 
//         //////////////////////////////////////////
//         // human
//         //////////////////////////////////////////
//         // - pedestrian
//         Pedestrian:     {color: '#88ff00',  size:[0.4, 0.5, 1.7], attr:["umbrella", "sitting", "squating", "bending over", "luggage"]},
// 
//         //////////////////////////////////////////
//         // animal
//         //////////////////////////////////////////
//         // - animal
//         Animal:         {color: '#00aaff',  size:[1.6, 0.6, 1.2]},
// 
//         //////////////////////////////////////////
//         // static_object
//         //////////////////////////////////////////
//         // - barrier
//         TrafficBarrier: {color: '#ff0000',  size:[1.5, 0.3, 1.2]},
//         // - trafficcone
//         Cone:           {color: '#86af49',  size:[0.3, 0.3, 0.6]},
//         // - trash_can
//         TrashCan: { color: '#00aaff', size: [0.6, 0.4, 1.0] },
//         
//         Unknown: { color: '#008888', size: [4.5, 1.8, 1.5] },
//         
// //         PoliceCar:      {color: '#86af49',  size:[4.5, 1.8, 1.5]},
// //         TourCar:        {color: '#86af49',  size:[4.4, 1.5, 2.2]},
// // 
// //         RoadWorker:     {color: '#ff0000',  size:[0.4, 0.5, 1.7]},
// //         Child:          {color: '#ff0000',  size:[0.4, 0.5, 1.2]},
// // 
// //         BabyCart:       {color: '#ff0000',  size:[0.8, 0.5, 1.0]},
// //         Cart:           {color: '#ff0000',  size:[0.8, 0.5, 1.0]},
// //         
// //         FireHydrant:    {color: '#ff0000',  size:[0.4, 0.4, 0.6]},
// //         SaftyTriangle:  {color: '#ff0000',  size:[0.3, 0.4, 0.4]},
// //         PlatformCart:   {color: '#ff0000',  size:[1.2, 0.8, 1.0]},
// //         
// //         RoadBarrel:     {color: '#ff0000',  size:[0.5, 0.5, 0.6]},
// //         LongVehicle:    {color: '#ff0000',  size:[16, 3, 3]},
// // 
// //         ConcreteTruck:  {color: '#00ffff',  size:[10., 2.8, 3]},
// //         Tram:           {color: '#00ffff',  size:[10., 2.8, 3]},
// //         Excavator:      {color: '#00ffff',  size:[6., 3, 3]},
// //  
// //         ForkLift:       {color: '#00aaff',  size:[5.0, 1.2, 2.0]},
// // 
// //         Crane:          {color: '#00aaff',  size:[5.0, 1.2, 2.0]},
// //         RoadRoller:     {color: '#00aaff',  size:[2.7, 1.5, 2.0]},
// //         Bulldozer:      {color: '#00aaff',  size:[3.0, 2.0, 2.0]},
// // 
// //         DontCare:       {color: '#00ff88',  size:[4, 4, 3]},
// //         Misc:           {color: '#008888',  size:[4.5, 1.8, 1.5]},
// 
//         
//         // Unknown1:       {color: '#008888',  size:[4.5, 1.8, 1.5]},
//         // Unknown2:       {color: '#008888',  size:[4.5, 1.8, 1.5]},
//         // Unknown3:       {color: '#008888',  size:[4.5, 1.8, 1.5]},
//         // Unknown4:       {color: '#008888',  size:[4.5, 1.8, 1.5]},
//         // Unknown5: { color: '#008888', size: [4.5, 1.8, 1.5] },
// 
//     };

    constructor(){
    }

    popularCategories = ["rider","car","van","truck", "bus","pedestrian", "traffic_cone"];

    // popularCategories = ["Bicycle","Scooter", "Rider","Car", "Van", "Bus", "Truck", "Pedestrian"];

    
    guess_obj_type_by_dimension(scale){

        var max_score = 0;
        var max_name = 0;
        this.popularCategories.forEach(i=>{
            var o = this.obj_type_map[i];
            var scorex = o.size[0]/scale.x;
            var scorey = o.size[1]/scale.y;
            var scorez = o.size[2]/scale.z;

            if (scorex>1) scorex = 1/scorex;
            if (scorey>1) scorey = 1/scorey;
            if (scorez>1) scorez = 1/scorez;

            if (scorex + scorey + scorez > max_score){
                max_score = scorex + scorey + scorez;
                max_name = i;
            }
        });

        console.log("guess type", max_name);
        return max_name;
    }

    global_color_idx = 0;
    get_color_by_id(id){
        let idx = parseInt(id);

        if (!idx)
        {
            idx = this.global_color_idx;
            this.global_color_idx += 1;
        }

        idx %= 33;
        idx = idx*19 % 33;

        return {
            x: idx*8/256.0,
            y: 1- idx*8/256.0,
            z: (idx<16)?(idx*2*8/256.0):((32-idx)*2*8/256.0),
        };
    }

    get_color_by_category(category){
        let target_color_hex = parseInt("0x"+this.get_obj_cfg_by_type(category).color.slice(1));
        
        return {
            x: (target_color_hex/256/256)/255.0,
            y: (target_color_hex/256 % 256)/255.0,
            z: (target_color_hex % 256)/255.0,
        };
    }

    get_obj_cfg_by_type(name){
        if (this.obj_type_map[name]){
            return this.obj_type_map[name];
        }
        else{
            return this.obj_type_map["Unknown"];
        }
    }
}


let globalObjectCategory = new ObjectCategory();

export { globalObjectCategory };
