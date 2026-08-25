import urllib.parse

from config import S3_BUCKET_NAME
from s3_storage import (load_event_file, save_target_frame)
from image_recognition import (detect_target_frames, extract_jpeg_frames)


def process_s3_event(event):
    """
    Process an uploaded Lepton MJPEG file.

    PAG and Lepton are stored together in the same event.
    Image recognition is performed only on Lepton frames.
    Only frames containing configured targets are copied
    into the animals/ directory.
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

    # Image recognition must only be performed on Lepton.
    if sensor == "pag":
        process_pag_event(camera_id, event_id, uploaded_key)
    else:
        print("Ignoring non-PAG S3 event.")


def process_pag_event(camera_id, event_id, pag_key):
    """
    Analyze the PAG MJPEG and save only frames
    containing configured targets.
    """

    # Download the PAG MJPEG recording.
    pag_data = load_event_file(S3_BUCKET_NAME, pag_key )

    frames = extract_jpeg_frames(pag_data)

    print(f"Extracted {len(frames)} PAG frames.")

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