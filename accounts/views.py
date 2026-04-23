from decouple import config
import requests
from django.http import JsonResponse
import json
from django.shortcuts import redirect
from accounts.models import GHLAuthCredentials
from django.views.decorators.csrf import csrf_exempt
import logging
from accounts import services






logger = logging.getLogger(__name__)

# Map GHL invoice webhook event types to local Invoice status values
INVOICE_EVENT_STATUS_MAP = {
    "InvoicePaid": "paid",
    "InvoicePartiallyPaid": "partially_paid",
    "InvoiceSent": "sent",
    "InvoiceVoid": "void",
}


GHL_CLIENT_ID = config("GHL_CLIENT_ID")
GHL_CLIENT_SECRET = config("GHL_CLIENT_SECRET")
GHL_REDIRECTED_URI = config("GHL_REDIRECTED_URI")

TOKEN_URL = "https://services.leadconnectorhq.com/oauth/token"
SCOPE = config("SCOPE")
GHL_VERSION_ID = config("GHL_VERSION_ID",default="")
def auth_connect(request):
    auth_url = ("https://marketplace.gohighlevel.com/oauth/chooselocation?response_type=code&"
                f"redirect_uri={GHL_REDIRECTED_URI}&"
                f"client_id={GHL_CLIENT_ID}&"
                f"scope={SCOPE}"
                f"{f'&version_id={GHL_VERSION_ID}' if GHL_VERSION_ID else ''}"
                )
    return redirect(auth_url)



def callback(request):
    
    code = request.GET.get('code')

    if not code:
        return JsonResponse({"error": "Authorization code not received from OAuth"}, status=400)

    return redirect(f'{config("BASE_URI")}/api/accounts/auth/tokens?code={code}')


def tokens(request):
    authorization_code = request.GET.get("code")

    if not authorization_code:
        return JsonResponse({"error": "Authorization code not found"}, status=400)

    data = {
        "grant_type": "authorization_code",
        "client_id": GHL_CLIENT_ID,
        "client_secret": GHL_CLIENT_SECRET,
        "redirect_uri": GHL_REDIRECTED_URI,
        "code": authorization_code,
    }

    response = requests.post(TOKEN_URL, data=data)

    try:
        response_data = response.json()
        if not response_data:
            return

        data = services.get_location_name(location_id=response_data.get("locationId"), access_token=response_data.get('access_token'))
        location_data = data.get("location")


        obj, created = GHLAuthCredentials.objects.update_or_create(
            location_id= response_data.get("locationId"),
            defaults={
                "access_token": response_data.get("access_token"),
                "refresh_token": response_data.get("refresh_token"),
                "expires_in": response_data.get("expires_in"),
                "scope": response_data.get("scope"),
                "user_type": response_data.get("userType"),
                "company_id": response_data.get("companyId"),
                "user_id":response_data.get("userId"),
                "location_name":location_data.get("name"),
                "timezone": location_data.get("timezone"),
                "business_email":location_data.get("email"),
                "business_phone":location_data.get("phone")
            }
        )
        from documents.account_library import (
            seed_account_document_library,
            seed_account_print_group_library,
        )

        seed_account_document_library(obj)
        seed_account_print_group_library(obj)
        services.sync_custom_fields_to_db(location_id=response_data.get("locationId"), access_token=response_data.get("access_token"))


    
        location_id = response_data.get("locationId")
        access_token = response_data.get("access_token")
        
        return JsonResponse({
            "message": "Authentication successful",
            "access_token": response_data.get('access_token'),
            "token_stored": True
        })
        
    except requests.exceptions.JSONDecodeError:
        return JsonResponse({
            "error": "Invalid JSON response from API",
            "status_code": response.status_code,
            "response_text": response.text[:500]
        }, status=500)