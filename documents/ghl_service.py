"""
GoHighLevel (GHL) Media API service.
Uploads files to GHL instead of storing on server; update/delete via GHL API.
"""
import requests
from django.conf import settings

GHL_UPLOAD_URL = "https://services.leadconnectorhq.com/medias/upload-file"
GHL_MEDIA_BASE = "https://services.leadconnectorhq.com/medias"
GHL_VERSION = "2021-07-28"


def _auth_headers():
    token = getattr(settings, "GHL_ACCESS_TOKEN", None) or ""
    return {
        "Accept": "application/json",
        "Version": GHL_VERSION,
        "Authorization": f"Bearer {token}",
    }


def upload_file(file, name, parent_id=None):
    """
    Upload a file to GHL media.
    :param file: Django UploadedFile (request.FILES['file'])
    :param name: Display name for the file
    :param parent_id: GHL parentId (folder/location). Uses settings.GHL_PARENT_ID if None.
    :return: dict with fileId, url, traceId
    """
    parent_id = parent_id or getattr(settings, "GHL_PARENT_ID", "") or ""
    headers = _auth_headers()

    files = {
        "file": (file.name or "document", file, getattr(file, "content_type", "application/octet-stream")),
    }
    data = {
        "parentId": parent_id,
        "name": name,
    }

    resp = requests.post(GHL_UPLOAD_URL, headers=headers, data=data, files=files, timeout=60)
    resp.raise_for_status()
    result = resp.json()
    return {
        "fileId": result.get("fileId"),
        "url": result.get("url"),
        "traceId": result.get("traceId"),
    }


def update_media(document_id, name=None, alt_type=None, alt_id=None):
    """
    Update a media document in GHL.
    PATCH /medias/{document_id}
    """
    headers = _auth_headers()
    headers["Content-Type"] = "application/json"
    url = f"{GHL_MEDIA_BASE}/{document_id}"
    payload = {}
    if name is not None:
        payload["name"] = name
    if alt_type is not None:
        payload["altType"] = alt_type
    if alt_id is not None:
        payload["altId"] = alt_id
    if not payload:
        return
    resp = requests.patch(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()


def delete_media(document_id, alt_type=None, alt_id=None):
    """
    Delete a media document from GHL.
    DELETE /medias/{document_id}?altType=...&altId=...
    """
    headers = _auth_headers()
    url = f"{GHL_MEDIA_BASE}/{document_id}"
    params = {}
    if alt_type is not None:
        params["altType"] = alt_type
    if alt_id is not None:
        params["altId"] = alt_id
    resp = requests.delete(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()


GHL_OPPORTUNITIES_BASE = "https://services.leadconnectorhq.com/opportunities"
GHL_CONTACTS_BASE = "https://services.leadconnectorhq.com/contacts"


def get_opportunity(opportunity_id):
    """
    Fetch a single opportunity from GHL by ID.
    GET /opportunities/{opportunity_id}
    :return: dict with 'opportunity' (e.g. id, name, contactId, ...)
    """
    headers = _auth_headers()
    url = f"{GHL_OPPORTUNITIES_BASE}/{opportunity_id}"
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def create_contact_note(contact_id, body):
    """
    Create a note on a GHL contact.
    POST /contacts/{contact_id}/notes
    :param contact_id: GHL contact ID
    :param body: note body text
    :return: dict from API (e.g. note id, etc.)
    """
    headers = _auth_headers()
    headers["Content-Type"] = "application/json"
    url = f"{GHL_CONTACTS_BASE}/{contact_id}/notes"
    payload = {"body": body}
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json() if resp.content else {}
