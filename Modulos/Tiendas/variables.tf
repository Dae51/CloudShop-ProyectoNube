variable "stores_table_name" {
  description = "Nombre de la tabla DynamoDB de tiendas"
  type        = string
  default     = "Stores"
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

