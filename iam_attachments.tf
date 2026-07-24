resource "aws_iam_role_policy_attachment" "usuarios_identity" {
  for_each = module.usuarios.api_role_policy_arns

  role       = module.autenticacion.role_names[each.key]
  policy_arn = each.value
}

resource "aws_iam_role_policy_attachment" "productos_identity" {
  for_each = module.productos.api_role_policy_arns

  role       = module.autenticacion.role_names[upper(each.key)]
  policy_arn = each.value
}

resource "aws_iam_role_policy_attachment" "tiendas_identity" {
  for_each = module.tiendas.api_role_policy_arns

  role       = module.autenticacion.role_names[each.key]
  policy_arn = each.value
}

resource "aws_iam_role_policy_attachment" "carritos_identity" {
  for_each = module.carritos.api_role_policy_arns

  role       = module.autenticacion.role_names[each.key]
  policy_arn = each.value
}

resource "aws_iam_role_policy_attachment" "pedidos_identity" {
  for_each = module.pedidos.api_role_policy_arns

  role       = module.autenticacion.role_names[each.key]
  policy_arn = each.value
}

resource "aws_iam_role_policy_attachment" "reportes_identity" {
  for_each = module.reportes.api_role_policy_arns

  role       = module.autenticacion.role_names[each.key]
  policy_arn = each.value
}
