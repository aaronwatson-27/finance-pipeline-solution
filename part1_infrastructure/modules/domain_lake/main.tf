# File to set up buckets for each data layer
locals {
  data_layers = ["landing", "curated"]

  bucket_names = {
    for layer in local.data_layers :
    layer => "${var.bucket_prefix}${var.domain}-data-${layer}"
  }
}

# Create each bucket from the list of bucket names, providing name and tags
resource "aws_s3_bucket" "this" {
  for_each = local.bucket_names

  bucket = each.value

  tags = merge(var.tags, {
    Domain = var.domain
    Layer  = each.key
  })
}

# Enable SSE-S3 encryption on all buckets
resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# Block public access on all buckets
resource "aws_s3_bucket_public_access_block" "this" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable versioning on buckets
resource "aws_s3_bucket_versioning" "this" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Bucket lifecycle for landing - currently applies to all landing objects
resource "aws_s3_bucket_lifecycle_configuration" "landing" {
  bucket = aws_s3_bucket.this["landing"].id

  depends_on = [aws_s3_bucket_versioning.this]

  rule {
    id     = "expire-landing-objects"
    status = "Enabled"
    # No filter, applies to all objects
    filter {}

    expiration {
      days = var.landing_expiration_days
    }

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_expiration_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# Retain curated, but expire old versions from curated after a set amount of expiration days
resource "aws_s3_bucket_lifecycle_configuration" "curated" {
  bucket = aws_s3_bucket.this["curated"].id

  depends_on = [aws_s3_bucket_versioning.this]

  rule {
    id     = "expire-old-versions-from-curated"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_expiration_days
    }
  }
}
