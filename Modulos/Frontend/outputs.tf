output "bucket_name" {
  description = "Nombre del bucket S3 del frontend"
  value       = aws_s3_bucket.frontend.bucket
}

output "cloudfront_distribution_id" {
  description = "ID de la distribucion CloudFront del frontend"
  value       = aws_cloudfront_distribution.frontend.id
}

output "cloudfront_distribution_arn" {
  description = "ARN de la distribucion CloudFront del frontend"
  value       = aws_cloudfront_distribution.frontend.arn
}

output "cloudfront_domain_name" {
  description = "Dominio CloudFront del frontend"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "frontend_url" {
  description = "URL HTTPS del frontend"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}
