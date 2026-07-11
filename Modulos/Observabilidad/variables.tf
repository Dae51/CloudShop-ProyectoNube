variable "lambda_function_names" {
  description = "Nombres de Lambdas a monitorear"
  type        = list(string)
}

variable "api_gateways" {
  description = "APIs REST Gateway a monitorear y configurar"
  type = list(object({
    name        = string
    rest_api_id = string
    stage_name  = string
  }))
}

variable "dynamodb_table_names" {
  description = "Tablas DynamoDB a monitorear"
  type        = list(string)
}

variable "alarm_actions" {
  description = "ARNs SNS u otros destinos para acciones de alarma"
  type        = list(string)
  default     = []
}

variable "ok_actions" {
  description = "ARNs SNS u otros destinos para acciones OK"
  type        = list(string)
  default     = []
}

variable "lambda_error_threshold" {
  description = "Cantidad de errores Lambda permitidos por periodo antes de alarmar"
  type        = number
  default     = 1
}

variable "api_5xx_threshold" {
  description = "Cantidad de errores 5XX de API Gateway permitidos por periodo antes de alarmar"
  type        = number
  default     = 1
}

variable "api_latency_threshold_ms" {
  description = "Latencia promedio de API Gateway en milisegundos antes de alarmar"
  type        = number
  default     = 2000
}

variable "dynamodb_throttle_threshold" {
  description = "Eventos de throttling DynamoDB permitidos por periodo antes de alarmar"
  type        = number
  default     = 1
}

variable "dashboard_name" {
  description = "Nombre del dashboard CloudWatch"
  type        = string
  default     = "cloudshop-observabilidad"
}

