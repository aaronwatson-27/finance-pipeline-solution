# Expected input variables for bucket setup
variable "domain" {
  description = "Domain name, used as the bucket name prefix (e.g. finance, sales)."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.domain))
    error_message = "Domain can only be lowercase letters, numbers, hyphens."
  }
}

variable "bucket_prefix" {
  description = "Uniqueness prefix. Empty for LocalStack but for AWS, likely set it to something like company-{env}."
  type        = string
  default     = ""
}

variable "landing_expiration_days" {
  description = "Number of days before raw landing objects expire."
  type        = number
  default     = 30
}

variable "noncurrent_version_expiration_days" {
  description = "Number of days before superseded object versions are deleted."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags for all resources."
  type        = map(string)
  default     = {}
}
