# Expected input variables
variable "region" {
  description = "AWS region."
  type        = string
  default     = "ap-southeast-2"
}

variable "localstack_endpoint" {
  description = "LocalStack gateway URL."
  type        = string
  default     = "http://localhost:4566"
}

variable "bucket_prefix" {
  description = "Uniqueness prefix. Empty for LocalStack."
  type        = string
  default     = ""
}

variable "domains" {
  description = "Data domains to provision. Each entry creates a landing and a curated bucket."
  type = map(object({
    landing_expiration_days = optional(number, 30)
  }))
}

variable "analyst_domain" {
  description = "Domain whose curated layer the financial analyst role can read."
  type        = string
  default     = "finance"
}

variable "role_trust" {
  description = "Principals permitted to assume each role, keyed by role name."
  type        = map(list(string))
}
