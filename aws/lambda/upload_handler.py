import boto3
import json
import os
import time
import urllib.parse


# AWS clients are created outside lambda_handler so that Lambda
# can reuse them between invocations when possible.
s3 = boto3.client("s3")

# Amazon Rekognition is called through the Ireland region because
# the service endpoint is not being used from the Stockholm region.
rekognition = boto3.client(
    "rekognition",
    region_name="eu-west-1"
)


# S3 object containing the user-configurable processing settings.
SETTINGS_KEY = "settings/upload_settings.json"

# Number of bytes read from the MJPEG file at a time.
READ_CHUNK_SIZE = 65536


# Used if the settings file is missing or contains an invalid value.
DEFAULT_SETTINGS = {
    "enabled": True,
    "target_species": [
        "Otter",
        "Beaver",
        "Bear",
        "Wolf",
        "Lynx",
        "Wolverine",
        "Fox",
        "Deer",
        "Moose",
        "Reindeer",
        "Wild Boar",
        "Badger",
        "Hare",
        "Rabbit",
        "Squirrel",
        "Marten",
        "Bird",
        "Duck",
        "Goose",
        "Swan",
        "Owl",
        "Eagle"
    ],
    "analyze_every_nth_frame": 5,
    "minimum_confidence": 70.0,
    "maximum_labels_per_frame": 20,
    "minimum_detection_frames": 2,
    "save_all_extracted_frames": True,
    "organize_detected_frames": True,
    "copy_source_video_to_species_folder": True
}


# Loads processing settings from S3.
def load_settings(bucket):
    try:
        response = s3.get_object(
            Bucket=bucket,
            Key=SETTINGS_KEY
        )

        settings_data = response["Body"].read()
        loaded_settings = json.loads(
            settings_data.decode("utf-8")
        )

        # Start with defaults and replace only values that are
        # present in the uploaded settings document.
        settings = DEFAULT_SETTINGS.copy()
        settings.update(loaded_settings)

        validate_settings(settings)

        print("Loaded settings:", SETTINGS_KEY)

        return settings

    except s3.exceptions.NoSuchKey:
        print(
            "Settings file not found. "
            "Using default settings."
        )

        return DEFAULT_SETTINGS.copy()

    except Exception as error:
        print(
            "Failed to load settings:",
            repr(error)
        )

        print("Using default settings.")

        return DEFAULT_SETTINGS.copy()


# Checks and normalizes values loaded from the settings file.
def validate_settings(settings):
    if not isinstance(
        settings.get("target_species"),
        list
    ):
        settings["target_species"] = (
            DEFAULT_SETTINGS["target_species"][:]
        )

    settings["target_species"] = [
        str(species)
        for species in settings["target_species"]
        if str(species).strip()
    ]

    settings["analyze_every_nth_frame"] = max(
        1,
        int(
            settings.get(
                "analyze_every_nth_frame",
                5
            )
        )
    )

    settings["minimum_confidence"] = float(
        settings.get(
            "minimum_confidence",
            70.0
        )
    )

    settings["maximum_labels_per_frame"] = max(
        1,
        int(
            settings.get(
                "maximum_labels_per_frame",
                20
            )
        )
    )

    settings["minimum_detection_frames"] = max(
        1,
        int(
            settings.get(
                "minimum_detection_frames",
                2
            )
        )
    )


# Returns True when the current frame should be analyzed.
def should_analyze_frame(
    frame_number,
    analyze_every_nth_frame
):
    return (
        frame_number == 1
        or (
            frame_number - 1
        ) % analyze_every_nth_frame == 0
    )


# Sends JPEG bytes directly to Amazon Rekognition.
#
# Bytes are used because the S3 bucket and Rekognition client
# operate through different AWS regions.
def detect_labels(
    frame_bytes,
    minimum_confidence,
    maximum_labels
):
    response = rekognition.detect_labels(
        Image={
            "Bytes": frame_bytes
        },
        MaxLabels=maximum_labels,
        MinConfidence=minimum_confidence
    )

    detected_labels = []

    for label in response.get("Labels", []):
        detected_label = {
            "name": label["Name"],
            "confidence": round(
                label["Confidence"],
                2
            ),
            "instances": []
        }

        # Object labels may contain individual instances with
        # confidence values and bounding boxes.
        for instance in label.get("Instances", []):
            detected_instance = {
                "confidence": round(
                    instance.get(
                        "Confidence",
                        0.0
                    ),
                    2
                )
            }

            bounding_box = instance.get(
                "BoundingBox"
            )

            if bounding_box is not None:
                detected_instance["bounding_box"] = {
                    "left": round(
                        bounding_box.get(
                            "Left",
                            0.0
                        ),
                        5
                    ),
                    "top": round(
                        bounding_box.get(
                            "Top",
                            0.0
                        ),
                        5
                    ),
                    "width": round(
                        bounding_box.get(
                            "Width",
                            0.0
                        ),
                        5
                    ),
                    "height": round(
                        bounding_box.get(
                            "Height",
                            0.0
                        ),
                        5
                    )
                }

            detected_label["instances"].append(
                detected_instance
            )

        detected_labels.append(
            detected_label
        )

    return detected_labels


# Uploads one extracted JPEG frame to S3.
def upload_frame(
    bucket,
    frame_key,
    frame_bytes
):
    s3.put_object(
        Bucket=bucket,
        Key=frame_key,
        Body=frame_bytes,
        ContentType="image/jpeg"
    )


# Extracts JPEG frames from the MJPEG file.
#
# JPEG frames begin with FF D8 and end with FF D9.
# Every extracted frame can be stored in S3, while only the
# configured subset is analyzed with Rekognition.
def extract_upload_and_analyze_frames(
    mjpeg_path,
    bucket,
    frame_output_prefix,
    settings
):
    frame_count = 0
    analyzed_frame_count = 0

    frame_data = bytearray()
    inside_frame = False
    previous_byte = None

    analyzed_frames = []

    analyze_interval = settings[
        "analyze_every_nth_frame"
    ]

    save_all_frames = settings[
        "save_all_extracted_frames"
    ]

    with open(mjpeg_path, "rb") as mjpeg_file:
        while True:
            chunk = mjpeg_file.read(
                READ_CHUNK_SIZE
            )

            if not chunk:
                break

            for current_byte in chunk:
                # Look for JPEG start marker FF D8.
                if not inside_frame:
                    if (
                        previous_byte == 0xFF
                        and current_byte == 0xD8
                    ):
                        inside_frame = True

                        frame_data = bytearray(
                            (0xFF, 0xD8)
                        )

                else:
                    frame_data.append(
                        current_byte
                    )

                    # Look for JPEG end marker FF D9.
                    if (
                        previous_byte == 0xFF
                        and current_byte == 0xD9
                    ):
                        frame_count += 1

                        frame_filename = (
                            "frame_{:05d}.jpg".format(
                                frame_count
                            )
                        )

                        frame_key = (
                            frame_output_prefix
                            + "/"
                            + frame_filename
                        )

                        frame_bytes = bytes(
                            frame_data
                        )

                        analyze_frame = (
                            should_analyze_frame(
                                frame_count,
                                analyze_interval
                            )
                        )

                        # Save all frames when enabled. Analyzed
                        # frames are always saved because the
                        # result JSON references their S3 keys.
                        if (
                            save_all_frames
                            or analyze_frame
                        ):
                            upload_frame(
                                bucket,
                                frame_key,
                                frame_bytes
                            )

                        if analyze_frame:
                            detected_labels = (
                                detect_labels(
                                    frame_bytes,
                                    settings[
                                        "minimum_confidence"
                                    ],
                                    settings[
                                        "maximum_labels_per_frame"
                                    ]
                                )
                            )

                            analyzed_frame_count += 1

                            analyzed_frames.append({
                                "frame_number": (
                                    frame_count
                                ),
                                "frame_key": frame_key,
                                "labels": detected_labels
                            })

                            print(
                                "Analyzed frame:",
                                frame_count
                            )

                            print(
                                "Detected labels:",
                                len(detected_labels)
                            )

                        inside_frame = False
                        frame_data = bytearray()

                previous_byte = current_byte

    if inside_frame:
        print(
            "Warning: MJPEG ended with "
            "an incomplete JPEG frame"
        )

    return {
        "frame_count": frame_count,
        "analyzed_frame_count": (
            analyzed_frame_count
        ),
        "analyzed_frames": analyzed_frames
    }


# Collects video-level statistics for every detected label.
def collect_label_statistics(analyzed_frames):
    label_statistics = {}

    for frame in analyzed_frames:
        frame_number = frame[
            "frame_number"
        ]

        labels_seen_in_frame = set()

        for label in frame["labels"]:
            label_name = label["name"]

            # Count one label only once per analyzed frame.
            if label_name in labels_seen_in_frame:
                continue

            labels_seen_in_frame.add(
                label_name
            )

            if label_name not in label_statistics:
                label_statistics[label_name] = {
                    "name": label_name,
                    "frame_count": 0,
                    "frames": [],
                    "frame_keys": [],
                    "highest_confidence": 0.0
                }

            statistics = label_statistics[
                label_name
            ]

            statistics["frame_count"] += 1

            statistics["frames"].append(
                frame_number
            )

            statistics["frame_keys"].append(
                frame["frame_key"]
            )

            statistics["highest_confidence"] = max(
                statistics[
                    "highest_confidence"
                ],
                label["confidence"]
            )

    return label_statistics


# Creates a summary of confirmed target-species detections.
#
# A species is confirmed only when it appears in at least the
# configured number of analyzed frames.
def create_detection_summary(
    analyzed_frames,
    settings
):
    label_statistics = (
        collect_label_statistics(
            analyzed_frames
        )
    )

    minimum_frames = settings[
        "minimum_detection_frames"
    ]

    target_species_lookup = {
        species.lower(): species
        for species in settings[
            "target_species"
        ]
    }

    confirmed_labels = []
    confirmed_target_species = []

    for statistics in label_statistics.values():
        if (
            statistics["frame_count"]
            < minimum_frames
        ):
            continue

        confirmed_label = {
            "name": statistics["name"],
            "frame_count": (
                statistics["frame_count"]
            ),
            "frames": statistics["frames"],
            "highest_confidence": round(
                statistics[
                    "highest_confidence"
                ],
                2
            )
        }

        confirmed_labels.append(
            confirmed_label
        )

        normalized_name = statistics[
            "name"
        ].lower()

        if normalized_name in target_species_lookup:
            confirmed_target_species.append({
                "name": target_species_lookup[
                    normalized_name
                ],
                "rekognition_label": (
                    statistics["name"]
                ),
                "frame_count": (
                    statistics["frame_count"]
                ),
                "frames": statistics["frames"],
                "frame_keys": (
                    statistics["frame_keys"]
                ),
                "highest_confidence": round(
                    statistics[
                        "highest_confidence"
                    ],
                    2
                )
            })

    confirmed_labels.sort(
        key=lambda item: (
            -item["frame_count"],
            item["name"]
        )
    )

    confirmed_target_species.sort(
        key=lambda item: (
            -item["frame_count"],
            item["name"]
        )
    )

    return {
        "minimum_detection_frames": (
            minimum_frames
        ),
        "target_species_detected": bool(
            confirmed_target_species
        ),
        "detected_target_species": [
            species["name"]
            for species
            in confirmed_target_species
        ],
        "target_species": (
            confirmed_target_species
        ),
        "confirmed_labels": confirmed_labels
    }


# Converts an animal name into a safe S3 path segment.
def create_species_path_name(species_name):
    safe_name = species_name.strip().lower()

    safe_name = safe_name.replace(
        " ",
        "_"
    )

    safe_name = safe_name.replace(
        "/",
        "_"
    )

    safe_name = safe_name.replace(
        "\\",
        "_"
    )

    return safe_name


# Copies confirmed target-species frames and optionally the source
# MJPEG into species-specific S3 paths.
def organize_confirmed_detections(
    bucket,
    source_key,
    video_name,
    filename,
    detection_summary,
    settings
):
    if not settings[
        "organize_detected_frames"
    ]:
        return []

    organized_species = []

    for species in detection_summary[
        "target_species"
    ]:
        species_name = species["name"]

        species_path = (
            create_species_path_name(
                species_name
            )
        )

        destination_prefix = (
            "animals/"
            + species_path
            + "/"
            + video_name
        )

        copied_frames = []

        # Copy every analyzed frame in which the confirmed
        # species was detected.
        for frame_key in sorted(
            set(species["frame_keys"])
        ):
            frame_filename = os.path.basename(
                frame_key
            )

            destination_frame_key = (
                destination_prefix
                + "/frames/"
                + frame_filename
            )

            s3.copy_object(
                Bucket=bucket,
                CopySource={
                    "Bucket": bucket,
                    "Key": frame_key
                },
                Key=destination_frame_key,
                ContentType="image/jpeg",
                MetadataDirective="REPLACE"
            )

            copied_frames.append(
                destination_frame_key
            )

        destination_video_key = None

        if settings[
            "copy_source_video_to_species_folder"
        ]:
            destination_video_key = (
                destination_prefix
                + "/"
                + filename
            )

            s3.copy_object(
                Bucket=bucket,
                CopySource={
                    "Bucket": bucket,
                    "Key": source_key
                },
                Key=destination_video_key
            )

        organized_species.append({
            "species": species_name,
            "destination_prefix": (
                destination_prefix
            ),
            "video_key": (
                destination_video_key
            ),
            "frame_keys": copied_frames
        })

        print(
            "Organized detection:",
            species_name,
            "Frames:",
            len(copied_frames)
        )

    return organized_species


# Creates the final result JSON document.
def create_result_document(
    source_key,
    source_size,
    processing_duration_ms,
    processing_result,
    detection_summary,
    organized_detections,
    settings
):
    return {
        "source_video": source_key,
        "source_size_bytes": source_size,
        "total_frames": (
            processing_result["frame_count"]
        ),
        "analyzed_frames": (
            processing_result[
                "analyzed_frame_count"
            ]
        ),
        "processing_duration_ms": (
            processing_duration_ms
        ),
        "settings": {
            "target_species": (
                settings["target_species"]
            ),
            "analyze_every_nth_frame": (
                settings[
                    "analyze_every_nth_frame"
                ]
            ),
            "minimum_confidence": (
                settings[
                    "minimum_confidence"
                ]
            ),
            "maximum_labels_per_frame": (
                settings[
                    "maximum_labels_per_frame"
                ]
            ),
            "minimum_detection_frames": (
                settings[
                    "minimum_detection_frames"
                ]
            )
        },
        "summary": detection_summary,
        "organized_detections": (
            organized_detections
        ),
        "frames": (
            processing_result[
                "analyzed_frames"
            ]
        )
    }


# Saves the final processing result as JSON in S3.
def save_result_json(
    bucket,
    result_key,
    result_document
):
    result_bytes = json.dumps(
        result_document,
        indent=2
    ).encode("utf-8")

    s3.put_object(
        Bucket=bucket,
        Key=result_key,
        Body=result_bytes,
        ContentType="application/json"
    )


# Processes one MJPEG object from an S3 event record.
def process_mjpeg_record(record):
    processing_start_time = time.time()

    bucket = record[
        "s3"
    ]["bucket"]["name"]

    source_key = urllib.parse.unquote_plus(
        record[
            "s3"
        ]["object"]["key"]
    )

    filename = os.path.basename(
        source_key
    )

    video_name = os.path.splitext(
        filename
    )[0]

    local_mjpeg_path = os.path.join(
        "/tmp",
        filename
    )

    frame_output_prefix = (
        "frames/"
        + video_name
    )

    result_key = (
        "results/"
        + video_name
        + ".json"
    )

    settings = load_settings(
        bucket
    )

    if not settings["enabled"]:
        print(
            "Processing disabled in settings"
        )

        return {
            "source": source_key,
            "processing_enabled": False
        }

    try:
        print("Bucket:", bucket)
        print("Source key:", source_key)
        print(
            "Downloading to:",
            local_mjpeg_path
        )

        s3.download_file(
            bucket,
            source_key,
            local_mjpeg_path
        )

        source_size = os.path.getsize(
            local_mjpeg_path
        )

        print(
            "Downloaded file size:",
            source_size
        )

        processing_result = (
            extract_upload_and_analyze_frames(
                local_mjpeg_path,
                bucket,
                frame_output_prefix,
                settings
            )
        )

        detection_summary = (
            create_detection_summary(
                processing_result[
                    "analyzed_frames"
                ],
                settings
            )
        )

        organized_detections = (
            organize_confirmed_detections(
                bucket,
                source_key,
                video_name,
                filename,
                detection_summary,
                settings
            )
        )

        processing_duration_ms = int(
            (
                time.time()
                - processing_start_time
            )
            * 1000
        )

        result_document = (
            create_result_document(
                source_key,
                source_size,
                processing_duration_ms,
                processing_result,
                detection_summary,
                organized_detections,
                settings
            )
        )

        save_result_json(
            bucket,
            result_key,
            result_document
        )

        print(
            "Extracted frames:",
            processing_result[
                "frame_count"
            ]
        )

        print(
            "Analyzed frames:",
            processing_result[
                "analyzed_frame_count"
            ]
        )

        print(
            "Target species detected:",
            detection_summary[
                "target_species_detected"
            ]
        )

        print(
            "Detected target species:",
            detection_summary[
                "detected_target_species"
            ]
        )

        print(
            "Result JSON:",
            result_key
        )

        print(
            "Processing duration ms:",
            processing_duration_ms
        )

        return {
            "source": source_key,
            "result_key": result_key,
            "frame_count": (
                processing_result[
                    "frame_count"
                ]
            ),
            "analyzed_frame_count": (
                processing_result[
                    "analyzed_frame_count"
                ]
            ),
            "target_species_detected": (
                detection_summary[
                    "target_species_detected"
                ]
            ),
            "detected_target_species": (
                detection_summary[
                    "detected_target_species"
                ]
            )
        }

    finally:
        # Always remove the temporary MJPEG file.
        if os.path.exists(
            local_mjpeg_path
        ):
            os.remove(
                local_mjpeg_path
            )


# AWS Lambda entry point.
def lambda_handler(event, context):
    processed_files = []

    for record in event.get(
        "Records",
        []
    ):
        try:
            processed_file = (
                process_mjpeg_record(
                    record
                )
            )

            processed_files.append(
                processed_file
            )

        except Exception as error:
            print(
                "MJPEG processing failed:",
                repr(error)
            )

            # Mark the invocation as failed so AWS can retry it.
            raise

    return {
        "statusCode": 200,
        "processed_files": processed_files
    }