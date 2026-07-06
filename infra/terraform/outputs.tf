output "ecr_repository_url" {
  description = "Push the app image here: docker tag paz-rav:latest <this>:latest && docker push <this>:latest"
  value       = aws_ecr_repository.app.repository_url
}

output "app_runner_url" {
  description = "The live dashboard URL once App Runner finishes deploying"
  value       = aws_apprunner_service.app.service_url
}

output "postgres_endpoint" {
  value = aws_db_instance.postgres.address
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.redis.cache_nodes[0].address
}
