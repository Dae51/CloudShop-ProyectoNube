output "bucket_name" {
  description = "Bucket privado del build estático"
  value       = aws_s3_bucket.frontend.id
}

output "distribution_id" {
  description = "ID de la distribución CloudFront"
  value       = aws_cloudfront_distribution.frontend.id
}

output "distribution_arn" {
  description = "ARN de la distribución CloudFront"
  value       = aws_cloudfront_distribution.frontend.arn
}

output "url" {
  description = "URL HTTPS del frontend"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}
