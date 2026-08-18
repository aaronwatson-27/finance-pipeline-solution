variable "region" {
  description = "AWS region."
  type        = string
  default     = "ap-southeast-2"
}

variable "aws_profile" {
  description = "Named AWS CLI profile used for credentials."
  type        = string
}

variable "bucket_prefix" {
  description = "Prefix for global S3 bucket-name uniqueness."
  type        = string
}

variable "domains" {
  description = "Data domains to provision. Add a key to add a domain."
  type = map(object({
    landing_expiration_days = optional(number, 30)
  }))
}

variable "analyst_domain" {
  description = "Domain whose curated layer the analyst role can read."
  type        = string
  default     = "finance"
}

variable "role_trust" {
  description = "Principals permitted to assume each role, keyed by role name."
  type        = map(list(string))
}
