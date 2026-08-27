import urllib.parse

from config import (S3_BUCKET_NAME, S3_UPLOADS_PREFIX)
from s3_storage import (
    load_event_file, save_target_frame, delete_event, object_exists
    )
from image_recognition import (detect_target_frames, extract_jpeg_frames)


def process_s3_event(event):
    """
    Process uploaded PAG and Lepton MJPEG files.

    PAG and Lepton are stored together in the same event.
    Image recognition is performed only on PAG frames.
    """

    # Get the S3 object key that triggered Lambda.
    uploaded_key = urllib.parse.unquote_plus(
        event["Records"][0]["s3"]["object"]["key"],
        encoding="utf-8"
    )

    camera_id, event_id, sensor = parse_event_key(uploaded_key)

    print(
        f"Processing event {event_id}, "
        f"camera {camera_id}, "
        f"sensor {sensor}"
    )

    # Image recognition must only be performed on PAG.
    if sensor == "pag":
        process_pag_event(camera_id, event_id, uploaded_key)
    elif sensor == "lepton":
        process_lepton_event(camera_id, event_id, uploaded_key)

def process_pag_event(camera_id, event_id, pag_key):
    """
    Analyze the PAG MJPEG and save only frames
    containing configured targets.

    Delete the complete event if no target is found.
    """

    # Download the PAG MJPEG recording.
    pag_data = load_event_file(S3_BUCKET_NAME, pag_key )

    # Extract individual JPEG frames.
    frames = extract_jpeg_frames(pag_data)

    print(f"Extracted {len(frames)} PAG frames.")

    # Analyze configured frames with Rekognition.
    target_frames = detect_target_frames(frames)

    if target_frames:
        print(f"Detected target frames: {len(target_frames)}")

        for target_frame in target_frames:
            frame_number = target_frame["frame_number"]
            frame = target_frame["frame"]
            targets = target_frame["targets"]

            for target in targets:
                object_key = save_target_frame(
                    S3_BUCKET_NAME,
                    target,
                    camera_id,
                    event_id,
                    frame_number,
                    frame
                )

                print(f"Saved target frame: {object_key}")
    else:
        print("No targets detected.")
        delete_event(S3_BUCKET_NAME, camera_id, event_id)
        print("Rejected event deleted.")

def process_lepton_event(camera_id, event_id, lepton_key):
    """
    Keep Lepton only if the matching PAG recording exists.
    """

    pag_key = (
        S3_UPLOADS_PREFIX 
        + "{}/event_{:05d}/pag.mjpeg").format(camera_id, int(event_id))

    if object_exists(S3_BUCKET_NAME, pag_key):
        print("Matching PAG found. Keeping Lepton.")
    else:
        print("Matching PAG not found. Deleting Lepton.")
        delete_event(S3_BUCKET_NAME, camera_id, event_id)

def parse_event_key(object_key):
    """
    Extract camera_id, event_id and sensor from an S3 object key.

    Example:
    uploads/camera_001/event_00042/lepton.mjpeg
    """

    parts = object_key.split("/")

    camera_id = parts[-3]
    event_dir = parts[-2]
    filename = parts[-1]

    event_id = int(event_dir.removeprefix("event_"))
    sensor = filename.removesuffix(".mjpeg")

    return camera_id, event_id, sensor