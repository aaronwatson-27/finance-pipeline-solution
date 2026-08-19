# S3 functions to create client and other read, write, upload functions.

import logging

import boto3
from botocore.config import Config

from finance_platform.config import Settings

logger = logging.getLogger(__name__)


def s3_client(settings: Settings):
    """Build an S3 client for the configured environment.

    If localstack_endpoint is set, client targets LocalStack and uses placeholder credentials
    (boto3 requires populated credentials). Note that path-style addressing specifically required
    for LocalStack because it serves every bucket from a single host.

    Otherwise the client targets real AWS.
    """
    if settings.localstack_endpoint:
        return boto3.client(
            "s3",
            endpoint_url=settings.localstack_endpoint,
            region_name=settings.aws_region,
            aws_access_key_id="test",
            aws_secret_access_key="test",
            config=Config(s3={"addressing_style": "path"}),
        )
    return boto3.client("s3", region_name=settings.aws_region)


# Writes csv straight to S3
def write_csv(bucket: str, key: str, body: str, settings: Settings) -> str:
    """Write CSV text to S3. Returns the key."""
    s3_client(settings).put_object(
        Bucket=bucket, Key=key, Body=body.encode("utf-8"), ContentType="text/csv"
    )
    logger.info("Wrote %d bytes to s3://%s/%s", len(body), bucket, key)
    return key


# Reads S3 object based on key and returns string
def read_text(bucket: str, key: str, settings: Settings) -> str:
    response = s3_client(settings).get_object(Bucket=bucket, Key=key)
    return response["Body"].read().decode("utf-8")


# Uploads file to S3 from path
def upload_file(bucket: str, key: str, path: str, settings: Settings) -> str:
    s3_client(settings).upload_file(path, bucket, key)
    return key


def list_keys(bucket: str, prefix: str, settings: Settings) -> list[str]:
    """List every key under a prefix."""
    client = s3_client(settings)
    keys: list[str] = []

    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys.extend(obj["Key"] for obj in page.get("Contents", []))

    return keys


def delete_prefix(bucket: str, prefix: str, settings: Settings) -> int:
    """Delete every object under a prefix. Returns the count deleted.

    This is used to make writes idempotent: a partition is cleared before
    being rewritten, so a re-run replaces the partition rather than leaving
    orphaned files from a previous run.
    """
    keys = list_keys(bucket, prefix, settings)
    if not keys:
        return 0

    client = s3_client(settings)
    # delete_objects accepts a maximum of 1000 keys per call.
    for i in range(0, len(keys), 1000):
        client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": k} for k in keys[i : i + 1000]]},
        )

    logger.info("Deleted %d objects under s3://%s/%s", len(keys), bucket, prefix)
    return len(keys)
