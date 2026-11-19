
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):

    response = exception_handler(exc, context)

    if response is not None:

        custom_response = {
            "success": False,
            "message": "Request failed.",
            "errors": response.data
        }

        if response.status_code == 400:
            custom_response["message"] = "Validation failed."

        elif response.status_code == 401:
            custom_response["message"] = (
                "Authentication failed."
            )

        elif response.status_code == 403:
            custom_response["message"] = "Permission denied."

        elif response.status_code == 404:
            custom_response["message"] = "Resource not found."

        response.data = custom_response

    return response
