output "state_bucket_name" {
  description = "Bucket a pasar a terraform init -backend-config"
  value       = aws_s3_bucket.terraform_state.id
}

output "state_region" {
  description = "Región a pasar a terraform init -backend-config"
  value       = var.aws_region
}

output "state_key" {
  description = "Clave recomendada para el ambiente"
  value       = "cloudshop/${var.environment}/terraform.tfstate"
}
