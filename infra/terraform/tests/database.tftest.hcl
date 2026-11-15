mock_provider "aws" {}

run "database_is_private" {
  command = plan

  module {
    source = "./modules/database"
  }

  variables {
    name_prefix           = "rutalibre-test"
    vpc_id                = "vpc-test"
    subnet_ids            = ["subnet-a", "subnet-b"]
    app_security_group_id = "sg-app"
  }

  assert {
    condition = (
      aws_db_instance.this.engine == "postgres" &&
      aws_db_instance.this.instance_class == "db.t4g.micro" &&
      aws_db_instance.this.allocated_storage == 20 &&
      aws_db_instance.this.storage_type == "gp3"
    )
    error_message = "Expected PostgreSQL on db.t4g.micro with 20 GB of gp3."
  }

  assert {
    condition = (
      aws_db_instance.this.publicly_accessible == false &&
      aws_db_instance.this.storage_encrypted == true &&
      aws_db_instance.this.multi_az == false
    )
    error_message = "The database must be private and encrypted (single AZ)."
  }

  assert {
    condition     = aws_db_instance.this.manage_master_user_password == true && aws_db_instance.this.password == null
    error_message = "RDS must manage the master password; none may appear in the code."
  }

  assert {
    condition = (
      aws_db_instance.this.deletion_protection == true &&
      aws_db_instance.this.skip_final_snapshot == false &&
      aws_db_instance.this.backup_retention_period == 7
    )
    error_message = "Deletion protection, a final snapshot and 7 days of backups are required."
  }

  assert {
    condition = (
      aws_vpc_security_group_ingress_rule.from_app.from_port == 5432 &&
      aws_vpc_security_group_ingress_rule.from_app.to_port == 5432 &&
      aws_vpc_security_group_ingress_rule.from_app.ip_protocol == "tcp"
    )
    error_message = "The database accepts only TCP 5432."
  }

  assert {
    condition = (
      aws_vpc_security_group_ingress_rule.from_app.referenced_security_group_id == "sg-app" &&
      aws_vpc_security_group_ingress_rule.from_app.cidr_ipv4 == null &&
      aws_vpc_security_group_ingress_rule.from_app.cidr_ipv6 == null
    )
    error_message = "Port 5432 must be open only to the app security group, never to a CIDR."
  }

  assert {
    condition = anytrue([
      for parameter in aws_db_parameter_group.this.parameter :
      parameter.name == "rds.force_ssl" && parameter.value == "1"
    ])
    error_message = "The database must require TLS (rds.force_ssl = 1)."
  }
}
