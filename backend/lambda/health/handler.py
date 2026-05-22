from common.response import json_response

SERVICE_NAME = "aws-ai-platform-api"
SERVICE_VERSION = "0.1.0"


def lambda_handler(event, context):
    return json_response(
        200,
        {
            "status": "ok",
            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
        },
    )
