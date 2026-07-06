# Paz Rav — Stage 1 AWS deployment (App Runner + RDS + ElastiCache).
# See README.md in this directory before running `terraform apply` — this costs real money.

terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = var.aws_region
}

# ---- Image registry ----
# Apply this first (`terraform apply -target=aws_ecr_repository.app`), push the image
# built by the repo's Dockerfile, THEN apply the rest — App Runner needs an image to exist.
resource "aws_ecr_repository" "app" {
  name                 = "${var.project}-app"
  image_tag_mutability = "MUTABLE"
}

# ---- Networking (default VPC keeps this cheap/simple for stage 1) ----
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "db" {
  name        = "${var.project}-db"
  description = "Postgres + Redis, reachable only from App Runner's VPC connector"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }
  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ---- RDS Postgres (db.t4g.micro — the cheap tier) ----
resource "aws_db_subnet_group" "this" {
  name       = "${var.project}-db"
  subnet_ids = data.aws_subnets.default.ids
}

resource "aws_db_instance" "postgres" {
  identifier             = "${var.project}-pg"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = "db.t4g.micro"
  allocated_storage      = 20
  db_name                = "pazrav"
  username               = "paz"
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.db.id]
  skip_final_snapshot    = true
  publicly_accessible    = false
}

# ---- ElastiCache Redis (cache.t4g.micro — the cheap tier) ----
resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.project}-redis"
  subnet_ids = data.aws_subnets.default.ids
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${var.project}-redis"
  engine               = "redis"
  node_type            = "cache.t4g.micro"
  num_cache_nodes      = 1
  subnet_group_name    = aws_elasticache_subnet_group.this.name
  security_group_ids   = [aws_security_group.db.id]
  port                 = 6379
}

# ---- Secrets (app reads these as env vars) ----
resource "aws_secretsmanager_secret" "app" {
  name = "${var.project}/app"
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    DATABASE_URL      = "postgresql://paz:${var.db_password}@${aws_db_instance.postgres.address}:5432/pazrav"
    REDIS_URL         = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0"
    ANTHROPIC_API_KEY = var.anthropic_api_key
  })
}

# ---- App Runner (the app + dashboard container) ----
resource "aws_apprunner_service" "app" {
  service_name = "${var.project}-app"

  source_configuration {
    image_repository {
      image_identifier      = "${aws_ecr_repository.app.repository_url}:latest"
      image_repository_type = "ECR"
      image_configuration {
        port = "8000"
        runtime_environment_variables = {
          PAZ_PERSIST = "redis_postgres"
          PAZ_DATA    = "yfinance"
          UNDERLYINGS = var.underlyings
        }
      }
    }
    auto_deployments_enabled = true
  }

  instance_configuration {
    cpu    = "256"   # 0.25 vCPU — the cheap tier
    memory = "512"   # 0.5 GB
  }

  # Note: connecting App Runner to the default VPC (to reach RDS/ElastiCache) needs a
  # VPC connector — omitted here for brevity; add aws_apprunner_vpc_connector +
  # network_configuration before applying for real. See README.md in this directory.

  depends_on = [aws_ecr_repository.app]
}
