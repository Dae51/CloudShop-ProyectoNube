variable "name_prefix" {
  description = "Prefijo estable para recursos del frontend"
  type        = string
}

variable "aws_region" {
  description = "Región de S3, API y Cognito"
  type        = string
}

variable "api_url" {
  description = "URL base real de API Gateway"
  type        = string
}

variable "user_pool_id" {
  description = "ID del Cognito User Pool"
  type        = string
}

variable "user_pool_client_id" {
  description = "ID del cliente web público de Cognito"
  type        = string
}

variable "identity_pool_id" {
  description = "ID del Cognito Identity Pool"
  type        = string
}

variable "build_directory" {
  description = "Ruta absoluta del build Vite validado"
  type        = string

  validation {
    condition     = fileexists("${var.build_directory}/index.html")
    error_message = "Ejecute npm ci y npm run build en Modulos/Frontend/app antes de Terraform."
  }
}

variable "common_tags" {
  description = "Etiquetas comunes"
  type        = map(string)
}
