variable "cart_table_name" {
  description = "Nombre de la tabla DynamoDB de carrito"
  type        = string
  default     = "CartItems"
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

