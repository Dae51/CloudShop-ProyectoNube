variable "products_table_name" {
  description = "Nombre de la tabla DynamoDB de productos"
  type        = string
  default     = "Products"
}

variable "rest_api_id" {
  description = "ID de la API Gateway REST compartida"
  type        = string
}

variable "root_resource_id" {
  description = "ID del recurso raíz de la API compartida"
  type        = string
}

variable "execution_arn" {
  description = "ARN de ejecución de la API compartida"
  type        = string
}

variable "audit_table_name" {
  description = "Nombre de la tabla DynamoDB de auditoría de productos"
  type        = string
  default     = "ProductAudit"
}

variable "stage_name" {
  description = "Stage compartido de API Gateway"
  type        = string
}

variable "log_retention_days" {
  description = "Retención de logs de la Lambda en CloudWatch"
  type        = number
  default     = 30
}
