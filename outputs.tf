output "cloudshop_api_url" {
  description = "URL base de la API compartida de CloudShop"
  value       = aws_api_gateway_stage.cloudshop.invoke_url
}

output "cloudshop_api_execution_arn" {
  description = "ARN de ejecución de la API compartida"
  value       = aws_api_gateway_rest_api.cloudshop.execution_arn
}

output "productos_routes" {
  description = "Rutas registradas por el módulo de Productos"
  value       = module.productos.routes_summary
}

output "productos_table_name" {
  description = "Nombre de la tabla de productos"
  value       = module.productos.products_table_name
}

output "product_audit_table_name" {
  description = "Nombre de la tabla de auditoría de productos"
  value       = module.productos.audit_table_name
}

output "productos_lambda_name" {
  description = "Nombre de la Lambda de Productos"
  value       = module.productos.lambda_function_name
}

output "productos_role_policy_arns" {
  description = "Políticas de invocación de Productos por rol"
  value       = module.productos.api_role_policy_arns
}
