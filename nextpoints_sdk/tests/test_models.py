from nextpoints_sdk.models.project_metadata import (
    ProjectMetadataResponse,
    FrameMetadata,
    ProjectResponse,
)
from nextpoints_sdk.models.calibration import (
    CalibrationMetadata,
    SensorType,
    CameraConfig,
    CameraIntrinsics,
    CameraDistortion,
)
from nextpoints_sdk.models.pose import Pose, Transform, Translation, Rotation


def build_sample():
    calib = CalibrationMetadata(
        channel="L1",
        sensor_type=SensorType.LIDAR,
        pose=Pose(
            parent_frame_id="world",
            child_frame_id="L1",
            transform=Transform(
                translation=Translation(x=0, y=0, z=0),
                rotation=Rotation(x=0, y=0, z=0, w=1),
            ),
        ),
    )
    frame = FrameMetadata(
        id=1,
        timestamp_ns="1000",
        prev_timestamp_ns="0",
        next_timestamp_ns="2000",
        lidars={"L1": "https://example.com/pcd1"},
        images=None,
        pose=None,
        annotation=None,
    )
    return ProjectMetadataResponse(
        project=ProjectResponse(id=1, name="demo"),
        frame_count=1,
        start_timestamp_ns="1000",
        end_timestamp_ns="1000",
        duration_seconds=0.0,
        main_channel="L1",
        calibration={"L1": calib},
        frames=[frame],
    )


def test_project_metadata_validation():
    m = build_sample()
    assert m.frame_count == 1
