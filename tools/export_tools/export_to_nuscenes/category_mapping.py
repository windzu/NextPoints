# NextPoints to NuScenes Category Mapping Configuration
# This file maps NextPoints object types to NuScenes categories and attributes

# NuScenes Standard Categories
NUSCENES_CATEGORIES = [
    "human.pedestrian.adult",
    "human.pedestrian.child", 
    "human.pedestrian.wheelchair",
    "human.pedestrian.stroller",
    "human.pedestrian.personal_mobility",
    "human.pedestrian.police_officer",
    "human.pedestrian.construction_worker",
    "animal",
    "vehicle.rider",
    "vehicle.bicycle",
    "vehicle.bus.bendy",
    "vehicle.bus.rigid", 
    "vehicle.car",
    "vehicle.construction",
    "vehicle.emergency.ambulance",
    "vehicle.emergency.police",
    "vehicle.motorcycle",
    "vehicle.trailer",
    "vehicle.truck",
    "movable_object.barrier",
    "movable_object.trafficcone",
    "movable_object.pushable_pullable",
    "movable_object.debris",
    "static_object.bicycle_rack"
]

# NuScenes Standard Attributes
NUSCENES_ATTRIBUTES = [
    "vehicle.moving",
    "vehicle.stopped", 
    "vehicle.parked",
    "cycle.with_rider",
    "cycle.without_rider",
    "pedestrian.sitting_lying_down",
    "pedestrian.standing",
    "pedestrian.moving"
]

# Visibility levels (NuScenes standard)
NUSCENES_VISIBILITY = {
    "v0-40": "1",     # 0-40% visible
    "v40-60": "2",    # 40-60% visible  
    "v60-80": "3",    # 60-80% visible
    "v80-100": "4"    # 80-100% visible
}

# Category mapping from NextPoints to NuScenes
CATEGORY_MAPPING = {
    # Vehicles
    "car": "vehicle.car",
    "van": "vehicle.car", 
    "bus": "vehicle.bus.rigid",
    "truck": "vehicle.truck",
    "trailer": "vehicle.trailer",
    "motorcycle": "vehicle.motorcycle",
    
    # Pedestrians
    "pedestrian": "human.pedestrian.adult",
    "person": "human.pedestrian.adult",
    "child": "human.pedestrian.child",
    "police": "human.pedestrian.police_officer",
    "worker": "human.pedestrian.construction_worker",
    
    # Cycles
    "rider": "vehicle.rider",
    "bicycle": "vehicle.bicycle",
    "tricycle": "vehicle.tricycle",
    "bicycle_group": "vehicle.bicycle_group",
    
    # Animals
    "animal": "animal",
    "dog": "animal",
    "cat": "animal",

    # Movable objects
    "barrier": "movable_object.barrier",
    "traffic_cone": "movable_object.trafficcone",
    "cone": "movable_object.trafficcone",
    "debris": "movable_object.debris",

    # Static objects
    "bicycle_rack": "static_object.bicycle_rack",

    # Default for unknown categories
    "unknown": "movable_object.pushable_pullable"
}

# Attribute mapping based on object type and context
ATTRIBUTE_MAPPING = {
    # Vehicle attributes
    "vehicle.car": ["vehicle.moving", "vehicle.stopped", "vehicle.parked"],
    "vehicle.bus.rigid": ["vehicle.moving", "vehicle.stopped", "vehicle.parked"],
    "vehicle.truck": ["vehicle.moving", "vehicle.stopped", "vehicle.parked"],
    "vehicle.trailer": ["vehicle.moving", "vehicle.stopped", "vehicle.parked"],
    "vehicle.motorcycle": ["vehicle.moving", "vehicle.stopped", "vehicle.parked"],
    
    # Cycle attributes
    "vehicle.bicycle": ["cycle.with_rider", "cycle.without_rider"],
    
    # Pedestrian attributes
    "human.pedestrian.adult": ["pedestrian.standing", "pedestrian.moving", "pedestrian.sitting_lying_down"],
    "human.pedestrian.child": ["pedestrian.standing", "pedestrian.moving", "pedestrian.sitting_lying_down"],
    "human.pedestrian.police_officer": ["pedestrian.standing", "pedestrian.moving"],
    "human.pedestrian.construction_worker": ["pedestrian.standing", "pedestrian.moving"],
    
    # Default empty attributes for static objects
    "movable_object.barrier": [],
    "movable_object.trafficcone": [],
    "movable_object.pushable_pullable": [],
    "movable_object.debris": [],
    "static_object.bicycle_rack": [],
    "animal": []
}

# Default attribute selection (first attribute for each category)
DEFAULT_ATTRIBUTES = {
    "vehicle.car": "vehicle.stopped",
    "vehicle.bus.rigid": "vehicle.stopped", 
    "vehicle.truck": "vehicle.stopped",
    "vehicle.trailer": "vehicle.stopped",
    "vehicle.motorcycle": "vehicle.stopped",
    "vehicle.bicycle": "cycle.without_rider",
    "human.pedestrian.adult": "pedestrian.standing",
    "human.pedestrian.child": "pedestrian.standing",
    "human.pedestrian.police_officer": "pedestrian.standing",
    "human.pedestrian.construction_worker": "pedestrian.standing"
}

# Size constraints for categories (length, width, height in meters)
CATEGORY_SIZE_CONSTRAINTS = {
    "vehicle.car": {"min": [3.0, 1.5, 1.0], "max": [6.0, 2.5, 3.0]},
    "vehicle.bus.rigid": {"min": [8.0, 2.0, 2.5], "max": [15.0, 3.0, 4.0]},
    "vehicle.truck": {"min": [4.0, 2.0, 2.0], "max": [20.0, 3.5, 4.5]},
    "vehicle.trailer": {"min": [6.0, 2.0, 2.0], "max": [15.0, 3.0, 4.0]},
    "vehicle.motorcycle": {"min": [1.5, 0.5, 1.0], "max": [3.0, 1.0, 2.0]},
    "vehicle.bicycle": {"min": [1.2, 0.3, 0.8], "max": [2.2, 0.8, 1.5]},
    "human.pedestrian.adult": {"min": [0.3, 0.3, 1.5], "max": [0.8, 0.8, 2.0]},
    "human.pedestrian.child": {"min": [0.2, 0.2, 0.8], "max": [0.5, 0.5, 1.5]},
    "animal": {"min": [0.2, 0.2, 0.2], "max": [2.0, 1.5, 2.0]}
}

def get_nuscenes_category(nextpoints_type: str) -> str:
    """
    Get NuScenes category for NextPoints object type
    
    Args:
        nextpoints_type: NextPoints object type
        
    Returns:
        NuScenes category name
    """
    return CATEGORY_MAPPING.get(nextpoints_type, CATEGORY_MAPPING["Unknown"])


def get_default_attributes(category: str) -> list:
    """
    Get default attributes for a category
    
    Args:
        category: NuScenes category name
        
    Returns:
        List of attribute tokens (empty if no default)
    """
    default_attr = DEFAULT_ATTRIBUTES.get(category)
    return [default_attr] if default_attr else []


def validate_category_size(category: str, size: list) -> bool:
    """
    Validate if object size is reasonable for the category
    
    Args:
        category: NuScenes category name
        size: Object size [length, width, height]
        
    Returns:
        True if size is within reasonable bounds
    """
    if category not in CATEGORY_SIZE_CONSTRAINTS:
        return True  # No constraints defined
    
    constraints = CATEGORY_SIZE_CONSTRAINTS[category]
    min_size = constraints["min"]
    max_size = constraints["max"]
    
    for i in range(3):
        if size[i] < min_size[i] or size[i] > max_size[i]:
            return False
    
    return True


def get_all_nuscenes_categories() -> list:
    """Get all NuScenes categories"""
    return NUSCENES_CATEGORIES.copy()


def get_all_nuscenes_attributes() -> list:
    """Get all NuScenes attributes"""  
    return NUSCENES_ATTRIBUTES.copy()
