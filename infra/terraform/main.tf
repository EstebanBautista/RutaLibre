locals {
  name_prefix = "${var.project}-${var.environment}"
}

module "network" {
  source = "./modules/network"

  name_prefix          = local.name_prefix
  vpc_cidr             = var.vpc_cidr
  availability_zones   = var.availability_zones
  public_subnet_cidrs  = [cidrsubnet(var.vpc_cidr, 8, 0), cidrsubnet(var.vpc_cidr, 8, 1)]
  private_subnet_cidrs = [cidrsubnet(var.vpc_cidr, 8, 10), cidrsubnet(var.vpc_cidr, 8, 11)]
}

module "storage" {
  source = "./modules/storage"

  evidence_bucket_name = var.evidence_bucket_name
  frontend_bucket_name = var.frontend_bucket_name
  # Replaced by the CloudFront address once the edge module exists.
  cors_allowed_origins = ["https://rutalibre-chi.vercel.app"]
}
