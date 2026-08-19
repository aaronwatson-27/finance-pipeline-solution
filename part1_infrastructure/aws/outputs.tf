# Expected outputs: list of created bucket names for each domain and role ARNs
output "bucket_names" {
  description = "All provisioned buckets, keyed by domain then layer."
  value       = { for domain, lake in module.domain_lake : domain => lake.bucket_names }
}

output "role_arns" {
  value = {
    data_engineer   = aws_iam_role.data_engineer.arn
    finance_analyst = aws_iam_role.finance_analyst.arn
  }
}
