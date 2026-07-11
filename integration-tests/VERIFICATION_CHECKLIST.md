# Verification Checklist

## Case 1: Unauthorized Access

- [ ] Unauthorized identity exists.
- [ ] Unauthorized identity does not have `execute-api:Invoke` for `POST /productos`.
- [ ] Request is signed with unauthorized identity.
- [ ] API returns `403 Forbidden`.
- [ ] API Gateway execution logs show the failed authorization attempt.
- [ ] Evidence file `case1-unauthorized-access` is generated.

## Case 2: Complete Order Flow

- [ ] Admin identity can invoke `POST /productos`.
- [ ] Test product is created with inventory greater than zero.
- [ ] Admin identity can invoke `POST /pedidos`.
- [ ] Order creation returns `201 Created`.
- [ ] Order exists in `Orders`.
- [ ] Order has `eventPublicationStatus = PUBLICADO`.
- [ ] Product inventory is decreased by the inventory consumer.
- [ ] `OrderEventsAudit` contains a record for the order id.
- [ ] Email Lambda logs contain the order id.
- [ ] SES source email is verified.
- [ ] SES recipient is verified if the account is in sandbox mode.
- [ ] Evidence file `case2-complete-order-flow` is generated.

## Case 3: CloudWatch Monitoring

- [ ] Lambda log groups exist for every Lambda.
- [ ] API Gateway detailed metrics/logging are enabled.
- [ ] Lambda error metrics can be queried.
- [ ] API Gateway request metrics can be queried.
- [ ] API Gateway 5XX metrics can be queried.
- [ ] Dashboard `cloudshop-observabilidad` exists.
- [ ] Alarms with prefix `cloudshop` exist.
- [ ] Evidence file `case3-cloudwatch-monitoring` is generated.

## Case 4: Terraform Deployment

- [ ] No resources are created manually.
- [ ] `terraform fmt -recursive -check` passes.
- [ ] `terraform init` passes.
- [ ] `terraform validate` passes.
- [ ] `terraform plan -out cloudshop.tfplan` passes.
- [ ] Optional `terraform apply -auto-approve cloudshop.tfplan` passes.
- [ ] Terraform outputs include API URLs and frontend URL.
- [ ] Evidence file `case4-terraform-deployment` is generated.

