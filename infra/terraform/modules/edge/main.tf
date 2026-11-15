# CloudFront is the single HTTPS entry point, on its free *.cloudfront.net
# certificate. The frontend and the API share one origin, so the browser
# needs no CORS for the API.

locals {
  frontend_origin_id = "frontend-s3"
  api_origin_id      = "api-ec2"
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

# Forwards every header (including Host), query string and cookie to the API.
# HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, ...
data "aws_cloudfront_response_headers_policy" "security_headers" {
  name = "Managed-SecurityHeadersPolicy"
}

data "aws_cloudfront_origin_request_policy" "all_viewer" {
  name = "Managed-AllViewer"
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${var.name_prefix}-frontend"
  description                       = "CloudFront reads the private frontend bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "this" {
  #checkov:skip=CKV_AWS_68:WAF is a paid service; out of scope
  #checkov:skip=CKV2_AWS_47:WAF is a paid service; out of scope
  #checkov:skip=CKV_AWS_86:Access logs need a separate log bucket; out of scope
  #checkov:skip=CKV_AWS_310:Origin failover needs a second app server
  #checkov:skip=CKV_AWS_374:The app is public; no country is blocked
  #checkov:skip=CKV2_AWS_42:No own domain: the free *.cloudfront.net certificate is used
  #checkov:skip=CKV_AWS_174:The default *.cloudfront.net certificate does not allow choosing a minimum TLS version; needs an own domain
  enabled             = true
  comment             = var.name_prefix
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  http_version        = "http2and3"

  origin {
    origin_id                = local.frontend_origin_id
    domain_name              = var.frontend_bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  # Port 80 only: an HTTPS origin would need a load balancer or a domain with
  # its own certificate. The security group accepts only CloudFront.
  origin {
    origin_id   = local.api_origin_id
    domain_name = var.api_origin_domain_name

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id           = local.frontend_origin_id
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security_headers.id
    compress                   = true
  }

  dynamic "ordered_cache_behavior" {
    for_each = var.api_path_patterns

    content {
      path_pattern               = ordered_cache_behavior.value
      target_origin_id           = local.api_origin_id
      viewer_protocol_policy     = "redirect-to-https"
      allowed_methods            = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
      cached_methods             = ["GET", "HEAD"]
      cache_policy_id            = data.aws_cloudfront_cache_policy.disabled.id
      origin_request_policy_id   = data.aws_cloudfront_origin_request_policy.all_viewer.id
      response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security_headers.id
      compress                   = true
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# Only this distribution may read the frontend bucket.
resource "aws_s3_bucket_policy" "frontend" {
  bucket = var.frontend_bucket_id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "CloudFrontReadsFrontend"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = "s3:GetObject"
        Resource  = "${var.frontend_bucket_arn}/*"
        Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.this.arn } }
      }
    ]
  })
}
