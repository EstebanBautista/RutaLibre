variable "evidence_bucket_name" {
  description = "Bucket for the delivery photos (today: Backblaze B2 bucket of the same name)."
  type        = string
}

variable "frontend_bucket_name" {
  description = "Bucket for the static frontend files, served only through CloudFront."
  type        = string
}

variable "cors_allowed_origins" {
  description = "Origins allowed to PUT and GET photos with presigned URLs."
  type        = list(string)

  validation {
    condition     = length(var.cors_allowed_origins) > 0 && alltrue([for origin in var.cors_allowed_origins : origin != "*"])
    error_message = "List at least one origin, and never \"*\"."
  }
}
