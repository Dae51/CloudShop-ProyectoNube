locals {
  name_prefix = "${var.project_name}-${var.environment}"
  common_tags = {
    Project     = "CloudShop"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

module "autenticacion" {
  source = "./Modulos/Autenticacion"

  name_prefix        = local.name_prefix
  environment        = var.environment
  log_retention_days = var.log_retention_days
  common_tags        = local.common_tags
}

module "usuarios" {
  source = "./Modulos/Usuarios"

  name_prefix        = local.name_prefix
  rest_api_id        = aws_api_gateway_rest_api.cloudshop.id
  root_resource_id   = aws_api_gateway_rest_api.cloudshop.root_resource_id
  execution_arn      = aws_api_gateway_rest_api.cloudshop.execution_arn
  stage_name         = var.api_stage_name
  users_table_name   = module.autenticacion.users_table_name
  users_table_arn    = module.autenticacion.users_table_arn
  audit_table_name   = module.autenticacion.audit_table_name
  audit_table_arn    = module.autenticacion.audit_table_arn
  user_pool_id       = module.autenticacion.user_pool_id
  user_pool_arn      = module.autenticacion.user_pool_arn
  common_layer_arn   = aws_lambda_layer_version.common.arn
  log_retention_days = var.log_retention_days
  common_tags        = local.common_tags
}

module "productos" {
  source = "./Modulos/Productos"

  rest_api_id      = aws_api_gateway_rest_api.cloudshop.id
  root_resource_id = aws_api_gateway_rest_api.cloudshop.root_resource_id
  execution_arn    = aws_api_gateway_rest_api.cloudshop.execution_arn
  stage_name       = var.api_stage_name
}

module "tiendas" {
  source = "./Modulos/Tiendas"

  name_prefix        = local.name_prefix
  rest_api_id        = aws_api_gateway_rest_api.cloudshop.id
  execution_arn      = aws_api_gateway_rest_api.cloudshop.execution_arn
  stage_name         = var.api_stage_name
  stores_resource_id = module.productos.stores_resource_id
  store_resource_id  = module.productos.store_resource_id
  audit_table_name   = module.autenticacion.audit_table_name
  audit_table_arn    = module.autenticacion.audit_table_arn
  common_layer_arn   = aws_lambda_layer_version.common.arn
  log_retention_days = var.log_retention_days
  common_tags        = local.common_tags
}

module "carritos" {
  source = "./Modulos/Carritos"

  name_prefix         = local.name_prefix
  rest_api_id         = aws_api_gateway_rest_api.cloudshop.id
  root_resource_id    = aws_api_gateway_rest_api.cloudshop.root_resource_id
  execution_arn       = aws_api_gateway_rest_api.cloudshop.execution_arn
  stage_name          = var.api_stage_name
  products_table_name = module.productos.products_table_name
  products_table_arn  = module.productos.products_table_arn
  common_layer_arn    = aws_lambda_layer_version.common.arn
  log_retention_days  = var.log_retention_days
  common_tags         = local.common_tags
}

module "pedidos" {
  source = "./Modulos/Pedidos"

  name_prefix            = local.name_prefix
  rest_api_id            = aws_api_gateway_rest_api.cloudshop.id
  root_resource_id       = aws_api_gateway_rest_api.cloudshop.root_resource_id
  execution_arn          = aws_api_gateway_rest_api.cloudshop.execution_arn
  stage_name             = var.api_stage_name
  products_table_name    = module.productos.products_table_name
  products_table_arn     = module.productos.products_table_arn
  carts_table_name       = module.carritos.carts_table_name
  carts_table_arn        = module.carritos.carts_table_arn
  users_table_name       = module.autenticacion.users_table_name
  users_table_arn        = module.autenticacion.users_table_arn
  audit_table_name       = module.autenticacion.audit_table_name
  audit_table_arn        = module.autenticacion.audit_table_arn
  idempotency_table_name = module.autenticacion.idempotency_table_name
  idempotency_table_arn  = module.autenticacion.idempotency_table_arn
  common_layer_arn       = aws_lambda_layer_version.common.arn
  log_retention_days     = var.log_retention_days
  ses_sender_email       = var.ses_sender_email
  ses_override_recipient = var.ses_demo_recipient
  common_tags            = local.common_tags
}

module "reportes" {
  source = "./Modulos/Reportes"

  name_prefix         = local.name_prefix
  rest_api_id         = aws_api_gateway_rest_api.cloudshop.id
  root_resource_id    = aws_api_gateway_rest_api.cloudshop.root_resource_id
  execution_arn       = aws_api_gateway_rest_api.cloudshop.execution_arn
  stage_name          = var.api_stage_name
  orders_table_name   = module.pedidos.orders_table_name
  orders_table_arn    = module.pedidos.orders_table_arn
  products_table_name = module.productos.products_table_name
  products_table_arn  = module.productos.products_table_arn
  common_layer_arn    = aws_lambda_layer_version.common.arn
  log_retention_days  = var.log_retention_days
  common_tags         = local.common_tags
}

module "frontend" {
  source = "./Modulos/Frontend"

  name_prefix         = local.name_prefix
  aws_region          = var.aws_region
  api_url             = aws_api_gateway_stage.cloudshop.invoke_url
  user_pool_id        = module.autenticacion.user_pool_id
  user_pool_client_id = module.autenticacion.user_pool_client_id
  identity_pool_id    = module.autenticacion.identity_pool_id
  build_directory     = abspath("${path.root}/Modulos/Frontend/app/dist")
  common_tags         = local.common_tags
}
