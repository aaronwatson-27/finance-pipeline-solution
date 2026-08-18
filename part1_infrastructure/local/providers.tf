terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region

  # LocalStack ignores credentials, but AWS SDK requires them.
  access_key = "test"
  secret_key = "test"

  # LocalStack serves S3 on a single endpoint, so bucket names must go in
  # the path rather than the hostname.
  s3_use_path_style = true

  # These calls hit real AWS metadata endpoints that LocalStack does not serve.
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    s3  = var.localstack_endpoint
    iam = var.localstack_endpoint
    sts = var.localstack_endpoint
  }

  default_tags {
    tags = {
      Project     = "finance-data-platform"
      Environment = "local"
      ManagedBy   = "terraform"
    }
  }
}
