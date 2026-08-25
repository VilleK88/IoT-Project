import json
from s3_event_handler import process_s3_event
from upload_api import generate_upload_url
from validation import validate_upload_request

def lambda_handler(event, context):
    """Route API Gateway and S3 events to the correct logic."""

    # S3 ObjectCreated event.
    if is_s3_event(event):
         return process_s3_event(event)

    # Handle OpenMV presigned upload URL requests.
    return handle_upload_request(event)

def is_s3_event(event):
    """Check whether Lambda was invoked by an S3 event."""
    return (
        "Records" in event and len(event["Records"]) > 0
        and event["Records"][0].get("eventSource") == "aws:s3"
    )

def handle_upload_request(event):
    # Parse the JSON body sent by the OpenMV device.
        body = json.loads(event.get("body") or "{}")
    
        camera_id = body.get("camera_id")
        event_id = body.get("event_id")
        sensor = body.get("sensor")
    
        # Validate the upload request before generating an upload URL.
        validation_error =  validate_upload_request(camera_id, event_id, sensor)
        if validation_error:
            return validation_error
    
        # Generate a presigned S3 PUT URL for exactly one
        # sensor recording belonging to this event.
        upload_url, object_key = generate_upload_url(camera_id, event_id, sensor)
    
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
            },
            "body": json.dumps({
                "upload_url": upload_url,
                "object_key": object_key,
            }),
        }