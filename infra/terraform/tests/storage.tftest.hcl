mock_provider "aws" {}

run "buckets_are_private" {
  command = plan

  module {
    source = "./modules/storage"
  }

  variables {
    evidence_bucket_name = "ev-test"
    frontend_bucket_name = "fe-test"
    cors_allowed_origins = ["https://example.test"]
  }

  assert {
    condition = alltrue([
      for block in [aws_s3_bucket_public_access_block.evidence, aws_s3_bucket_public_access_block.frontend] :
      block.block_public_acls && block.block_public_policy && block.ignore_public_acls && block.restrict_public_buckets
    ])
    error_message = "Both buckets must block every kind of public access."
  }

  assert {
    condition = (
      aws_s3_bucket_versioning.evidence.versioning_configuration[0].status == "Enabled" &&
      aws_s3_bucket_versioning.frontend.versioning_configuration[0].status == "Enabled"
    )
    error_message = "Both buckets must keep versions."
  }

  assert {
    condition = (
      aws_s3_bucket_ownership_controls.evidence.rule[0].object_ownership == "BucketOwnerEnforced" &&
      aws_s3_bucket_ownership_controls.frontend.rule[0].object_ownership == "BucketOwnerEnforced"
    )
    error_message = "Both buckets must disable ACLs (BucketOwnerEnforced)."
  }

  assert {
    condition = alltrue([
      for config in [aws_s3_bucket_server_side_encryption_configuration.evidence, aws_s3_bucket_server_side_encryption_configuration.frontend] :
      one(one(config.rule).apply_server_side_encryption_by_default).sse_algorithm == "AES256"
    ])
    error_message = "Both buckets must encrypt objects at rest."
  }

  assert {
    condition = (
      length(aws_s3_bucket_cors_configuration.evidence.cors_rule) == 1 &&
      toset(one(aws_s3_bucket_cors_configuration.evidence.cors_rule).allowed_methods) == toset(["PUT", "GET"]) &&
      toset(one(aws_s3_bucket_cors_configuration.evidence.cors_rule).allowed_origins) == toset(["https://example.test"])
    )
    error_message = "Evidence CORS must allow only PUT and GET, only from the given origins."
  }

  assert {
    condition = anytrue([
      for rule in aws_s3_bucket_lifecycle_configuration.evidence.rule :
      rule.status == "Enabled" && try(rule.filter[0].prefix, "") == "uploads/" && try(rule.expiration[0].days, 0) == 1
    ])
    error_message = "Unconfirmed uploads (uploads/) must expire after one day."
  }

  assert {
    condition = anytrue([
      for statement in jsondecode(aws_s3_bucket_policy.evidence.policy).Statement :
      statement.Effect == "Deny" && try(statement.Condition.Bool["aws:SecureTransport"], "") == "false"
    ])
    error_message = "The evidence bucket must deny requests without TLS."
  }

  assert {
    condition     = output.evidence_bucket_arn == "arn:aws:s3:::ev-test"
    error_message = "The evidence bucket ARN must be built from its name."
  }

  assert {
    condition = anytrue([
      for rule in aws_s3_bucket_lifecycle_configuration.frontend.rule :
      rule.status == "Enabled" && try(rule.noncurrent_version_expiration[0].noncurrent_days, 0) == 30
    ])
    error_message = "Old frontend versions must expire after 30 days."
  }
}
