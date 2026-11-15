# Two private buckets. The evidence bucket reproduces what Backblaze B2 does
# today for backend/core/storage.py: CORS for presigned PUT/GET from the
# frontend, a temporary uploads/ area that expires, and versioning.

locals {
  evidence_bucket_arn = "arn:aws:s3:::${var.evidence_bucket_name}"
  frontend_bucket_arn = "arn:aws:s3:::${var.frontend_bucket_name}"
}

resource "aws_s3_bucket" "evidence" {
  #checkov:skip=CKV_AWS_18:Access logs need a separate log bucket; out of scope for this design
  #checkov:skip=CKV_AWS_144:Cross-region replication doubles storage cost; photos are evidence, not critical records
  #checkov:skip=CKV_AWS_145:SSE-S3 (AES256) encrypts at rest without a paid customer-managed KMS key
  #checkov:skip=CKV2_AWS_62:No consumer for bucket events
  bucket = var.evidence_bucket_name
}

resource "aws_s3_bucket" "frontend" {
  #checkov:skip=CKV_AWS_18:Access logs need a separate log bucket; out of scope for this design
  #checkov:skip=CKV_AWS_144:Cross-region replication doubles storage cost; photos are evidence, not critical records
  #checkov:skip=CKV_AWS_145:SSE-S3 (AES256) encrypts at rest without a paid customer-managed KMS key
  #checkov:skip=CKV2_AWS_62:No consumer for bucket events
  bucket = var.frontend_bucket_name
}

resource "aws_s3_bucket_public_access_block" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_ownership_controls" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Same rule as the Backblaze bucket (.tools/scripts/b2_cors.py).
resource "aws_s3_bucket_cors_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  cors_rule {
    allowed_origins = var.cors_allowed_origins
    allowed_methods = ["PUT", "GET"]
    allowed_headers = ["content-type"]
    expose_headers  = ["etag"]
    max_age_seconds = 3600
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  # Uploads never confirmed by the backend.
  rule {
    id     = "expire-uploads"
    status = "Enabled"

    filter {
      prefix = "uploads/"
    }

    expiration {
      days = 1
    }
  }

  # Deleting a photo must free the space: old versions and delete markers go too.
  rule {
    id     = "expire-noncurrent"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 1
    }

    expiration {
      expired_object_delete_marker = true
    }
  }

  rule {
    id     = "abort-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  depends_on = [aws_s3_bucket_versioning.evidence]
}

# Old versions of the frontend files are kept 30 days, enough to roll back.
resource "aws_s3_bucket_lifecycle_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    id     = "expire-noncurrent"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  rule {
    id     = "abort-multipart"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  depends_on = [aws_s3_bucket_versioning.frontend]
}

resource "aws_s3_bucket_policy" "evidence" {
  bucket = aws_s3_bucket.evidence.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [local.evidence_bucket_arn, "${local.evidence_bucket_arn}/*"]
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.evidence]
}
