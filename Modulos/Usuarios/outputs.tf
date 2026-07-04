output "route_configuration_hash" {
  description = "Huella de la ruta de Usuarios usada por el deployment compartido"
  value = sha1(jsonencode({
    resource = {
      id        = aws_api_gateway_resource.users.id
      path_part = aws_api_gateway_resource.users.path_part
    }
    method = {
      id            = aws_api_gateway_method.get_users.id
      http_method   = aws_api_gateway_method.get_users.http_method
      authorization = aws_api_gateway_method.get_users.authorization
      resource_id   = aws_api_gateway_method.get_users.resource_id
    }
    integration = {
      id                      = aws_api_gateway_integration.get_users.id
      type                    = aws_api_gateway_integration.get_users.type
      integration_http_method = aws_api_gateway_integration.get_users.integration_http_method
      uri                     = aws_api_gateway_integration.get_users.uri
    }
    lambda_permission = aws_lambda_permission.api_gateway.source_arn
  }))
}
