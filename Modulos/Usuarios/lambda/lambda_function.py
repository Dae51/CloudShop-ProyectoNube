import json
import boto3
import uuid
from datetime import datetime

dynamodb = boto3.resource("dynamodb")

table = dynamodb.Table("Users")


def response(code, body):
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }


def lambda_handler(event, context):

    method = event["httpMethod"]

    if method == "POST":

        body = json.loads(event["body"])

        item = {

            "userId": str(uuid.uuid4()),
            "name": body["name"],
            "email": body["email"],
            "role": body["role"],
            "status": "ACTIVE",
            "createdAt": datetime.utcnow().isoformat()

        }

        table.put_item(Item=item)

        return response(201, item)

    elif method == "GET":

        users = table.scan()

        return response(200, users["Items"])

    elif method == "PUT":

        return response(200, {
            "message": "Actualizar usuario"
        })

    elif method == "DELETE":

        return response(200, {
            "message": "Desactivar usuario"
        })

    return response(400, {
        "message": "Método no soportado"
    })