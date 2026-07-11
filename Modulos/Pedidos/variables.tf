variable "orders_table_name" {
  description = "Nombre de la tabla DynamoDB de pedidos"
  type        = string
  default     = "Orders"
}

variable "orders_audit_table_name" {
  description = "Nombre de la tabla DynamoDB de auditoria de eventos de pedidos"
  type        = string
  default     = "OrderEventsAudit"
}

variable "products_table_name" {
  description = "Nombre de la tabla DynamoDB de productos usada para inventario"
  type        = string
  default     = "Products"
}

variable "event_bus_name" {
  description = "Nombre del bus custom de EventBridge para pedidos"
  type        = string
  default     = "cloudshop-pedidos-bus"
}

variable "stage_name" {
  description = "Stage de API Gateway"
  type        = string
  default     = "dev"
}

variable "log_retention_days" {
  description = "Retencion de logs de las Lambdas en CloudWatch"
  type        = number
  default     = 30
}

variable "ses_source_email" {
  description = "Correo verificado en SES usado como remitente"
  type        = string
  default     = "no-reply@cloudshop.local"
}

