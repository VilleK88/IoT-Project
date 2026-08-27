import os

# Name of the S3 bucket used for wildlife camera uploads.
S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]

# Directory-like prefix used for newly uploaded, unprocessed events.
S3_UPLOADS_PREFIX = os.environ["S3_UPLOADS_PREFIX"]

# How long a generated presigned upload URL remains valid, in seconds.
PRESIGNED_URL_EXPIRATION = int(os.environ.get("PRESIGNED_URL_EXPIRATION", "43200"))