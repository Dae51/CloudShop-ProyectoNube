output "stores_table_name" { value = aws_dynamodb_table.stores.name }
output "stores_table_arn" { value = aws_dynamodb_table.stores.arn }
output "lambda_function_name" { value = aws_lambda_function.lambda.function_name }
output "api_role_policy_arns" {
  value = { for role, policy in aws_iam_policy.api : role => policy.arn }
}
output "route_configuration_hash" {
  value = sha1(jsonencode({
    methods      = { for key, value in aws_api_gateway_method.route : key => value.id }
    integrations = { for key, value in aws_api_gateway_integration.route : key => value.id }
    cors         = { for key, value in aws_api_gateway_integration.options : key => value.id }
  }))
}
