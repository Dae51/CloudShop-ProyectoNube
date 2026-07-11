output "dashboard_name" {
  description = "Nombre del dashboard de CloudWatch"
  value       = aws_cloudwatch_dashboard.cloudshop.dashboard_name
}

output "api_gateway_cloudwatch_role_arn" {
  description = "ARN del rol usado por API Gateway para publicar logs en CloudWatch"
  value       = aws_iam_role.api_gateway_cloudwatch.arn
}

output "lambda_error_alarm_names" {
  description = "Nombres de alarmas de errores Lambda"
  value       = [for alarm in aws_cloudwatch_metric_alarm.lambda_errors : alarm.alarm_name]
}

output "api_5xx_alarm_names" {
  description = "Nombres de alarmas de errores 5XX API Gateway"
  value       = [for alarm in aws_cloudwatch_metric_alarm.api_5xx : alarm.alarm_name]
}

output "api_latency_alarm_names" {
  description = "Nombres de alarmas de latencia API Gateway"
  value       = [for alarm in aws_cloudwatch_metric_alarm.api_latency : alarm.alarm_name]
}

output "dynamodb_throttle_alarm_names" {
  description = "Nombres de alarmas de throttling DynamoDB"
  value = concat(
    [for alarm in aws_cloudwatch_metric_alarm.dynamodb_read_throttles : alarm.alarm_name],
    [for alarm in aws_cloudwatch_metric_alarm.dynamodb_write_throttles : alarm.alarm_name]
  )
}

