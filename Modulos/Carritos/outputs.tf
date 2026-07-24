output "carts_table_name" { value = aws_dynamodb_table.carts.name }
output "carts_table_arn" { value = aws_dynamodb_table.carts.arn }
output "lambda_function_name" { value = aws_lambda_function.lambda.function_name }
output "api_role_policy_arns" { value = { CLIENTE = aws_iam_policy.cliente.arn } }
output "route_configuration_hash" {
  value = sha1(jsonencode({
    methods      = { for key, value in aws_api_gateway_method.route : key => value.id }
    integrations = { for key, value in aws_api_gateway_integration.route : key => value.id }
    cors         = { for key, value in aws_api_gateway_integration.options : key => value.id }
  }))
}
