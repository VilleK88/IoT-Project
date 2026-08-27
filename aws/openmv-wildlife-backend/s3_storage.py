import boto3
from config import S3_UPLOADS_PREFIX

s3 = boto3.client("s3")

def get_event_state(bucket, camera_id, event_id):
    """
    Inspect an event folder and return which sensor files exist.
    """
    event_prefix = build_event_prefix(camera_id, event_id)

    pag_key = f"{event_prefix}/pag.mjpeg"
    lepton_key = f"{event_prefix}/lepton.mjpeg"
    pag_exists = object_exists(bucket, pag_key)
    lepton_exists = object_exists(bucket, lepton_key)
    return {
        "event_prefix": event_prefix,
        "pag_key": pag_key,
        "lepton_key": lepton_key,
        "pag_exists": pag_exists,
        "lepton_exists": lepton_exists,
        "complete": pag_exists and lepton_exists
    }

def build_event_prefix(camera_id, event_id):
    """Build the common S3 prefix for one camera event."""
    return (S3_UPLOADS_PREFIX + "{}/event_{:05d}").format(camera_id, int(event_id))

def object_exists(bucket, key):
    """Check whether an S3 object exists."""
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except s3.exceptions.ClientError as err:
        err_code = err.response["Error"]["Code"]
        if err_code in ("404", "NoSuchKey"):
            return False
        raise

def load_event_file(bucket, key):
    """
    Download an event recording from S3 and return
    its contents as bytes.
    """
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()

def move_object(bucket, source_key, destination_key):
    """
    Move an S3 object by copying it to a new key
    and deleting the original.
    """

    # S3 does not provide a direct rename operation.
    s3.copy_object(
        Bucket=bucket,
        CopySource={
            "Bucket": bucket,
            "Key": source_key
        },
        Key=destination_key
    )

    # Delete the original only after the copy succeeds.
    s3.delete_object(Bucket=bucket, Key=source_key)

def build_animal_frame_key(target, camera_id, event_id, frame_number):
    """
    Build the S3 key for a detected target frame.

    Example:
    animals/person/camera_001/event_00042/frame_00005.jpg
    """

    return (
        S3_UPLOADS_PREFIX
        + "animals/"
        + target.lower()
        + "/{}/event_{:05d}/frame_{:05d}.jpg"
    ).format(camera_id, int(event_id), int(frame_number)
    )

def save_target_frame(bucket, target, camera_id, event_id, frame_number, frame):
    """Save one detected JPEG frame into its target directory."""

    object_key = build_animal_frame_key(
        target,
        camera_id,
        event_id,
        frame_number
    )

    s3.put_object(
        Bucket=bucket,
        Key=object_key,
        Body=frame,
        ContentType="image/jpeg"
    )

    return object_key

def delete_event(bucket, camera_id, event_id):
    """Delete all objectst belonging to one rejected event"""

    event_prefix = (
        S3_UPLOADS_PREFIX + "{}/event_{:05d}/"
        ).format(camera_id, int(event_id))

    response = s3.list_objects_v2(Bucket=bucket, Prefix=event_prefix)

    objects = response.get("Contents", [])

    if objects:
        s3.delete_objects(
            Bucket=bucket,
            Delete={
                "Objects": [
                    {"Key": obj["Key"]}
                    for obj in objects
                ]
            }
        )