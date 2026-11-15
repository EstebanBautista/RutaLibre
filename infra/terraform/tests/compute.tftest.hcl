mock_provider "aws" {}

variables {
  name_prefix          = "rutalibre-test"
  region               = "us-east-1"
  vpc_id               = "vpc-test"
  vpc_cidr             = "10.20.0.0/16"
  subnet_id            = "subnet-test"
  evidence_bucket_name = "ev-test"
  evidence_bucket_arn  = "arn:aws:s3:::ev-test"
  db_secret_arn        = "arn:aws:secretsmanager:us-east-1:123456789012:secret:rds-test"
  db_address           = "db.test.internal"
  db_port              = 5432
  db_name              = "rutalibre"
  repo_url             = "https://github.com/example/rutalibre.git"
}

run "instance_is_hardened" {
  command = plan

  module {
    source = "./modules/compute"
  }

  assert {
    condition     = aws_instance.app.instance_type == "t3.micro"
    error_message = "Expected a t3.micro instance."
  }

  assert {
    condition     = aws_instance.app.metadata_options[0].http_tokens == "required"
    error_message = "IMDSv2 must be required."
  }

  assert {
    condition     = aws_instance.app.root_block_device[0].encrypted == true
    error_message = "The root disk must be encrypted."
  }

  assert {
    condition     = aws_instance.app.associate_public_ip_address == false
    error_message = "The instance gets its public address only from the Elastic IP."
  }

  assert {
    condition = (
      aws_vpc_security_group_ingress_rule.http_from_cloudfront.from_port == 80 &&
      aws_vpc_security_group_ingress_rule.http_from_cloudfront.to_port == 80 &&
      aws_vpc_security_group_ingress_rule.http_from_cloudfront.cidr_ipv4 == null &&
      aws_vpc_security_group_ingress_rule.http_from_cloudfront.cidr_ipv6 == null
    )
    error_message = "Port 80 must be open only to CloudFront's prefix list, never to a CIDR."
  }

  assert {
    condition = (
      strcontains(aws_instance.app.user_data, "OnUnitActiveSec=5min") &&
      strcontains(aws_instance.app.user_data, "systemctl enable --now rutalibre-api.service rutalibre-optimizer.service nginx.service rutalibre-env.timer")
    )
    error_message = "The settings (rotated database password) must be refreshed by a timer."
  }
}

run "iam_is_least_privilege" {
  command = plan

  module {
    source = "./modules/compute"
  }

  assert {
    condition     = jsondecode(aws_iam_role.app.assume_role_policy).Statement[0].Principal.Service == "ec2.amazonaws.com"
    error_message = "Only EC2 may assume the app role."
  }

  assert {
    condition = anytrue([
      for statement in jsondecode(aws_iam_role_policy.evidence_photos.policy).Statement :
      statement.Resource == "arn:aws:s3:::ev-test/*" &&
      toset(statement.Action) == toset(["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:DeleteObjectVersion"])
    ])
    error_message = "Object actions must be exactly Put, Get, Delete and DeleteObjectVersion on the bucket's objects."
  }

  assert {
    condition = anytrue([
      for statement in jsondecode(aws_iam_role_policy.evidence_photos.policy).Statement :
      statement.Resource == "arn:aws:s3:::ev-test" &&
      toset(statement.Action) == toset(["s3:ListBucket", "s3:ListBucketVersions"])
    ])
    error_message = "Bucket actions must be exactly ListBucket and ListBucketVersions on the bucket."
  }

  assert {
    condition = (
      length(jsondecode(aws_iam_role_policy.evidence_photos.policy).Statement) == 2 &&
      alltrue([
        for statement in jsondecode(aws_iam_role_policy.evidence_photos.policy).Statement :
        statement.Effect == "Allow" &&
        !contains(flatten([statement.Action]), "*") &&
        !contains(flatten([statement.Action]), "s3:*") &&
        !contains(flatten([statement.Resource]), "*")
      ])
    )
    error_message = "The photos policy has two Allow statements and no wildcards."
  }

  assert {
    condition     = aws_iam_role_policy_attachment.ssm.policy_arn == "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
    error_message = "The instance is managed through SSM Session Manager."
  }

  assert {
    condition = (
      length(flatten([jsondecode(aws_iam_role_policy.read_config.policy).Statement[0].Resource])) == 2 &&
      anytrue([for arn in flatten([jsondecode(aws_iam_role_policy.read_config.policy).Statement[0].Resource]) : endswith(arn, ":parameter/rutalibre/prod")]) &&
      anytrue([for arn in flatten([jsondecode(aws_iam_role_policy.read_config.policy).Statement[0].Resource]) : endswith(arn, ":parameter/rutalibre/prod/*")])
    )
    error_message = "read-config must cover exactly the path (GetParametersByPath) and the parameters under it."
  }
}
