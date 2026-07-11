output "users_table_name" {
  description = "Nombre de la tabla de usuarios"
  value       = aws_dynamodb_table.users.name
}

output "user_audit_table_name" {
  description = "Nombre de la tabla de auditoria de usuarios"
  value       = aws_dynamodb_table.user_audit.name
}

output "api_url" {
  description = "URL base de la API de usuarios"
  value       = aws_api_gateway_stage.usuarios.invoke_url
}

output "api_stage_arn" {
  description = "ARN del stage de API Gateway de usuarios"
  value       = aws_api_gateway_stage.usuarios.arn
}

output "api_name" {
  description = "Nombre de la API Gateway de usuarios"
  value       = aws_api_gateway_rest_api.usuarios.name
}

output "api_rest_api_id" {
  description = "ID de REST API Gateway de usuarios"
  value       = aws_api_gateway_rest_api.usuarios.id
}

output "api_stage_name" {
  description = "Nombre del stage de API Gateway de usuarios"
  value       = aws_api_gateway_stage.usuarios.stage_name
}

output "lambda_name" {
  description = "Nombre de la Lambda de usuarios"
  value       = aws_lambda_function.usuarios.function_name
}

output "api_role_policy_arns" {
  description = "Politicas para adjuntar a roles empresariales existentes"
  value = {
    administrador = aws_iam_policy.usuarios_api_administrador.arn
    operador      = aws_iam_policy.usuarios_api_operador.arn
    cliente       = aws_iam_policy.usuarios_api_cliente.arn
  }
}
