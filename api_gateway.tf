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

resource "aws_api_gateway_gateway_response" "cors_errors" {
  for_each = {
    ACCESS_DENIED = "403"
    UNAUTHORIZED  = "401"
    DEFAULT_4XX   = "400"
    DEFAULT_5XX   = "500"
  }

  rest_api_id   = aws_api_gateway_rest_api.cloudshop.id
  response_type = each.key
  status_code   = each.value
  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"   = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers"  = "'Content-Type,Authorization,X-Amz-Date,X-Amz-Security-Token,X-Amz-Content-Sha256,X-Correlation-Id,Idempotency-Key'"
    "gatewayresponse.header.Access-Control-Expose-Headers" = "'X-Correlation-Id'"
    "gatewayresponse.header.X-Correlation-Id"              = "context.requestId"
  }
  response_templates = {
    "application/json" = jsonencode({
      error = {
        code          = each.key
        message       = "$context.error.messageString"
        correlationId = "$context.requestId"
      }
    })
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
      reportes  = module.reportes.route_configuration_hash
      errors    = { for key, value in aws_api_gateway_gateway_response.cors_errors : key => value.id }
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
    module.pedidos,
    module.reportes,
    aws_api_gateway_gateway_response.cors_errors
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
