output "security_group_id" {
  description = "Security group of the app server (the database allows only this group)."
  value       = aws_security_group.app.id
}

output "public_dns" {
  description = "Public DNS name of the Elastic IP, used as the CloudFront API origin."
  value       = aws_eip.app.public_dns
}

output "instance_id" {
  description = "ID of the instance (for Session Manager)."
  value       = aws_instance.app.id
}

output "role_name" {
  description = "Name of the instance role."
  value       = aws_iam_role.app.name
}
