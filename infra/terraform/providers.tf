# Credentials are never configured here. This configuration is validated and
# tested in CI with a mocked provider; it is not applied.
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
