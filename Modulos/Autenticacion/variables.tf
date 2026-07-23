variable "name_prefix" {
  description = "Prefijo único del proyecto y ambiente"
  type        = string
}

variable "environment" {
  description = "Ambiente de despliegue"
  type        = string
}

variable "log_retention_days" {
  description = "Retención de logs Lambda"
  type        = number
}

variable "common_tags" {
  description = "Tags comunes"
  type        = map(string)
  default     = {}
}
