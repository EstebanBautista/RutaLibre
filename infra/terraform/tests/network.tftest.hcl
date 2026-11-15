mock_provider "aws" {}

run "network_layout" {
  command = plan

  module {
    source = "./modules/network"
  }

  # Route table IDs are assigned by AWS; fix them so associations can be checked.
  override_resource {
    target          = aws_route_table.private
    override_during = plan
    values          = { id = "rtb-private" }
  }

  override_resource {
    target          = aws_route_table.public
    override_during = plan
    values          = { id = "rtb-public" }
  }

  variables {
    name_prefix          = "rutalibre-test"
    vpc_cidr             = "10.20.0.0/16"
    availability_zones   = ["us-east-1a", "us-east-1b"]
    public_subnet_cidrs  = ["10.20.0.0/24", "10.20.1.0/24"]
    private_subnet_cidrs = ["10.20.10.0/24", "10.20.11.0/24"]
  }

  assert {
    condition     = aws_vpc.this.cidr_block == "10.20.0.0/16" && aws_vpc.this.enable_dns_hostnames
    error_message = "VPC must use the given CIDR with DNS hostnames enabled."
  }

  assert {
    condition     = length(aws_subnet.public) == 2 && length(aws_subnet.private) == 2
    error_message = "Expected two public and two private subnets."
  }

  assert {
    condition     = aws_subnet.private[*].cidr_block == ["10.20.10.0/24", "10.20.11.0/24"] && aws_subnet.private[*].availability_zone == ["us-east-1a", "us-east-1b"]
    error_message = "Private subnets must cover both zones with the given CIDRs."
  }

  assert {
    condition     = alltrue([for s in concat(aws_subnet.public, aws_subnet.private) : s.map_public_ip_on_launch == false])
    error_message = "No subnet may auto-assign public IPs."
  }

  assert {
    condition     = aws_subnet.public[*].cidr_block == ["10.20.0.0/24", "10.20.1.0/24"] && aws_subnet.public[*].availability_zone == ["us-east-1a", "us-east-1b"]
    error_message = "Public subnets must cover both zones with the given CIDRs."
  }

  assert {
    condition = (
      length(aws_route_table_association.private) == 2 &&
      alltrue([for association in aws_route_table_association.private : association.route_table_id == "rtb-private"])
    )
    error_message = "Private subnets must use the private route table (no route to the internet)."
  }
}
