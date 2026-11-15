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
