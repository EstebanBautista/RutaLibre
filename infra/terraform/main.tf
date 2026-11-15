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
  # The browser uploads photos from the page CloudFront serves. No cycle:
  # this CORS rule depends on the distribution, the distribution depends on
  # the frontend bucket, not on the evidence bucket.
  cors_allowed_origins = ["https://${module.edge.domain_name}"]
}

module "compute" {
  source = "./modules/compute"

  name_prefix          = local.name_prefix
  region               = var.region
  vpc_id               = module.network.vpc_id
  vpc_cidr             = module.network.vpc_cidr
  subnet_id            = module.network.public_subnet_ids[0]
  evidence_bucket_name = module.storage.evidence_bucket_name
  evidence_bucket_arn  = module.storage.evidence_bucket_arn
  db_secret_arn        = module.database.master_user_secret_arn
  db_address           = module.database.address
  db_port              = module.database.port
  db_name              = module.database.db_name
  repo_url             = var.repo_url
  public_host          = module.edge.domain_name
}

module "database" {
  source = "./modules/database"

  name_prefix           = local.name_prefix
  vpc_id                = module.network.vpc_id
  subnet_ids            = module.network.private_subnet_ids
  app_security_group_id = module.compute.security_group_id
}

module "edge" {
  source = "./modules/edge"

  name_prefix                          = local.name_prefix
  frontend_bucket_id                   = module.storage.frontend_bucket_id
  frontend_bucket_arn                  = module.storage.frontend_bucket_arn
  frontend_bucket_regional_domain_name = module.storage.frontend_bucket_regional_domain_name
  api_origin_domain_name               = module.compute.public_dns
}
