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

variable "stage_name" {
  description = "Stage compartido de API Gateway"
  type        = string
}
