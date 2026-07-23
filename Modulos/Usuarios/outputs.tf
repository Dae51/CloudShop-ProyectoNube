output "lambda_function_name" {
  value = aws_lambda_function.usuarios_lambda.function_name
}

output "api_role_policy_arns" {
  value = { for role, policy in aws_iam_policy.api : role => policy.arn }
}

output "route_configuration_hash" {
  description = "Huella de rutas de Usuarios para el deployment compartido"
  value = sha1(jsonencode({
    resources = {
      usuarios = aws_api_gateway_resource.usuarios.id
      user     = aws_api_gateway_resource.user.id
      role     = aws_api_gateway_resource.role.id
    }
    methods = {
      for key, method in aws_api_gateway_method.usuarios : key => {
        id            = method.id
        http_method   = method.http_method
        authorization = method.authorization
        resource_id   = method.resource_id
      }
    }
    integrations = {
      for key, integration in aws_api_gateway_integration.usuarios : key => {
        id                      = integration.id
        type                    = integration.type
        integration_http_method = integration.integration_http_method
        uri                     = integration.uri
      }
    }
    cors = {
      for key, integration in aws_api_gateway_integration.options : key => integration.id
    }
  }))
}
