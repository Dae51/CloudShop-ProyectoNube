variable "api_gateway_stage_arns" {
  description = "ARNs de stages API Gateway que se asociaran al Web ACL regional"
  type        = map(string)
}

variable "rate_limit_requests_per_5_minutes" {
  description = "Cantidad maxima de requests por IP en una ventana de 5 minutos"
  type        = number
  default     = 2000
}
