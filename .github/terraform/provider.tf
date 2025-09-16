# DO NOT EDIT - Managed by tackle
provider "github" {
  owner = "sudoblockio-new"
}
terraform {
  required_providers {
    github = {
      source  = "integrations/github"
      version = "6.6.0"
    }
  }

  backend "s3" {
    key            = "github/sudoblockio/pytest-ansible-kind/.github/terraform.tfstate"
    bucket         = "sb-github-remote-state"
    dynamodb_table = "sb-github-remote-state"
    region         = "us-east-1"
  }
}
