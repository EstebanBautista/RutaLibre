variable "name_prefix" {
  description = "Prefix for resource names, e.g. rutalibre-prod."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC."
  type        = string
}

variable "availability_zones" {
  description = "Exactly two availability zones. RDS needs subnets in two zones."
  type        = list(string)

  validation {
    condition     = length(var.availability_zones) == 2
    error_message = "Use exactly two availability zones."
  }
}

variable "public_subnet_cidrs" {
  description = "One CIDR per availability zone, for the subnets with a route to the internet."
  type        = list(string)

  validation {
    condition     = length(var.public_subnet_cidrs) == 2
    error_message = "Use one public subnet CIDR per availability zone (two)."
  }
}

variable "private_subnet_cidrs" {
  description = "One CIDR per availability zone, for the subnets without a route to the internet."
  type        = list(string)

  validation {
    condition     = length(var.private_subnet_cidrs) == 2
    error_message = "Use one private subnet CIDR per availability zone (two)."
  }
}
