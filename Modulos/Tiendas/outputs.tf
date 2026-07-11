output "api_url" {
  description = "URL base de la API de tiendas"
  value       = aws_api_gateway_stage.stores.invoke_url
}

output "api_stage_arn" {
  description = "ARN del stage de API Gateway de tiendas"
  value       = aws_api_gateway_stage.stores.arn
}

output "api_name" {
  description = "Nombre de la API Gateway de tiendas"
  value       = aws_api_gateway_rest_api.stores.name
}

output "api_rest_api_id" {
  description = "ID de REST API Gateway de tiendas"
  value       = aws_api_gateway_rest_api.stores.id
}

output "api_stage_name" {
  description = "Nombre del stage de API Gateway de tiendas"
  value       = aws_api_gateway_stage.stores.stage_name
}

output "stores_table_name" {
  description = "Nombre de la tabla DynamoDB de tiendas"
  value       = aws_dynamodb_table.stores.name
}

output "stores_lambda_name" {
  description = "Nombre de la Lambda de tiendas"
  value       = aws_lambda_function.stores.function_name
}

output "api_role_policy_arns" {
  description = "Politicas para adjuntar a roles empresariales existentes"
  value = {
    administrador = aws_iam_policy.stores_api_administrador.arn
    operador      = aws_iam_policy.stores_api_operador.arn
    cliente       = aws_iam_policy.stores_api_cliente.arn
  }
}
