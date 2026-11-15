variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "frontend_bucket_id" {
  description = "Frontend bucket (default origin)."
  type        = string
}

variable "frontend_bucket_arn" {
  description = "ARN of the frontend bucket."
  type        = string
}

variable "frontend_bucket_regional_domain_name" {
  description = "Regional domain name of the frontend bucket."
  type        = string
}

variable "api_origin_domain_name" {
  description = "Public DNS name of the app server."
  type        = string
}

variable "api_path_patterns" {
  description = "Paths served by the app server instead of the frontend bucket."
  type        = list(string)
  default     = ["/api/*", "/admin/*", "/static/*", "/docs", "/openapi.json"]
}
