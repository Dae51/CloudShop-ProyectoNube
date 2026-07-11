output "api_url" {
  description = "URL base de la API de reportes"
  value       = aws_api_gateway_stage.reports.invoke_url
}

output "api_stage_arn" {
  description = "ARN del stage de API Gateway de reportes"
  value       = aws_api_gateway_stage.reports.arn
}

output "api_name" {
  description = "Nombre de la API Gateway de reportes"
  value       = aws_api_gateway_rest_api.reports.name
}

output "api_rest_api_id" {
  description = "ID de REST API Gateway de reportes"
  value       = aws_api_gateway_rest_api.reports.id
}

output "api_stage_name" {
  description = "Nombre del stage de API Gateway de reportes"
  value       = aws_api_gateway_stage.reports.stage_name
}

output "reports_lambda_name" {
  description = "Nombre de la Lambda de reportes"
  value       = aws_lambda_function.reports.function_name
}

output "api_role_policy_arn" {
  description = "Politica para adjuntar a roles empresariales que consumen reportes"
  value       = aws_iam_policy.reports_api_ejecutivo.arn
}
