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

variable "ses_sender_email" {
  description = "Identidad SES remitente; vacío deja envío real deshabilitado"
  type        = string
  default     = ""

  validation {
    condition     = var.ses_sender_email == "" || can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", var.ses_sender_email))
    error_message = "ses_sender_email debe ser vacío o un email válido."
  }
}

variable "ses_demo_recipient" {
  description = "Destinatario verificado de demo en sandbox SES; vacío usa email del usuario"
  type        = string
  default     = ""

  validation {
    condition     = var.ses_demo_recipient == "" || can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", var.ses_demo_recipient))
    error_message = "ses_demo_recipient debe ser vacío o un email válido."
  }
}

variable "waf_rate_limit" {
  description = "Máximo de solicitudes por IP en una ventana de cinco minutos"
  type        = number
  default     = 500

  validation {
    condition     = var.waf_rate_limit >= 100 && var.waf_rate_limit <= 2000000000
    error_message = "waf_rate_limit debe estar entre 100 y 2,000,000,000."
  }
}
