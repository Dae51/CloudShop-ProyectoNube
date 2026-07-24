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

output "cognito_user_pool_id" {
  description = "User Pool del frontend"
  value       = module.autenticacion.user_pool_id
}

output "cognito_user_pool_client_id" {
  description = "App client público"
  value       = module.autenticacion.user_pool_client_id
}

output "cognito_identity_pool_id" {
  description = "Identity Pool para credenciales SigV4"
  value       = module.autenticacion.identity_pool_id
}

output "users_table_name" {
  description = "Tabla de usuarios para operaciones administrativas auditadas"
  value       = module.autenticacion.users_table_name
}

output "audit_table_name" {
  description = "Tabla central de auditoría"
  value       = module.autenticacion.audit_table_name
}

output "orders_table_name" {
  value = module.pedidos.orders_table_name
}

output "event_bus_name" {
  value = module.pedidos.event_bus_name
}

output "event_dlq_url" {
  value = module.pedidos.event_dlq_url
}

output "relay_failure_dlq_url" {
  description = "DLQ de registros de DynamoDB Streams agotados por el relay"
  value       = module.pedidos.relay_failure_dlq_url
}

output "reportes_lambda_name" {
  description = "Lambda del dashboard ejecutivo"
  value       = module.reportes.lambda_function_name
}

output "cloudwatch_dashboard_name" {
  description = "Dashboard operativo con métricas requeridas"
  value       = aws_cloudwatch_dashboard.cloudshop.dashboard_name
}

output "waf_web_acl_arn" {
  description = "WAF regional asociado directamente al stage de API Gateway"
  value       = aws_wafv2_web_acl.api.arn
}

output "frontend_url" {
  description = "URL HTTPS de CloudFront"
  value       = module.frontend.url
}

output "frontend_bucket_name" {
  description = "Bucket privado del frontend"
  value       = module.frontend.bucket_name
}

output "frontend_distribution_id" {
  description = "Distribución CloudFront"
  value       = module.frontend.distribution_id
}
