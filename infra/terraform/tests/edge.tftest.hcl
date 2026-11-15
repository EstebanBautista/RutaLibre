mock_provider "aws" {
  # The bucket policy names the distribution ARN, which AWS only assigns on
  # apply. A fixed ARN at plan time lets the test read the whole policy.
  mock_resource "aws_cloudfront_distribution" {
    override_during = plan
    defaults = {
      arn = "arn:aws:cloudfront::123456789012:distribution/TEST"
    }
  }
}

run "https_everywhere" {
  command = plan

  module {
    source = "./modules/edge"
  }

  variables {
    name_prefix                          = "rutalibre-test"
    frontend_bucket_id                   = "fe-test"
    frontend_bucket_arn                  = "arn:aws:s3:::fe-test"
    frontend_bucket_regional_domain_name = "fe-test.s3.us-east-1.amazonaws.com"
    api_origin_domain_name               = "ec2-test.compute-1.amazonaws.com"
  }

  assert {
    condition = (
      aws_cloudfront_distribution.this.enabled == true &&
      aws_cloudfront_distribution.this.default_root_object == "index.html" &&
      aws_cloudfront_distribution.this.price_class == "PriceClass_100"
    )
    error_message = "Expected an enabled distribution serving index.html from the cheapest price class."
  }

  assert {
    condition = (
      aws_cloudfront_distribution.this.default_cache_behavior[0].target_origin_id == "frontend-s3" &&
      aws_cloudfront_distribution.this.default_cache_behavior[0].viewer_protocol_policy == "redirect-to-https"
    )
    error_message = "By default, serve the frontend bucket and redirect HTTP to HTTPS."
  }

  assert {
    condition = (
      length(aws_cloudfront_distribution.this.ordered_cache_behavior) == 5 &&
      alltrue([
        for behavior in aws_cloudfront_distribution.this.ordered_cache_behavior :
        behavior.target_origin_id == "api-ec2" && behavior.viewer_protocol_policy == "redirect-to-https"
      ]) &&
      toset(aws_cloudfront_distribution.this.ordered_cache_behavior[*].path_pattern) == toset(["/api/*", "/admin/*", "/static/*", "/docs", "/openapi.json"])
    )
    error_message = "The five API paths go to the EC2 origin, always over HTTPS for the viewer."
  }

  assert {
    condition = anytrue([
      for origin in aws_cloudfront_distribution.this.origin :
      origin.origin_id == "api-ec2" &&
      origin.domain_name == "ec2-test.compute-1.amazonaws.com" &&
      origin.custom_origin_config[0].origin_protocol_policy == "http-only"
    ])
    error_message = "The API origin is the EC2 host on port 80."
  }

  assert {
    condition = (
      length(jsondecode(aws_s3_bucket_policy.frontend.policy).Statement) == 1 &&
      jsondecode(aws_s3_bucket_policy.frontend.policy).Statement[0].Effect == "Allow" &&
      jsondecode(aws_s3_bucket_policy.frontend.policy).Statement[0].Action == "s3:GetObject" &&
      jsondecode(aws_s3_bucket_policy.frontend.policy).Statement[0].Principal.Service == "cloudfront.amazonaws.com" &&
      jsondecode(aws_s3_bucket_policy.frontend.policy).Statement[0].Resource == "arn:aws:s3:::fe-test/*" &&
      jsondecode(aws_s3_bucket_policy.frontend.policy).Statement[0].Condition.StringEquals["AWS:SourceArn"] == "arn:aws:cloudfront::123456789012:distribution/TEST"
    )
    error_message = "Only this CloudFront distribution may read the frontend bucket."
  }

  assert {
    condition = (
      aws_cloudfront_distribution.this.default_cache_behavior[0].response_headers_policy_id != null &&
      alltrue([for behavior in aws_cloudfront_distribution.this.ordered_cache_behavior : behavior.response_headers_policy_id != null])
    )
    error_message = "Every behavior must add the security response headers."
  }
}
