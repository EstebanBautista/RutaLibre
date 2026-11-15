output "evidence_bucket_name" {
  description = "Name of the evidence photos bucket."
  value       = aws_s3_bucket.evidence.bucket
}

output "evidence_bucket_arn" {
  description = "ARN of the evidence photos bucket, built from its name so it is known at plan time."
  value       = local.evidence_bucket_arn
}

output "frontend_bucket_name" {
  description = "Name of the frontend bucket."
  value       = aws_s3_bucket.frontend.bucket
}

output "frontend_bucket_id" {
  description = "ID of the frontend bucket."
  value       = aws_s3_bucket.frontend.id
}

output "frontend_bucket_arn" {
  description = "ARN of the frontend bucket, built from its name so it is known at plan time."
  value       = local.frontend_bucket_arn
}

output "frontend_bucket_regional_domain_name" {
  description = "Regional domain name of the frontend bucket, used as the CloudFront origin."
  value       = aws_s3_bucket.frontend.bucket_regional_domain_name
}
