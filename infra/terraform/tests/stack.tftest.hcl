mock_provider "aws" {}

# Fixed IDs for the resources whose IDs AWS would assign, so the test can
# check which subnet and security group each module receives.
override_resource {
  target          = module.network.aws_subnet.private
  override_during = plan
  values          = { id = "subnet-private" }
}

override_resource {
  target          = module.network.aws_subnet.public
  override_during = plan
  values          = { id = "subnet-public" }
}

override_resource {
  target          = module.compute.aws_security_group.app
  override_during = plan
  values          = { id = "sg-app" }
}

override_resource {
  target          = module.edge.aws_cloudfront_distribution.this
  override_during = plan
  values          = { domain_name = "dstack.cloudfront.net" }
}

# The root module with its default values: every module wired together
# produces a plan.
run "whole_stack_plans" {
  command = plan

  assert {
    condition     = output.evidence_bucket_name == "rutalibre-evidencias"
    error_message = "The evidence bucket keeps the name used on Backblaze."
  }

  assert {
    condition     = output.frontend_bucket_name == "rutalibre-frontend"
    error_message = "Unexpected frontend bucket name."
  }
}

run "modules_are_wired_safely" {
  command = plan

  assert {
    condition     = toset(module.database.subnet_ids) == toset(["subnet-private"])
    error_message = "The database must live only in the private subnets."
  }

  assert {
    condition     = module.database.allowed_security_group_id == "sg-app"
    error_message = "The database must accept connections only from the app security group."
  }

  assert {
    condition     = module.compute.subnet_id == "subnet-public"
    error_message = "The app server must live in a public subnet."
  }

  assert {
    condition     = module.compute.public_host == "dstack.cloudfront.net"
    error_message = "The app server must receive the CloudFront host name."
  }
}
