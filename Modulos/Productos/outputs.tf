output "api_url" {
  description = "URL base de la API de productos"
  value       = aws_api_gateway_stage.products.invoke_url
}

output "products_table_name" {
  description = "Nombre de la tabla de productos"
  value       = aws_dynamodb_table.products.name
}

output "audit_table_name" {
  description = "Nombre de la tabla de auditoría de productos"
  value       = aws_dynamodb_table.product_audit.name
}

output "api_role_policy_arns" {
  description = "Políticas para adjuntar a los roles empresariales existentes"
  value = {
    administrador = aws_iam_policy.products_api_administrador.arn
    operador      = aws_iam_policy.products_api_operador.arn
    cliente       = aws_iam_policy.products_api_cliente.arn
  }
}
