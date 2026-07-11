variable "orders_table_name" {
  description = "Nombre de la tabla DynamoDB de pedidos existente"
  type        = string
  default     = "Orders"
}

variable "products_table_name" {
  description = "Nombre de la tabla DynamoDB de productos existente"
  type        = string
  default     = "Products"
}

variable "orders_status_index_name" {
  description = "Nombre del indice de pedidos por estado"
  type        = string
  default     = "StatusCreatedAtIndex"
}

variable "stage_name" {
  description = "Stage de API Gateway"
  type        = string
  default     = "dev"
}

variable "log_retention_days" {
  description = "Retencion de logs de la Lambda en CloudWatch"
  type        = number
  default     = 30
}

