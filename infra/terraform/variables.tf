variable "project" {
  description = "Project name, first part of every resource name."
  type        = string
  default     = "rutalibre"
}

variable "environment" {
  description = "Environment name, second part of every resource name."
  type        = string
  default     = "prod"
}

variable "region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "availability_zones" {
  description = "The two availability zones used by every subnet."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC."
  type        = string
  default     = "10.20.0.0/16"
}
