variable "users_table_name" {
  description = "Nombre de la tabla DynamoDB de usuarios"
  type        = string
  default     = "Users"
}

variable "user_audit_table_name" {
  description = "Nombre de la tabla DynamoDB de auditoria de usuarios"
  type        = string
  default     = "UserAudit"
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
