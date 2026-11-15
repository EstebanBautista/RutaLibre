# One EC2 instance runs both Python services behind nginx. It has no SSH key
# and no port 22; only CloudFront can reach it, on port 80.

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

resource "aws_security_group" "app" {
  name        = "${var.name_prefix}-app"
  description = "App server: HTTP from CloudFront only"
  vpc_id      = var.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "http_from_cloudfront" {
  security_group_id = aws_security_group.app.id
  description       = "HTTP from CloudFront edge locations"
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront.id
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
}

# HTTPS out: packages, git, and the AWS APIs (S3, SSM, Secrets Manager).
resource "aws_vpc_security_group_egress_rule" "https_out" {
  security_group_id = aws_security_group.app.id
  description       = "HTTPS to the internet and AWS APIs"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_vpc_security_group_egress_rule" "postgres_in_vpc" {
  security_group_id = aws_security_group.app.id
  description       = "PostgreSQL inside the VPC"
  cidr_ipv4         = var.vpc_cidr
  ip_protocol       = "tcp"
  from_port         = 5432
  to_port           = 5432
}

locals {
  # Non-secret settings for bootstrap.sh. Secrets are read on the instance
  # from Parameter Store and Secrets Manager, never passed here.
  bootstrap_env = {
    AWS_REGION            = var.region
    CONFIG_PARAMETER_PATH = var.config_parameter_path
    DB_SECRET_ARN         = var.db_secret_arn
    DB_HOST               = var.db_address
    DB_PORT               = tostring(var.db_port)
    DB_NAME               = var.db_name
    S3_BUCKET             = var.evidence_bucket_name
    REPO_URL              = var.repo_url
    APP_GIT_REF           = var.app_git_ref
  }

  user_data = join("\n", concat(
    ["#!/usr/bin/env bash"],
    [for name, value in local.bootstrap_env : "export ${name}=${jsonencode(value)}"],
    [file("${path.module}/files/bootstrap.sh")],
  ))
}

resource "aws_instance" "app" {
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.app.id]
  iam_instance_profile        = aws_iam_instance_profile.app.name
  associate_public_ip_address = false
  monitoring                  = false
  ebs_optimized               = true

  user_data                   = local.user_data
  user_data_replace_on_change = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = 20
    encrypted   = true
  }

  tags = { Name = "${var.name_prefix}-app" }
}

resource "aws_eip" "app" {
  domain   = "vpc"
  instance = aws_instance.app.id

  tags = { Name = "${var.name_prefix}-app" }
}
