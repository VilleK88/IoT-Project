import json

VALID_SENSORS = ("pag", "lepton")

def validate_upload_request(camera_id, event_id, sensor):
    """Validate the upload request parameters."""

    # camera_id identifies which physical camera generated the event.
    if camera_id is None:
        return create_error_response("camera_id is required")
    
    # event_id groups PAG and Lepton recordings
    # belonging to the same detection event.
    if event_id is None:
        return create_error_response("event_id is required")
    
    # Only the two supported sensors are accepted.
    if sensor not in VALID_SENSORS:
        return create_error_response("Invalid sensor")
    
    return None

def create_error_response(msg):
    """Create a standard HTTP 400 response."""
    return {"statusCode": 400, "body": json.dumps({"error": msg})}