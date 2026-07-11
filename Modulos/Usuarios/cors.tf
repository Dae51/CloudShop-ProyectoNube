locals {
  cors_response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,Accept'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,DELETE,OPTIONS'"
  }

  cors_auth_response_types = toset([
    "ACCESS_DENIED",
    "UNAUTHORIZED",
    "MISSING_AUTHENTICATION_TOKEN",
    "INVALID_SIGNATURE",
    "EXPIRED_TOKEN"
  ])
}

resource "aws_api_gateway_gateway_response" "default_4xx" {
  rest_api_id         = aws_api_gateway_rest_api.usuarios.id
  response_type       = "DEFAULT_4XX"
  response_parameters = local.cors_response_parameters
}

resource "aws_api_gateway_gateway_response" "default_5xx" {
  rest_api_id         = aws_api_gateway_rest_api.usuarios.id
  response_type       = "DEFAULT_5XX"
  response_parameters = local.cors_response_parameters
}

resource "aws_api_gateway_gateway_response" "auth_4xx" {
  for_each = local.cors_auth_response_types

  rest_api_id         = aws_api_gateway_rest_api.usuarios.id
  response_type       = each.value
  response_parameters = local.cors_response_parameters
}
