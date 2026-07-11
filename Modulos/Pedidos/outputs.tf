output "api_url" {
  description = "URL base de la API de pedidos"
  value       = aws_api_gateway_stage.orders.invoke_url
}

output "api_stage_arn" {
  description = "ARN del stage de API Gateway de pedidos"
  value       = aws_api_gateway_stage.orders.arn
}

output "api_name" {
  description = "Nombre de la API Gateway de pedidos"
  value       = aws_api_gateway_rest_api.orders.name
}

output "api_rest_api_id" {
  description = "ID de REST API Gateway de pedidos"
  value       = aws_api_gateway_rest_api.orders.id
}

output "api_stage_name" {
  description = "Nombre del stage de API Gateway de pedidos"
  value       = aws_api_gateway_stage.orders.stage_name
}

output "lambda_names" {
  description = "Nombres de Lambdas del modulo de pedidos"
  value = [
    aws_lambda_function.orders.function_name,
    aws_lambda_function.inventory.function_name,
    aws_lambda_function.audit.function_name,
    aws_lambda_function.email.function_name
  ]
}

output "orders_table_name" {
  description = "Nombre de la tabla DynamoDB de pedidos"
  value       = aws_dynamodb_table.orders.name
}

output "orders_event_bus_name" {
  description = "Nombre del bus EventBridge de pedidos"
  value       = aws_cloudwatch_event_bus.orders.name
}

output "orders_audit_table_name" {
  description = "Nombre de la tabla de auditoria de eventos de pedidos"
  value       = aws_dynamodb_table.order_events_audit.name
}
