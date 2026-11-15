output "vpc_id" {
  description = "ID of the VPC."
  value       = module.network.vpc_id
}

output "evidence_bucket_name" {
  description = "Name of the evidence photos bucket."
  value       = module.storage.evidence_bucket_name
}

output "frontend_bucket_name" {
  description = "Name of the frontend bucket."
  value       = module.storage.frontend_bucket_name
}

output "database_address" {
  description = "Host name of the database (reachable only from the app server)."
  value       = module.database.address
}

output "instance_id" {
  description = "ID of the app server, for Session Manager."
  value       = module.compute.instance_id
}
