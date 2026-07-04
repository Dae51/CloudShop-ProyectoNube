# archivo raiz de terraform


module "usuarios" {
  source = "./Modulos/Usuarios"

  rest_api_id      = aws_api_gateway_rest_api.cloudshop.id
  root_resource_id = aws_api_gateway_rest_api.cloudshop.root_resource_id
  execution_arn    = aws_api_gateway_rest_api.cloudshop.execution_arn
  stage_name       = var.api_stage_name
}

module "productos" {
  source = "./Modulos/Productos"

  rest_api_id      = aws_api_gateway_rest_api.cloudshop.id
  root_resource_id = aws_api_gateway_rest_api.cloudshop.root_resource_id
  execution_arn    = aws_api_gateway_rest_api.cloudshop.execution_arn
  stage_name       = var.api_stage_name
}
