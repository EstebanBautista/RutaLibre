variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "vpc_id" {
  description = "VPC of the database security group."
  type        = string
}

variable "subnet_ids" {
  description = "Private subnets, in two availability zones."
  type        = list(string)
}

variable "app_security_group_id" {
  description = "Security group of the app server: the only source allowed to connect."
  type        = string
}

variable "instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage" {
  description = "Storage in GB."
  type        = number
  default     = 20
}

variable "engine_version" {
  description = "PostgreSQL major version."
  type        = string
  default     = "17"
}

variable "db_name" {
  description = "Name of the database Django uses."
  type        = string
  default     = "rutalibre"
}

variable "username" {
  description = "Master user name. Its password is generated and kept by RDS in Secrets Manager."
  type        = string
  default     = "rutalibre"
}
