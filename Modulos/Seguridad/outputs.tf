output "cloudfront_web_acl_arn" {
  description = "ARN del Web ACL global para CloudFront"
  value       = aws_wafv2_web_acl.cloudfront.arn
}

output "api_gateway_web_acl_arn" {
  description = "ARN del Web ACL regional para API Gateway"
  value       = aws_wafv2_web_acl.api_gateway.arn
}

output "api_gateway_web_acl_association_count" {
  description = "Cantidad de stages API Gateway asociados al Web ACL regional"
  value       = length(aws_wafv2_web_acl_association.api_gateway)
}

