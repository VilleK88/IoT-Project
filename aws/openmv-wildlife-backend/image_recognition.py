import boto3
import json

rekognition = boto3.client("rekognition", region_name="eu-central-1")

def load_recognition_config():
    """
    Load image-recognition settings from the local JSON file
    included in the Lambda deployment package.
    """

    with open("recognition_targets.json", "r") as file:
        return json.load(file)

# Load configuration once when the Lambda execution environment starts.
RECOGNITION_CONFIG = load_recognition_config()

TARGET_SPECIES = set(RECOGNITION_CONFIG["target_species"])
FRAME_INTERVAL = RECOGNITION_CONFIG["analyze_every_nth_frame"]
MIN_CONFIDENCE = RECOGNITION_CONFIG["minimum_confidence"]
MAX_LABELS = RECOGNITION_CONFIG["maximum_labels_per_frame"]
ORGANIZE_DETECTED_FRAMES = RECOGNITION_CONFIG["organize_detected_frames"]
COPY_SOURCE_VIDEO_TO_SPECIES_FOLDER = RECOGNITION_CONFIG["copy_source_video_to_species_folder"]

def detect_target_frames(frames):
    """
    Analyze sampled Lepton frames and return only frames
    containing one or more configured targets.

    Returns:
        List of dictionaries containing:
        - frame_number
        - frame bytes
        - detected targets
    """
    target_frames = []

    for frame_number, frame in enumerate(frames):
        # Analyze only every Nth frame.
        if frame_number % FRAME_INTERVAL == 0:
            labels = detect_labels(frame)
            print(
                f"Frame {frame_number} labels: "
                f"{[(label['Name'], round(label['Confidence'], 1)) for label in labels]}"
            )
            targets = get_target_labels(labels)
            # Store only frames containing at least one target.
            if targets:
                print(
                    f"Targets detected in frame {frame_number}: "
                    f"{targets}"
                )

                target_frames.append({
                    "frame_number": frame_number,
                    "frame": frame,
                    "targets": targets,
                })

    return target_frames
                

def detect_labels(frame):
    """Send one JPEG frame to Amazon Rekognition."""
    response = rekognition.detect_labels(
         Image={"Bytes": frame},
         MaxLabels=MAX_LABELS,
         MinConfidence=MIN_CONFIDENCE
    )
    return response["Labels"]

def get_target_labels(labels):
    """Return configured target labels found in a frame."""
    targets = []
    for label in labels:
        label_name = label["Name"]
        if label_name in TARGET_SPECIES:
            targets.append(label_name)
    return targets

def extract_jpeg_frames(mjpeg_data):
    """
    Extract individual JPEG frames from an MJPEG byte stream.
    """

    frames = []
    position = 0

    while True:
        # JPEG Start of Image marker: FF D8
        start = mjpeg_data.find(b"\xff\xd8", position)
        if start != -1:
            # JPEG End of Image marker: FF D9
            end = mjpeg_data.find(b"\xff\xd9", start)

            if end != -1:
                # Include the FF D9 bytes in the JPEG frame.
                end += 2
                frames.append(mjpeg_data[start:end])
                # Continue searching after the current frame.
                position = end
            else:
                break
        else:
            break
        
    return frames