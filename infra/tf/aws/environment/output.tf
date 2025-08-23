
output "db_secret_name" {
  value = data.aws_secretsmanager_secret.db_secret.name
}

output "db_url" {
  value = local.db_url
}
