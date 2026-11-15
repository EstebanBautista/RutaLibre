variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "region" {
  description = "AWS region, used to build ARNs and for the AWS CLI on the instance."
  type        = string
}

variable "vpc_id" {
  description = "VPC of the app security group."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR of the VPC: the only destination allowed for database traffic."
  type        = string
}

variable "subnet_id" {
  description = "Public subnet for the instance."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type (x86, so every Python wheel exists)."
  type        = string
  default     = "t3.micro"
}

variable "evidence_bucket_name" {
  description = "Bucket the backend signs photo URLs for."
  type        = string
}

variable "evidence_bucket_arn" {
  description = "ARN of that bucket."
  type        = string
}

variable "db_secret_arn" {
  description = "Secrets Manager secret with the database master password."
  type        = string
}

variable "db_address" {
  description = "Database host name."
  type        = string
}

variable "db_port" {
  description = "Database port."
  type        = number
}

variable "db_name" {
  description = "Database name."
  type        = string
}

variable "config_parameter_path" {
  description = "Parameter Store path with the app settings (DJANGO_SECRET_KEY, JWT_SIGNING_KEY, ...)."
  type        = string
  default     = "/rutalibre/prod"
}

variable "repo_url" {
  description = "Git repository the instance deploys."
  type        = string
}

variable "app_git_ref" {
  description = "Branch or tag to deploy."
  type        = string
  default     = "main"
}

variable "public_host" {
  description = "Host name of the CloudFront distribution. nginx and Django accept only this name."
  type        = string
}
