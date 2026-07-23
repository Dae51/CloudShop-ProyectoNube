variable "api_stage_name" {
  description = "Nombre del stage compartido de API Gateway"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Nombre corto del proyecto"
  type        = string
  default     = "cloudshop"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.project_name))
    error_message = "project_name debe usar minúsculas, números y guiones."
  }
}

variable "environment" {
  description = "Ambiente de despliegue"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "environment debe ser dev, test o prod."
  }
}

variable "aws_region" {
  description = "Región principal del proyecto"
  type        = string
  default     = "us-east-1"
}

variable "log_retention_days" {
  description = "Retención de logs CloudWatch"
  type        = number
  default     = 30

  validation {
    condition     = contains([14, 30, 60, 90, 120, 150, 180, 365], var.log_retention_days)
    error_message = "Seleccione un período de retención soportado."
  }
}
