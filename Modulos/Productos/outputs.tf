output "products_table_name" {
  description = "Nombre de la tabla de productos"
  value       = aws_dynamodb_table.products.name
}

output "products_table_arn" {
  description = "ARN de la tabla de productos"
  value       = aws_dynamodb_table.products.arn
}

output "lambda_function_name" {
  description = "Nombre de la Lambda de Productos"
  value       = aws_lambda_function.products.function_name
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

output "store_resource_id" {
  description = "ID compartido de /tiendas/{storeId}"
  value       = var.store_resource_id
}

output "routes_summary" {
  description = "Rutas de Productos registradas en la API compartida"
  value = {
    "POST /productos"                         = ["Administrador"]
    "GET /productos"                          = ["Administrador", "Operador", "Cliente"]
    "GET /productos/{productId}"              = ["Administrador", "Operador", "Cliente"]
    "GET /tiendas/{storeId}/productos"        = ["Administrador", "Operador", "Cliente"]
    "PUT /productos/{productId}"              = ["Administrador"]
    "PATCH /productos/{productId}/inventario" = ["Administrador", "Operador"]
    "DELETE /productos/{productId}"           = ["Administrador"]
  }
}

output "route_configuration_hash" {
  description = "Huella de rutas usada por el deployment compartido"
  value = sha1(jsonencode({
    resources = {
      productos      = aws_api_gateway_resource.productos.id
      product        = aws_api_gateway_resource.product.id
      inventario     = aws_api_gateway_resource.inventario.id
      store          = var.store_resource_id
      store_products = aws_api_gateway_resource.store_products.id
    }
    methods = {
      for key, method in aws_api_gateway_method.products : key => {
        id            = method.id
        http_method   = method.http_method
        authorization = method.authorization
        resource_id   = method.resource_id
      }
    }
    integrations = {
      for key, integration in aws_api_gateway_integration.products : key => {
        id                      = integration.id
        type                    = integration.type
        integration_http_method = integration.integration_http_method
        uri                     = integration.uri
      }
    }
    lambda_permissions = {
      for key, permission in aws_lambda_permission.api_gateway : key => permission.source_arn
    }
    cors = {
      for key, integration in aws_api_gateway_integration.options : key => integration.id
    }
  }))
}
