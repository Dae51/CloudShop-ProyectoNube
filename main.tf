# Archivo raiz de Terraform

module "usuarios" {
  source = "./Modulos/Usuarios"
}

module "productos" {
  source = "./Modulos/Productos"
}

module "tiendas" {
  source = "./Modulos/Tiendas"
}

module "compras" {
  source = "./Modulos/Compras"
}

module "pedidos" {
  source = "./Modulos/Pedidos"

  products_table_name = module.productos.products_table_name
  ses_source_email    = var.ses_source_email
}

module "reportes" {
  source = "./Modulos/Reportes"

  orders_table_name   = module.pedidos.orders_table_name
  products_table_name = module.productos.products_table_name
}

module "seguridad" {
  source = "./Modulos/Seguridad"

  providers = {
    aws        = aws
    aws.global = aws.us_east_1
  }

  api_gateway_stage_arns = {
    usuarios  = module.usuarios.api_stage_arn
    productos = module.productos.api_stage_arn
    tiendas   = module.tiendas.api_stage_arn
    compras   = module.compras.api_stage_arn
    pedidos   = module.pedidos.api_stage_arn
    reportes  = module.reportes.api_stage_arn
  }
}

module "observabilidad" {
  source = "./Modulos/Observabilidad"

  lambda_function_names = concat(
    [
      module.usuarios.lambda_name,
      module.productos.lambda_name,
      module.tiendas.stores_lambda_name,
      module.compras.cart_lambda_name,
      module.reportes.reports_lambda_name
    ],
    module.pedidos.lambda_names
  )

  api_gateways = [
    {
      name        = module.usuarios.api_name
      rest_api_id = module.usuarios.api_rest_api_id
      stage_name  = module.usuarios.api_stage_name
    },
    {
      name        = module.productos.api_name
      rest_api_id = module.productos.api_rest_api_id
      stage_name  = module.productos.api_stage_name
    },
    {
      name        = module.tiendas.api_name
      rest_api_id = module.tiendas.api_rest_api_id
      stage_name  = module.tiendas.api_stage_name
    },
    {
      name        = module.compras.api_name
      rest_api_id = module.compras.api_rest_api_id
      stage_name  = module.compras.api_stage_name
    },
    {
      name        = module.pedidos.api_name
      rest_api_id = module.pedidos.api_rest_api_id
      stage_name  = module.pedidos.api_stage_name
    },
    {
      name        = module.reportes.api_name
      rest_api_id = module.reportes.api_rest_api_id
      stage_name  = module.reportes.api_stage_name
    }
  ]

  dynamodb_table_names = [
    module.usuarios.users_table_name,
    module.usuarios.user_audit_table_name,
    module.productos.products_table_name,
    module.productos.audit_table_name,
    module.tiendas.stores_table_name,
    module.compras.cart_table_name,
    module.pedidos.orders_table_name,
    module.pedidos.orders_audit_table_name
  ]
}

module "frontend" {
  source = "./Modulos/Frontend"

  environment            = "dev"
  usuarios_api_url       = module.usuarios.api_url
  productos_api_url      = module.productos.api_url
  tiendas_api_url        = module.tiendas.api_url
  compras_api_url        = module.compras.api_url
  pedidos_api_url        = module.pedidos.api_url
  reportes_api_url       = module.reportes.api_url
  cloudfront_web_acl_arn = module.seguridad.cloudfront_web_acl_arn
}

output "productos_api_url" {
  description = "URL base de la API del modulo de productos"
  value       = module.productos.api_url
}

output "tiendas_api_url" {
  description = "URL base de la API del modulo de tiendas"
  value       = module.tiendas.api_url
}

output "compras_api_url" {
  description = "URL base de la API del modulo de carrito"
  value       = module.compras.api_url
}

output "pedidos_api_url" {
  description = "URL base de la API del modulo de pedidos"
  value       = module.pedidos.api_url
}

output "reportes_api_url" {
  description = "URL base de la API del modulo de reportes"
  value       = module.reportes.api_url
}

output "frontend_url" {
  description = "URL HTTPS del frontend CloudFront"
  value       = module.frontend.frontend_url
}

output "cloudfront_web_acl_arn" {
  description = "ARN del Web ACL asociado a CloudFront"
  value       = module.seguridad.cloudfront_web_acl_arn
}

output "api_gateway_web_acl_arn" {
  description = "ARN del Web ACL asociado a API Gateway"
  value       = module.seguridad.api_gateway_web_acl_arn
}

output "observabilidad_dashboard_name" {
  description = "Nombre del dashboard CloudWatch de CloudShop"
  value       = module.observabilidad.dashboard_name
}
