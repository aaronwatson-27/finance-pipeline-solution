# Create an instance of the module "domain_lake" for each of the domains, e.g., finance, sales
# in the variables. This sets up landing/curated buckets and their configurations for each domain.
module "domain_lake" {
  source   = "../modules/domain_lake"
  for_each = var.domains

  domain                  = each.key
  bucket_prefix           = var.bucket_prefix
  landing_expiration_days = each.value.landing_expiration_days
}

locals {
  # Flatten every bucket ARN across every domain, so the engineer policy
  # picks up new domains automatically.
  all_bucket_arns = flatten([
    for domain, lake in module.domain_lake : values(lake.bucket_arns)
  ])
  # Data engineer IAM policy defines read/write access to all bucket arns
  all_object_arns = [for arn in local.all_bucket_arns : "${arn}/*"]
  # Analyst IAM policy defines read from the analyst_domain's curated bucket only
  analyst_bucket_arn = module.domain_lake[var.analyst_domain].bucket_arns["curated"]
}

# Trust policy, shared by both roles - allows trusted_principal_arns to assume both roles
# One trust policy per role. Both hold the same principal locally.
data "aws_iam_policy_document" "assume_role" {
  for_each = var.role_trust

  statement {
    sid     = "AllowAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = each.value
    }
  }
}


# Data_engineer: full access across all domains and buckets

data "aws_iam_policy_document" "data_engineer" {
  statement {
    sid       = "ListAllDomainBuckets"
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = local.all_bucket_arns
  }

  statement {
    sid    = "ReadWriteAllDomainObjects"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:PutObject",
      "s3:DeleteObject",
    ]
    resources = local.all_object_arns
  }
}

resource "aws_iam_role" "data_engineer" {
  name               = "data_engineer"
  assume_role_policy = data.aws_iam_policy_document.assume_role["data_engineer"].json
}
resource "aws_iam_role_policy" "data_engineer" {
  name   = "data-engineer-s3-access"
  role   = aws_iam_role.data_engineer.id
  policy = data.aws_iam_policy_document.data_engineer.json
}

# finance_analyst: only read access on the finance curated layer, nothing else.

data "aws_iam_policy_document" "finance_analyst" {
  statement {
    sid       = "ListCuratedBucket"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [local.analyst_bucket_arn]
  }

  statement {
    sid       = "ReadCuratedObjects"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${local.analyst_bucket_arn}/*"]
  }
}

resource "aws_iam_role" "finance_analyst" {
  name               = "finance_analyst"
  assume_role_policy = data.aws_iam_policy_document.assume_role["finance_analyst"].json
}

resource "aws_iam_role_policy" "finance_analyst" {
  name   = "finance-analyst-read-only"
  role   = aws_iam_role.finance_analyst.id
  policy = data.aws_iam_policy_document.finance_analyst.json
}
