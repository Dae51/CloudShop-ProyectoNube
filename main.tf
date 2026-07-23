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
