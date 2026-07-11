variable "bucket_name" {
  description = "Nombre opcional del bucket S3 del frontend. Si se omite, se genera uno por cuenta y region."
  type        = string
  default     = ""
}

variable "environment" {
  description = "Nombre visible del ambiente"
  type        = string
  default     = "dev"
}

variable "usuarios_api_url" {
  description = "URL base de la API de usuarios"
  type        = string
}

variable "productos_api_url" {
  description = "URL base de la API de productos"
  type        = string
}

variable "tiendas_api_url" {
  description = "URL base de la API de tiendas"
  type        = string
}

variable "compras_api_url" {
  description = "URL base de la API de carrito"
  type        = string
}

variable "pedidos_api_url" {
  description = "URL base de la API de pedidos"
  type        = string
}

variable "reportes_api_url" {
  description = "URL base de la API de reportes"
  type        = string
}

variable "cloudfront_web_acl_arn" {
  description = "ARN del Web ACL WAF global asociado a CloudFront"
  type        = string
  default     = null
}
