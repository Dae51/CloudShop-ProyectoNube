output "api_url" {
  description = "URL base de la API de carrito"
  value       = aws_api_gateway_stage.cart.invoke_url
}

output "api_stage_arn" {
  description = "ARN del stage de API Gateway de carrito"
  value       = aws_api_gateway_stage.cart.arn
}

output "api_name" {
  description = "Nombre de la API Gateway de carrito"
  value       = aws_api_gateway_rest_api.cart.name
}

output "api_rest_api_id" {
  description = "ID de REST API Gateway de carrito"
  value       = aws_api_gateway_rest_api.cart.id
}

output "api_stage_name" {
  description = "Nombre del stage de API Gateway de carrito"
  value       = aws_api_gateway_stage.cart.stage_name
}

output "cart_table_name" {
  description = "Nombre de la tabla DynamoDB de carrito"
  value       = aws_dynamodb_table.cart_items.name
}

output "cart_lambda_name" {
  description = "Nombre de la Lambda de carrito"
  value       = aws_lambda_function.cart.function_name
}
