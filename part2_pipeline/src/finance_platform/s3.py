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
