output "orders_table_name" { value = aws_dynamodb_table.orders.name }
output "orders_table_arn" { value = aws_dynamodb_table.orders.arn }
output "outbox_table_name" { value = aws_dynamodb_table.outbox.name }
output "event_bus_name" { value = aws_cloudwatch_event_bus.orders.name }
output "event_dlq_url" { value = aws_sqs_queue.event_dlq.url }
output "lambda_function_name" { value = aws_lambda_function.orders.function_name }
output "relay_lambda_name" { value = aws_lambda_function.relay.function_name }
output "notification_lambda_name" { value = aws_lambda_function.notification.function_name }
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
