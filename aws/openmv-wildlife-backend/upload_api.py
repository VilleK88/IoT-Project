import boto3
from config import(S3_BUCKET_NAME, S3_UPLOADS_PREFIX, PRESIGNED_URL_EXPIRATION)

# Create an S3 client using the Lambda execution role.
s3 = boto3.client("s3")

def generate_upload_url(camera_id, event_id, sensor):
    """
    Generate a presigned URL for uploading one MJPEG
    recording directly from OpenMV to S3.
    """

    # Both PAG and Lepton recordings from the same event
    # are placed inside the same event directory.
    #
    # Example:
    #
    # unprocessed/camera_01/event_00042/pag.mjpeg
    # unprocessed/camera_01/event_00042/lepton.mjpeg
    object_key = (
        S3_UPLOADS_PREFIX + "{}/event_{:05d}/{}.mjpeg"
    ).format(camera_id, int(event_id), sensor)

    # Generate a temporary PUT URL.
    #
    # The OpenMV device can upload directly to S3 without
    # having permanent AWS credentials on the device.
    upload_url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": S3_BUCKET_NAME,
            "Key": object_key,
        },
        ExpiresIn=PRESIGNED_URL_EXPIRATION,
        HttpMethod="PUT",
    )

    return upload_url, object_key