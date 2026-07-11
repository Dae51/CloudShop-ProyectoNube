# CloudShop Enterprise Integration Evidence

This folder contains automated scripts and evidence templates for the mandatory project use cases.

The scripts run against a real deployed CloudShop environment. They do not create AWS resources manually; application infrastructure must come from Terraform.

## Prerequisites

- Terraform installed.
- AWS CLI installed and authenticated.
- CloudShop infrastructure deployed with `terraform apply`.
- API Gateway endpoints using `AWS_IAM`.
- API Gateway detailed logging enabled by the Observabilidad module.
- SES source identity verified.
- If SES is in sandbox mode, the recipient in `testData.order.customerEmail` must also be verified.
- Two AWS identities:
  - `profiles.admin`: allowed to invoke admin endpoints and read verification evidence.
  - `profiles.unauthorized`: intentionally missing permission for `POST /productos`.

Static AWS credentials can also be provided with environment variables:

```powershell
$env:CLOUDSHOP_ADMIN_AWS_ACCESS_KEY_ID="..."
$env:CLOUDSHOP_ADMIN_AWS_SECRET_ACCESS_KEY="..."
$env:CLOUDSHOP_ADMIN_AWS_SESSION_TOKEN="..."
$env:CLOUDSHOP_UNAUTHORIZED_AWS_ACCESS_KEY_ID="..."
$env:CLOUDSHOP_UNAUTHORIZED_AWS_SECRET_ACCESS_KEY="..."
$env:CLOUDSHOP_UNAUTHORIZED_AWS_SESSION_TOKEN="..."
```

## Configuration

Copy `cloudshop-test-config.example.json` to `cloudshop-test-config.local.json` and adjust:

- `region`
- `profiles.admin`
- `profiles.unauthorized`
- `testData.order.customerEmail`
- API URLs, if `terraform output -json` is not available

When Terraform state is available, the script reads API URLs and dashboard name from `terraform output -json`.

## Run

```powershell
cd .\integration-tests
.\run-integration-tests.ps1 -Config .\cloudshop-test-config.local.json -Case all
```

Run a single case:

```powershell
.\run-integration-tests.ps1 -Config .\cloudshop-test-config.local.json -Case case2
```

Allow Terraform apply during Case 4:

```powershell
.\run-integration-tests.ps1 -Config .\cloudshop-test-config.local.json -Case case4 -Apply
```

Without `-Apply`, Case 4 runs `fmt`, `init`, `validate`, and `plan`.

## Evidence

Every run writes JSON evidence into `integration-tests/evidence`.

Evidence files include:

- API requests and responses
- DynamoDB verification records
- EventBridge workflow evidence
- Lambda logs
- API Gateway logs
- CloudWatch metrics
- Dashboard and alarm status
- Terraform command outputs

## Case 1: Unauthorized Access

Scenario:

- The unauthorized profile signs a request to `POST /productos`.
- This endpoint is treated as administrator-only through IAM `execute-api:Invoke` policies.
- API Gateway must reject the request before it reaches the Lambda.

Expected result:

```json
{
  "status": 403
}
```

Evidence:

- HTTP 403 response
- API Gateway execution log group:
  `API-Gateway-Execution-Logs_<productos-rest-api-id>/dev`

## Case 2: Complete Order Flow

Scenario:

1. Create a product with inventory.
2. Create an order using that product.
3. Verify the order is stored in DynamoDB.
4. Verify `eventPublicationStatus` is `PUBLICADO`.
5. Verify the inventory consumer discounted stock.
6. Verify the audit consumer wrote an item in `OrderEventsAudit`.
7. Verify the email consumer logged a successful SES send.
8. Display execution logs from all Lambdas in the workflow.

Expected order creation response:

```json
{
  "status": 201,
  "body": {
    "data": {
      "orderId": "uuid",
      "eventPublicationStatus": "PUBLICADO",
      "inventoryStatus": "PENDIENTE"
    }
  }
}
```

Expected asynchronous evidence:

- `Orders` contains the order.
- `Products.inventory` is lower than the initial inventory.
- `OrderEventsAudit` contains at least one item for the order.
- `/aws/lambda/pedidos-correo-consumer-lambda` contains the order id.

## Case 3: CloudWatch Monitoring

Scenario:

- Query Lambda logs.
- Query API Gateway request and error metrics.
- Query Lambda error metrics.
- Fetch the CloudWatch dashboard.
- Fetch alarm status with prefix `cloudshop`.

Expected evidence:

- Dashboard `cloudshop-observabilidad` exists.
- CloudWatch alarms are returned.
- Metrics calls return datapoints or empty datapoint arrays without API errors.

## Case 4: Terraform Deployment

Scenario:

- Run Terraform commands from the project root:
  - `terraform fmt -recursive -check`
  - `terraform init`
  - `terraform validate`
  - `terraform plan -out cloudshop.tfplan`
  - optionally `terraform apply -auto-approve cloudshop.tfplan`

Expected evidence:

- Every command exits with code `0`.
- Terraform outputs include API URLs and frontend URL after apply.
- No manual AWS console resource creation is required.

