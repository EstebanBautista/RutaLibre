# PostgreSQL in the private subnets. Only the app server's security group can
# reach it, it has no public address, and the master password never exists in
# this code or in the Terraform state: RDS generates it and keeps it in
# Secrets Manager (manage_master_user_password).

resource "aws_db_subnet_group" "this" {
  name       = var.name_prefix
  subnet_ids = var.subnet_ids
}

resource "aws_db_parameter_group" "this" {
  name   = "${var.name_prefix}-postgres${var.engine_version}"
  family = "postgres${var.engine_version}"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
}

resource "aws_security_group" "db" {
  name        = "${var.name_prefix}-db"
  description = "PostgreSQL, reachable only from the app server"
  vpc_id      = var.vpc_id

  # No egress rules: the database never starts connections.
}

resource "aws_vpc_security_group_ingress_rule" "from_app" {
  security_group_id            = aws_security_group.db.id
  description                  = "PostgreSQL from the app server"
  referenced_security_group_id = var.app_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_db_instance" "this" {
  identifier     = var.name_prefix
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage = var.allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name                     = var.db_name
  username                    = var.username
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.this.name
  parameter_group_name   = aws_db_parameter_group.this.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period    = 7
  copy_tags_to_snapshot      = true
  deletion_protection        = true
  skip_final_snapshot        = false
  final_snapshot_identifier  = "${var.name_prefix}-final"
  auto_minor_version_upgrade = true
}
