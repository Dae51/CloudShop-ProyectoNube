# Preserve an already-deployed Productos API when adopting the shared root API.
moved {
  from = module.productos.aws_api_gateway_rest_api.products
  to   = aws_api_gateway_rest_api.cloudshop
}

moved {
  from = module.productos.aws_api_gateway_deployment.products
  to   = aws_api_gateway_deployment.cloudshop
}

moved {
  from = module.productos.aws_api_gateway_stage.products
  to   = aws_api_gateway_stage.cloudshop
}

moved {
  from = module.usuarios.aws_dynamodb_table.users
  to   = module.autenticacion.aws_dynamodb_table.users
}

moved {
  from = module.productos.aws_api_gateway_resource.tiendas
  to   = module.tiendas.aws_api_gateway_resource.stores
}

moved {
  from = module.productos.aws_api_gateway_resource.store
  to   = module.tiendas.aws_api_gateway_resource.store
}
