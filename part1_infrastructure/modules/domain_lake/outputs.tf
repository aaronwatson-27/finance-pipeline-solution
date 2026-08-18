# Generalised outputs: list of bucket names and ARNs
output "bucket_names" {
  description = "Map of data_layer name to bucket name."
  value       = { for k, v in aws_s3_bucket.this : k => v.id }
}

output "bucket_arns" {
  description = "Map of data_layer name to bucket ARN."
  value       = { for k, v in aws_s3_bucket.this : k => v.arn }
}
