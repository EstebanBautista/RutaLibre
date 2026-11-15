output "address" {
  description = "Host name of the database."
  value       = aws_db_instance.this.address
}

output "port" {
  description = "Port of the database."
  value       = aws_db_instance.this.port
}

output "db_name" {
  description = "Name of the database."
  value       = aws_db_instance.this.db_name
}

output "master_user_secret_arn" {
  description = "ARN of the Secrets Manager secret that holds the master password."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}

output "security_group_id" {
  description = "Security group of the database."
  value       = aws_security_group.db.id
}

output "subnet_ids" {
  description = "Subnets of the database subnet group."
  value       = aws_db_subnet_group.this.subnet_ids
}

output "allowed_security_group_id" {
  description = "The only security group allowed to connect on port 5432."
  value       = aws_vpc_security_group_ingress_rule.from_app.referenced_security_group_id
}
