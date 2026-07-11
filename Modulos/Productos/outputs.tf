output "api_url" {
  description = "URL base de la API de productos"
  value       = aws_api_gateway_stage.products.invoke_url
}

output "api_stage_arn" {
  description = "ARN del stage de API Gateway de productos"
  value       = aws_api_gateway_stage.products.arn
}

output "api_name" {
  description = "Nombre de la API Gateway de productos"
  value       = aws_api_gateway_rest_api.products.name
}

output "api_rest_api_id" {
  description = "ID de REST API Gateway de productos"
  value       = aws_api_gateway_rest_api.products.id
}

output "api_stage_name" {
  description = "Nombre del stage de API Gateway de productos"
  value       = aws_api_gateway_stage.products.stage_name
}

output "lambda_name" {
  description = "Nombre de la Lambda de productos"
  value       = aws_lambda_function.products.function_name
}

output "products_table_name" {
  description = "Nombre de la tabla de productos"
  value       = aws_dynamodb_table.products.name
}

output "audit_table_name" {
  description = "Nombre de la tabla de auditoria de productos"
  value       = aws_dynamodb_table.product_audit.name
}

output "api_role_policy_arns" {
  description = "Politicas para adjuntar a roles empresariales existentes"
  value = {
    administrador = aws_iam_policy.products_api_administrador.arn
    operador      = aws_iam_policy.products_api_operador.arn
    cliente       = aws_iam_policy.products_api_cliente.arn
  }
}
