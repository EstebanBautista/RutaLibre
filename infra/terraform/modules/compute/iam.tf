# The instance role. Each inline policy has one purpose, and each lists only
# the calls the code makes.

data "aws_caller_identity" "current" {}

resource "aws_iam_role" "app" {
  name = "${var.name_prefix}-app"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "app" {
  name = "${var.name_prefix}-app"
  role = aws_iam_role.app.name
}

# Exactly what backend/core/storage.py calls: presigned PUT and GET,
# head_object, copy_object (GetObject on the source, PutObject on the target),
# list_object_versions and delete_objects by VersionId. head_bucket needs
# ListBucket.
resource "aws_iam_role_policy" "evidence_photos" {
  name = "evidence-photos"
  role = aws_iam_role.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "PhotoObjects"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:DeleteObjectVersion"]
        Resource = "${var.evidence_bucket_arn}/*"
      },
      {
        Sid      = "ListForChecksAndCleanup"
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:ListBucketVersions"]
        Resource = var.evidence_bucket_arn
      }
    ]
  })
}

# GetParametersByPath is authorized against the requested path itself, and
# GetParameters against each parameter, so both ARNs are needed.
# SecureString parameters use the AWS managed key aws/ssm. Its key policy
# already lets Parameter Store decrypt for any principal of the account that
# may read the parameter, so no kms:Decrypt statement is needed.
resource "aws_iam_role_policy" "read_config" {
  name = "read-config"
  role = aws_iam_role.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["ssm:GetParametersByPath", "ssm:GetParameters"]
        Resource = [
          "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter${var.config_parameter_path}",
          "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter${var.config_parameter_path}/*",
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "read_db_secret" {
  name = "read-db-secret"
  role = aws_iam_role.app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "secretsmanager:GetSecretValue"
        Resource = var.db_secret_arn
      }
    ]
  })
}

# Session Manager instead of SSH: no key pair, no port 22.
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.app.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
