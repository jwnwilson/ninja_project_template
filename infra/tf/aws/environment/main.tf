terraform {
  backend "s3" {
    region = "eu-west-1"
    bucket = "hexrepo-jwn"
    key = "{{project_slug}}_be-environment.tfstate"
  }
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}


locals {
  db_url = "postgresql+psycopg://postgres:{password}@${module.{{project_slug}}_be_postgres.db_instance_endpoint}/${var.project}"
  db_ro_url = module.{{project_slug}}_be_postgres.db_instance_ro_endpoint != null ? "postgresql+psycopg://postgres:{password}@${module.{{project_slug}}_be_postgres.db_instance_ro_endpoint}/${var.project}" : "postgresql+psycopg://postgres:{password}@${module.{{project_slug}}_be_postgres.db_instance_endpoint}/${var.project}"
}

locals {
    account_id = data.aws_caller_identity.current.account_id
    region = data.aws_region.current.name
    common_env_vars = {
      ENVIRONMENT             = terraform.workspace
      PROJECT                 = var.project
      CLOUD_PROVIDER          = "AWS"
      DB_URL                  = local.db_url
      DB_RO_URL               = local.db_ro_url
      READ_REPLICA_ENABLED    = "false"
      DB_PASSWORD_SECRET_NAME = data.aws_secretsmanager_secret.db_secret.name
      TASK_QUEUE              = "${var.project}_${terraform.workspace}_tasks"
      CLIENT_ID               = module.common_auth.client_id
      USER_POOL_ID            = module.common_auth.user_pool_id
      ALLOWED_ORIGINS         = "*"
      LOG_JSON                = "true"
      ORIGIN_URL              = "https://${local.api_subdomain_ecs}.${var.domain}"
      TASK_TABLE_NAME         = module.common_task_nosql.table_name
      LOG_LEVEL               = "INFO"
    }
}

provider "aws" {
  region  = var.aws_region
}

data "aws_vpc" "hexrepo" {
  filter {
    name   = "tag:Name"
    values = ["hexrepo-vpc-${terraform.workspace}"]
  }
}

data "aws_ecr_repository" "ecr_repo" {
  name                 = "hexrepo-${var.project}"
}






module "{{project_slug}}_be_ecs_api" {
  source             = "../../../../../../infra/tf/aws/modules/ecs"
  project            = var.project
  name               = "api"
  environment        = terraform.workspace
  aws_region         = var.aws_region
  vpc_id             = data.aws_vpc.hexrepo.id
  private_subnet_ids = data.aws_subnets.private.ids
  security_group_ids = [module.common_postgres.db_security_group_id]
  target_group_arn   = module.common_alb.target_group_arn
  # This costs money
  container_insights = "disabled"
  min_capacity       = 0

  ecr_url        = data.aws_ecr_repository.ecr_repo.repository_url
  docker_tag     = var.docker_tag_container
  container_port = 8000

  environment_variables = local.common_env_vars
  secrets = {
    DB_PASSWORD = data.aws_secretsmanager_secret.db_secret.arn
  }

  desired_count = 1
  task_cpu      = 256
  task_memory   = 512
}









module "{{project_slug}}_be_api_gateway" {
  source = "../../../../../../infra/tf/aws/modules/apigateway"

  environment       = terraform.workspace
  lambda_invoke_arn = module.{{project_slug}}_be_api.lambda_function_invoke_arn
  lambda_name       = module.{{project_slug}}_be_api.lambda_function_name
  domain            = var.domain
  api_subdomain     = "{{project_slug}}_be-${terraform.workspace}"
  project           = "{{project_slug}}_be"
  cognito_user_pool_arn = module.common_auth.user_pool_arn
  # Auth handled in api middleware
  auth_enabled          = false
}


module "{{project_slug}}_be_postgres" {
  source = "../../../../../../infra/tf/aws/modules/rds"

  environment       = terraform.workspace
  project           = "{{project_slug}}_be"
  vpc_id            = data.aws_vpc.hexrepo.id
  username          = "postgres"
}

data "aws_secretsmanager_secret" "db_secret" {
  arn = module.{{project_slug}}_be_postgres.db_password_secret_arn
}



module "{{project_slug}}_be_bucket" {
  source = "../../../../../../infra/tf/aws/modules/s3"

  project     = "{{project_slug}}_be"
  name        = "{{project_slug}}_be"
}
