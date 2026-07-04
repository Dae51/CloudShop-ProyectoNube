variable "products_table_name" {
  description = "Nombre de la tabla DynamoDB de productos"
  type        = string
  default     = "Products"
}

variable "audit_table_name" {
  description = "Nombre de la tabla DynamoDB de auditoría de productos"
  type        = string
  default     = "ProductAudit"
}

variable "stage_name" {
  description = "Stage de API Gateway"
  type        = string
  default     = "dev"
}

variable "log_retention_days" {
  description = "Retención de logs de la Lambda en CloudWatch"
  type        = number
  default     = 30
}
