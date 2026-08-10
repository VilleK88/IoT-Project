import boto3
import json
import os
import time
import urllib.parse

# AWS clients are created outside lambda_handler so that Lambda
# can reuse them between invocations when possible.
s3 = boto3.client("s3")

# DynamoDB stores the processing state and searchable metadata for each video.
dynamodb = boto3.resource("dynamodb")
STATUS_TABLE_NAME = os.environ.get(
    "STATUS_TABLE_NAME",
    "IoTMediaProcessingStatus"
)
status_table = dynamodb.Table(STATUS_TABLE_NAME)

# Amazon Rekognition is called through the Ireland region because
# the service endpoint is not being used from the Stockholm region.
rekognition = boto3.client("rekognition", region_name="eu-west-1")

# S3 object containing the user-configurable processing settings.
SETTINGS_KEY = "settings/upload_settings.json"
# Number of bytes read from the MJPEG file at a time.
READ_CHUNK_SIZE = 65536

# Writes the current processing state and metadata to DynamoDB.
#
# The DynamoDB table must use "video_key" as its partition key.
def save_processing_status(video_key, status, **attributes):
    item = {"video_key": video_key, "status": status, "updated_at": int(time.time())}

    # DynamoDB does not accept Python None values.
    for key, value in attributes.items():
        if value is not None:
            item[key] = value

    status_table.put_item(Item=item)

# Converts a processing summary into DynamoDB-safe metadata.
def create_database_metadata(
    source_size,
    processing_duration_ms,
    processing_result,
    detection_summary,
    organized_detections
):
    return {
        "source_size_bytes": source_size,
        "total_frames": processing_result["frame_count"],
        "analyzed_frames": processing_result["analyzed_frame_count"],
        "processing_duration_ms": (processing_duration_ms),
        "target_species_detected": (detection_summary["target_species_detected"]),
        "detected_target_species": (detection_summary["detected_target_species"]),
        # Store the detailed structures as JSON strings so the
        # database item remains simple and avoids float conversion issues.
        "summary_json": json.dumps(detection_summary),
        "organized_detections_json": json.dumps(organized_detections)
    }

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
        response = s3.get_object(Bucket=bucket, Key=SETTINGS_KEY)
        settings_data = response["Body"].read()
        loaded_settings = json.loads(settings_data.decode("utf-8"))

        # Start with defaults and replace only values that are
        # present in the uploaded settings document.
        settings = DEFAULT_SETTINGS.copy()
        settings.update(loaded_settings)
        validate_settings(settings)
        print("Loaded settings:", SETTINGS_KEY)
        return settings

    except s3.exceptions.NoSuchKey:
        print("Settings file not found. " "Using default settings.")
        return DEFAULT_SETTINGS.copy()

    except Exception as error:
        print("Failed to load settings:", repr(error))
        print("Using default settings.")
        return DEFAULT_SETTINGS.copy()

# Validates and normalizes the processing settings loaded
# from the configuration file.
#
# Invalid or missing values are replaced with safe defaults
# to ensure the processing pipeline always receives valid
# configuration values.
def validate_settings(settings):
    # Ensure the target species list exists.
    if not isinstance(settings.get("target_species"), list):
        settings["target_species"] = (DEFAULT_SETTINGS["target_species"][:])

    # Remove empty entries and normalize every species name to a string.
    settings["target_species"] = [
        str(species)
        for species in settings["target_species"]
        if str(species).strip()
    ]

    # Validate the numeric processing settings.
    settings["analyze_every_nth_frame"] = max(1, int(settings.get("analyze_every_nth_frame", 5)))
    settings["minimum_confidence"] = float(settings.get("minimum_confidence", 70.0))
    settings["maximum_labels_per_frame"] = max(1, int(settings.get("maximum_labels_per_frame", 20)))
    settings["minimum_detection_frames"] = max(1, int(settings.get("minimum_detection_frames", 2)))

# Returns True when the current frame should be analyzed.
def should_analyze_frame(frame_number, analyze_every_nth_frame):
    return (frame_number == 1 or (frame_number - 1) % analyze_every_nth_frame == 0)

# Sends a JPEG image directly to Amazon Rekognition and converts
# the response into the project's simplified label format.
#
# Image bytes are sent directly because the S3 bucket and the
# Rekognition client operate in different AWS regions.
#
# Each detected label may also contain one or more object
# instances with individual confidence values and bounding boxes.
def detect_labels(frame_bytes, minimum_confidence, maximum_labels):
    # Request object labels from Amazon Rekognition.
    response = rekognition.detect_labels(
        Image={"Bytes": frame_bytes},
        MaxLabels=maximum_labels,
        MinConfidence=minimum_confidence
    )

     # Store the simplified detection results returned by Rekognition.
    detected_labels = []

    # Process every label returned by Rekognition.
    for label in response.get("Labels", []):
        detected_label = {"name": label["Name"], "confidence": round(label["Confidence"], 2), "instances": []}

        # Object labels may contain individual instances with
        # confidence values and bounding boxes.
        for instance in label.get("Instances", []):
            detected_instance = {"confidence": round(instance.get("Confidence", 0.0), 2)}
            bounding_box = instance.get("BoundingBox")

            if bounding_box is not None:
                detected_instance["bounding_box"] = {
                    "left": round(bounding_box.get("Left", 0.0), 5),
                    "top": round(bounding_box.get("Top", 0.0),5),
                    "width": round(bounding_box.get("Width", 0.0), 5),
                    "height": round(bounding_box.get("Height", 0.0), 5)
                }

            detected_label["instances"].append(detected_instance)

        # Add the processed label to the detection results.
        detected_labels.append(detected_label)

    # Return the simplified Rekognition response.
    return detected_labels

# Uploads one extracted JPEG frame to Amazon S3.
#
# Metadata is attached directly to the frame so it remains
# associated with its source video and processing result
# without requiring a separate JSON result object.
def upload_frame(
    bucket,
    frame_key,
    frame_bytes,
    source_video_key,
    frame_number,
    analyzed,
    detected_labels=None
):
    metadata = {
        "source-video-key": source_video_key,
        "frame-number": str(frame_number),
        "analyzed": str(analyzed).lower()
    }

    # Recognition metadata exists only for frames selected
    # for Amazon Rekognition analysis.
    if detected_labels:
        label_names = sorted({label["name"] for label in detected_labels})
        highest_confidence = max((label["confidence"] for label in detected_labels), default=0.0)
        metadata.update({
            "detected-labels": ",".join(label_names),
            "highest-confidence": str(
                highest_confidence
            )
        })
    
    s3.put_object(
        Bucket=bucket,
        Key=frame_key,
        Body=frame_bytes,
        ContentType="image/jpeg",
        Metadata=metadata
    )

# Attaches the completed processing summary directly to an
# existing MJPEG object in Amazon S3.
#
# S3 object metadata cannot be edited in place, so the object
# is copied onto itself with replacement metadata.
def update_video_metadata(
        bucket,
        video_key,
        processing_result,
        detection_summary,
        processing_duration_ms
):
    # Read the current object properties so existing metadata
    # and the content type can be preserved.
    video_object = s3.head_object(Bucket=bucket, Key=video_key)

    metadata = video_object.get("Metadata",{}).copy()

    metadata.update({
        "processing-status": "completed",
        "total-frames": str(processing_result["frame_count"]),
        "analyzed-frames": str(processing_result["analyzed_frame_count"]),
        "target-species-detected": str(detection_summary["target_species_detected"]).lower(),
        "detected-target-species": ",".join(detection_summary["detected_target_species"]),
        "processing-duration-ms": str(processing_duration_ms)
    })

    copy_arguments = {
        "Bucket": bucket,
        "Key": video_key,
        "CopySource": {
            "Bucket": bucket,
            "Key": video_key
        },
        "Metadata": metadata,
        "MetadataDirective": "REPLACE"
    }

    # Preserve the original content type while replacing
    # the object's user-defined metadata.
    content_type = video_object.get("ContentType")

    if content_type:
        copy_arguments["ContentType"] = content_type

    s3.copy_object(**copy_arguments)

# Extracts JPEG frames from an MJPEG video, uploads the selected frames,
# analyzes them with Amazon Rekognition, and returns the processing summary.
#
# JPEG frames begin with FF D8 and end with FF D9.
# Every extracted frame can be stored in S3, while only the
# configured subset is analyzed with Rekognition.
def extract_upload_and_analyze_frames(
    mjpeg_path,
    bucket,
    source_video_key,
    frame_output_prefix,
    settings
):
    frame_count = 0
    analyzed_frame_count = 0

    # State used while scanning the MJPEG byte stream for JPEG start/end markers.
    frame_data = bytearray()
    inside_frame = False
    previous_byte = None

    analyzed_frames = []

    # Read the frame processing configuration.
    analyze_interval = settings["analyze_every_nth_frame"]
    save_all_frames = settings["save_all_extracted_frames"]

    with open(mjpeg_path, "rb") as mjpeg_file:
        # Read the MJPEG file incrementally to avoid loading
        # the entire video into memory.
        while True:
            chunk = mjpeg_file.read(READ_CHUNK_SIZE)

            # End of file reached.
            if not chunk:
                break

            for current_byte in chunk:
                # Look for JPEG start marker FF D8.
                if not inside_frame:
                    # Scan the MJPEG byte stream one byte at a time.
                    # Every JPEG frame begins with FF D8 and ends with FF D9.
                    if (previous_byte == 0xFF and current_byte == 0xD8):
                        inside_frame = True
                        frame_data = bytearray((0xFF, 0xD8))

                else:
                    frame_data.append(current_byte)

                    # Look for JPEG end marker FF D9.
                    if (previous_byte == 0xFF and current_byte == 0xD9):
                        frame_count += 1
                        frame_filename = ("frame_{:05d}.jpg".format(frame_count))
                        frame_key = (frame_output_prefix + "/" + frame_filename)
                        frame_bytes = bytes(frame_data)
                        analyze_frame = (should_analyze_frame(frame_count, analyze_interval))

                        detected_labels = None

                        # Analyze only the configured subset of frames.
                        if analyze_frame:
                            detected_labels = detect_labels(
                                frame_bytes,
                                settings["minimum_confidence"],
                                settings["maximum_labels_per_frame"]
                            )

                            analyzed_frame_count += 1

                            analyzed_frames.append({
                                "frame_number": frame_count,
                                "frame_key": frame_key,
                                "labels": detected_labels
                            })

                            print("Analyzed frame:", frame_count)
                            print(
                                "Detected labels:",
                                len(detected_labels)
                            )

                        # Preserve the existing frame-storage behavior:
                        # save every extracted frame when enabled,
                        # otherwise save only analyzed frames.
                        if save_all_frames or analyze_frame:
                            upload_frame(
                                bucket,
                                frame_key,
                                frame_bytes,
                                source_video_key,
                                frame_count,
                                analyze_frame,
                                detected_labels
                            )

                        # Reset the parser state before searching for
                        # the next JPEG frame in the MJPEG stream.
                        inside_frame = False
                        frame_data = bytearray()

                previous_byte = current_byte

    # Warn if the MJPEG stream ended before a complete
    # JPEG frame was reconstructed.
    if inside_frame:
        print("Warning: MJPEG ended with an incomplete JPEG frame")

    return {
        "frame_count": frame_count,
        "analyzed_frame_count": analyzed_frame_count,
        "analyzed_frames": analyzed_frames
    }

# Collects video-level statistics for every detected Rekognition label.
#
# Every analyzed frame contributes at most one detection per label,
# even if Rekognition reports the same label multiple times within
# the frame (for example, multiple dogs or people).
#
# The returned statistics are later used to determine which labels
# and target species are confirmed for the entire video.
def collect_label_statistics(analyzed_frames):
    label_statistics = {}

    # Process every analyzed frame independently.
    for frame in analyzed_frames:
        frame_number = frame["frame_number"]

        # Track which labels have already been counted in the current frame.
        labels_seen_in_frame = set()

        # Process every Rekognition label detected in the frame.
        for label in frame["labels"]:
            label_name = label["name"]

            # Count each label only once per analyzed frame.
            if label_name in labels_seen_in_frame:
                continue

            labels_seen_in_frame.add(label_name)

            # Create the statistics entry the first time the
            # label is encountered.
            if label_name not in label_statistics:
                label_statistics[label_name] = {
                    "name": label_name,
                    "frame_count": 0,
                    "frames": [],
                    "frame_keys": [],
                    "highest_confidence": 0.0
                }

            # Update the cumulative statistics for the label.
            statistics = label_statistics[label_name]
            statistics["frame_count"] += 1
            statistics["frames"].append(frame_number)
            statistics["frame_keys"].append(frame["frame_key"])
            statistics["highest_confidence"] = max(statistics["highest_confidence"],label["confidence"])

    return label_statistics

# Creates a video-level summary from all analyzed frames.
#
# Every detected Rekognition label is first collected across all
# analyzed frames. A label is considered confirmed only if it
# appears in at least the configured number of analyzed frames.
#
# The returned summary contains:
#   - All confirmed Rekognition labels.
#   - Confirmed target species defined in the processing settings.
#   - A list of the detected target species.
def create_detection_summary(analyzed_frames, settings):
    # Count how often every Rekognition label appears across
    # all analyzed frames.
    label_statistics = collect_label_statistics(analyzed_frames)

    minimum_frames = settings["minimum_detection_frames"]

    # Build a case-insensitive lookup table for the configured
    # target species.
    target_species_lookup = {species.lower(): species for species in settings["target_species"]}

    confirmed_labels = []
    confirmed_target_species = []

    # Evaluate every detected label.
    for statistics in label_statistics.values():
        # Confirm labels that were detected in enough analyzed frames.
        if statistics["frame_count"] >= minimum_frames:
            # Store the confirmed Rekognition label.
            confirmed_label = {
                "name": statistics["name"],
                "frame_count": statistics["frame_count"],
                "frames": statistics["frames"],
                "highest_confidence": round(statistics["highest_confidence"], 2)
            }

            confirmed_labels.append(confirmed_label)
            normalized_name = statistics["name"].lower()

            # Check whether the confirmed label is one of the
            # configured target species.
            if normalized_name in target_species_lookup:
                # Store additional information for the confirmed
                # target species.
                confirmed_target_species.append({
                    "name": target_species_lookup[normalized_name],
                    "rekognition_label": statistics["name"],
                    "frame_count": statistics["frame_count"],
                    "frames": statistics["frames"],
                    "frame_keys": statistics["frame_keys"],
                    "highest_confidence": round(statistics["highest_confidence"], 2)
                })

    # Sort the summaries so the most frequently detected
    # labels and species appear first.
    confirmed_labels.sort(key=lambda item: (-item["frame_count"], item["name"]))

    confirmed_target_species.sort(key=lambda item: (-item["frame_count"], item["name"]))

    # Return the complete detection summary for the video.
    return {
        "minimum_detection_frames": minimum_frames,
        "target_species_detected": bool(confirmed_target_species),
        "detected_target_species": [species["name"] for species in confirmed_target_species],
        "target_species": confirmed_target_species,
        "confirmed_labels": confirmed_labels
    }

# Converts an animal name into a safe S3 path segment.
def create_species_path_name(species_name):
    safe_name = species_name.strip().lower()
    safe_name = safe_name.replace(" ", "_")
    safe_name = safe_name.replace("/", "_")
    safe_name = safe_name.replace("\\", "_")
    return safe_name

# Organizes confirmed target-species detections into species-specific
# folders in Amazon S3.
#
# For every confirmed species:
#   1. Copy all matching detection frames.
#   2. Optionally copy the original MJPEG video.
#   3. Return the created S3 locations for DynamoDB metadata.
def organize_confirmed_detections(
    bucket,
    source_key,
    video_name,
    filename,
    detection_summary,
    settings
):
    # Skip organization when disabled in the processing settings.
    if not settings["organize_detected_frames"]:
        return []

    organized_species = []

    # Process every confirmed target species independently.
    for species in detection_summary["target_species"]:
        species_name = species["name"]
        species_path = (create_species_path_name(species_name))
        destination_prefix = ("animals/" + species_path + "/" + video_name)
        copied_frames = []

        # Copy every analyzed frame in which the confirmed
        # species was detected.
        for frame_key in sorted(set(species["frame_keys"])):
            frame_filename = os.path.basename(frame_key)
            destination_frame_key = (destination_prefix + "/frames/" + frame_filename)

            s3.copy_object(
                Bucket=bucket,
                CopySource={
                    "Bucket": bucket,
                    "Key": frame_key
                },
                Key=destination_frame_key,
            )

            copied_frames.append(destination_frame_key)

        destination_video_key = None

        # Optionally copy the original MJPEG recording into the
        # species folder so the full event is available alongside
        # the extracted detection frames.
        if settings["copy_source_video_to_species_folder"]:
            destination_video_key = (destination_prefix + "/" + filename)

            s3.copy_object(
                Bucket=bucket,
                CopySource={
                    "Bucket": bucket, 
                    "Key": source_key
                },
                Key=destination_video_key
            )

        # Store the created S3 locations for DynamoDB metadata.
        organized_species.append({
            "species": species_name,
            "destination_prefix": (destination_prefix),
            "video_key": (destination_video_key),
            "frame_keys": copied_frames
        })

        print("Organized detection:", species_name, "Frames:", len(copied_frames))

    return organized_species

# Processes one uploaded MJPEG video from start to finish.
#
# The processing pipeline:
#   1. Download the uploaded MJPEG file from Amazon S3.
#   2. Extract JPEG frames and analyze selected frames with Amazon Rekognition.
#   3. Create a detection summary for the entire video.
#   4. Organize confirmed detections into species-specific folders.
#   5. Attach metadata directly to the MJPEG video and extracted frames.
#   6. Store the processing status and detailed metadata in DynamoDB.
def process_mjpeg_record(record):
    processing_start_time = time.time()
    # Read the source video information from the S3 event.
    bucket = record["s3"]["bucket"]["name"]
    source_key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
    
    # Build the local and S3 paths used during processing.
    filename = os.path.basename(source_key)
    video_name = os.path.splitext(filename)[0]
    local_mjpeg_path = os.path.join("/tmp", filename)
    frame_output_prefix = ("frames/" + video_name)

    # Load the user-configurable processing settings.
    settings = load_settings(bucket)

    # Mark the video as being processed.
    save_processing_status(
        source_key,
        "PROCESSING",
        filename=filename,
        bucket=bucket,
        started_at=int(processing_start_time)
    )

    # Skip processing when it has been disabled in the settings.
    if not settings["enabled"]:
        save_processing_status(
            source_key,
            "SKIPPED",
            filename=filename,
            bucket=bucket,
            reason="Processing disabled in settings"
        )
        print("Processing disabled in settings")
        return {"source": source_key, "processing_enabled": False}

    try:
        print("Bucket:", bucket)
        print("Source key:", source_key)
        print("Downloading to:", local_mjpeg_path)

        # Download the uploaded MJPEG file to Lambda's temporary storage.
        s3.download_file(bucket, source_key, local_mjpeg_path)
        source_size = os.path.getsize(local_mjpeg_path)
        print("Downloaded file size:", source_size)

        # Step 1: Extract JPEG frames from the MJPEG file and analyze
        # the configured subset with Amazon Rekognition.
        processing_result = (
            extract_upload_and_analyze_frames(
                local_mjpeg_path,
                bucket,
                source_key,
                frame_output_prefix,
                settings
            )
        )

        # Step 2: Combine all analyzed frames into a single
        # video-level detection summary.
        detection_summary = (create_detection_summary(processing_result["analyzed_frames"], settings))

        # Step 3: Copy confirmed detections into species-specific
        # folders for easier browsing.
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

        processing_duration_ms = int((time.time() - processing_start_time) * 1000)

        update_video_metadata(
            bucket,
            source_key,
            processing_result,
            detection_summary,
            processing_duration_ms
        )

        # Update the metadata of any MJPEG copies that were placed
        # into species-specific folders.
        for organized_detection in organized_detections:
            copied_video_key = organized_detection["video_key"]

            if copied_video_key:
                update_video_metadata(
                    bucket,
                    copied_video_key,
                    processing_result,
                    detection_summary,
                    processing_duration_ms
                )

        # Display a processing summary in the Lambda logs.
        print("Extracted frames:", processing_result["frame_count"])
        print("Analyzed frames:", processing_result[ "analyzed_frame_count"])
        print("Target species detected:", detection_summary["target_species_detected"])
        print("Detected target species:", detection_summary["detected_target_species"])
        print("Processing duration ms:", processing_duration_ms)

        # Convert the processing results into DynamoDB-compatible metadata.
        database_metadata = create_database_metadata(
            source_size,
            processing_duration_ms,
            processing_result,
            detection_summary,
            organized_detections
        )

        # Mark the video as successfully processed.
        save_processing_status(
            source_key,
            "COMPLETED",
            filename=filename,
            bucket=bucket,
            completed_at=int(time.time()),
            **database_metadata
        )

        return {
            "source": source_key,
            "frame_count": (processing_result["frame_count"]),
            "analyzed_frame_count": (processing_result["analyzed_frame_count"]),
            "target_species_detected": (detection_summary["target_species_detected"]),
            "detected_target_species": (detection_summary["detected_target_species"])
        }

    except Exception as error:
        # Store the failure information before allowing Lambda
        # to retry the message through Amazon SQS.
        save_processing_status(
            source_key,
            "FAILED",
            filename=filename,
            bucket=bucket,
            failed_at=int(time.time()),
            error=str(error)
        )
        raise

    finally:
        # Always remove the temporary MJPEG file from Lambda storage,
        # regardless of whether processing succeeded or failed.
        if os.path.exists(local_mjpeg_path):
            os.remove(local_mjpeg_path)


# AWS Lambda entry point.
#
# Each invocation may contain one or more SQS messages.
# Every SQS message contains one S3 event notification, which
# is processed one uploaded MJPEG file at a time.
def lambda_handler(event, context):
    # Collect a summary of every processed MJPEG file.
    processed_files = []

    # Process every SQS message received in this invocation.
    for sqs_record in event.get("Records", []):
        try:
            # Decode the embedded S3 event notification.
            s3_event = json.loads(sqs_record["body"])
            # Process every uploaded MJPEG file referenced by the S3 event.
            for s3_record in s3_event.get("Records", []):
                processed_file = (process_mjpeg_record(s3_record))
                processed_files.append(processed_file)

        except Exception as error:
            print("MJPEG processing failed:", repr(error))
            # Mark the invocation as failed so AWS can retry it.
            raise
    # Return a processing summary for this Lambda invocation.
    return {"statusCode": 200, "processed_files": processed_files}