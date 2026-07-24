output "user_pool_id" {
  description = "ID del User Pool"
  value       = aws_cognito_user_pool.cloudshop.id
}

output "user_pool_arn" {
  description = "ARN del User Pool"
  value       = aws_cognito_user_pool.cloudshop.arn
}

output "user_pool_client_id" {
  description = "App client público sin secret"
  value       = aws_cognito_user_pool_client.web.id
}

output "identity_pool_id" {
  description = "ID del Identity Pool"
  value       = aws_cognito_identity_pool.cloudshop.id
}

output "role_names" {
  description = "Nombres de roles IAM por rol oficial"
  value       = { for key, role in aws_iam_role.identity : key => role.name }
}

output "role_arns" {
  description = "ARN de roles IAM por rol oficial"
  value       = { for key, role in aws_iam_role.identity : key => role.arn }
}

output "users_table_name" {
  value = aws_dynamodb_table.users.name
}

output "users_table_arn" {
  value = aws_dynamodb_table.users.arn
}

output "audit_table_name" {
  value = aws_dynamodb_table.audit.name
}

output "audit_table_arn" {
  value = aws_dynamodb_table.audit.arn
}

output "idempotency_table_name" {
  value = aws_dynamodb_table.idempotency.name
}

output "idempotency_table_arn" {
  value = aws_dynamodb_table.idempotency.arn
}

output "post_confirmation_lambda_name" {
  value = aws_lambda_function.post_confirmation.function_name
}
