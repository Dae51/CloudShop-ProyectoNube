resource "aws_api_gateway_rest_api" "cloudshop" {
  name        = "cloudshop-api"
  description = "API REST compartida de CloudShop Enterprise"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = {
    Project = "CloudShop"
  }
}

resource "aws_api_gateway_deployment" "cloudshop" {
  rest_api_id = aws_api_gateway_rest_api.cloudshop.id

  triggers = {
    redeployment = sha1(jsonencode({
      usuarios  = module.usuarios.route_configuration_hash
      productos = module.productos.route_configuration_hash
      tiendas   = module.tiendas.route_configuration_hash
      carritos  = module.carritos.route_configuration_hash
      pedidos   = module.pedidos.route_configuration_hash
    }))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    module.usuarios,
    module.productos,
    module.tiendas,
    module.carritos,
    module.pedidos
  ]
}

resource "aws_api_gateway_stage" "cloudshop" {
  deployment_id = aws_api_gateway_deployment.cloudshop.id
  rest_api_id   = aws_api_gateway_rest_api.cloudshop.id
  stage_name    = var.api_stage_name

  tags = {
    Project = "CloudShop"
  }
}
