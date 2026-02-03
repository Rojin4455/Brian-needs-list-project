from django.http import JsonResponse, Http404, HttpResponse
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import json
from io import BytesIO
import html
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib import colors
from .models import Category, Document, PrintGroup, DocumentRequest, AdminDocumentSelection, UserDocumentUpload


@require_http_methods(["GET"])
def get_categories(request):
    """
    API endpoint to get all categories
    GET /api/categories/
    """
    categories = Category.objects.all()
    data = [
        {
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'created_at': category.created_at.isoformat() if category.created_at else None,
            'updated_at': category.updated_at.isoformat() if category.updated_at else None,
        }
        for category in categories
    ]
    return JsonResponse({'categories': data}, safe=False)


@csrf_exempt
@require_http_methods(["POST"])
def create_category(request):
    """
    API endpoint to create a new category
    POST /api/categories/create/
    Body: JSON with name and description (optional)
    """
    try:
        data = json.loads(request.body)
        name = data.get('name')
        description = data.get('description', '')
        
        if not name:
            return JsonResponse({'error': 'Missing required field: name'}, status=400)
        
        # Check if category already exists
        if Category.objects.filter(name=name).exists():
            return JsonResponse({'error': 'Category with this name already exists'}, status=400)
        
        # Create the category
        category = Category.objects.create(
            name=name,
            description=description or f'Category: {name}'
        )
        
        return JsonResponse({
            'success': True,
            'category': {
                'id': category.id,
                'name': category.name,
                'description': category.description,
            }
        }, status=201)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def get_documents(request):
    """
    API endpoint to get all documents
    GET /api/documents/
    
    Query parameters:
    - category_id: Filter by category ID (optional)
    - print_group_id: Filter by print group ID (optional)
    """
    documents = Document.objects.select_related('category').prefetch_related('print_groups').all()
    
    # Filter by category if provided
    category_id = request.GET.get('category_id')
    if category_id:
        documents = documents.filter(category_id=category_id)
    
    # Filter by print group if provided
    print_group_id = request.GET.get('print_group_id')
    if print_group_id:
        documents = documents.filter(print_groups__id=print_group_id).distinct()
    
    data = [
        {
            'id': document.id,
            'name': document.name,
            'description': document.description,
            'category': {
                'id': document.category.id,
                'name': document.category.name,
            },
            'print_groups': [
                {
                    'id': pg.id,
                    'name': pg.name,
                }
                for pg in document.print_groups.all()
            ],
            'file': document.file.url if document.file else None,
            'file_name': document.file.name.split('/')[-1] if document.file else None,
            'created_at': document.created_at.isoformat() if document.created_at else None,
            'updated_at': document.updated_at.isoformat() if document.updated_at else None,
        }
        for document in documents
    ]
    return JsonResponse({'documents': data}, safe=False)


@require_http_methods(["GET"])
def get_print_groups(request):
    """
    API endpoint to get all print groups
    GET /api/print-groups/
    
    Query parameters:
    - document_id: Filter by document ID to get print groups for a specific document (optional)
    """
    print_groups = PrintGroup.objects.all()
    
    # Filter by document if provided
    document_id = request.GET.get('document_id')
    if document_id:
        print_groups = print_groups.filter(documents__id=document_id).distinct()
    
    data = [
        {
            'id': pg.id,
            'name': pg.name,
            'description': pg.description,
            'created_at': pg.created_at.isoformat() if pg.created_at else None,
            'updated_at': pg.updated_at.isoformat() if pg.updated_at else None,
        }
        for pg in print_groups
    ]
    return JsonResponse({'print_groups': data}, safe=False)


def homepage(request, request_id):
    """
    Homepage view with 3 card options for admin
    """
    # Get or create the document request
    doc_request, created = DocumentRequest.objects.get_or_create(request_id=request_id)
    
    context = {
        'request_id': request_id,
    }
    return render(request, 'documents/homepage.html', context)


def admin_user_uploads_view(request, request_id):
    """
    Admin view page to see all user uploads and accept/reject them.
    URL: {request_id}/request/admin/uploads/
    If no document list exists yet, shows a friendly "create the list first" page instead of 404.
    """
    try:
        doc_request = DocumentRequest.objects.get(request_id=request_id)
    except DocumentRequest.DoesNotExist:
        return render(request, 'documents/request_not_found.html', {'request_id': request_id})
    adhoc_docs, individual_docs, needs_list_docs = _build_request_document_data(doc_request)
    context = {
        'request_id': request_id,
        'adhoc_documents': adhoc_docs,
        'individual_documents': individual_docs,
        'needs_list_documents': needs_list_docs,
    }
    return render(request, 'documents/admin_user_uploads.html', context)


def _build_request_document_data(doc_request):
    """Build adhoc_docs, individual_docs, needs_list_docs for a document request (shared for PDF and pages)."""
    selections = AdminDocumentSelection.objects.filter(
        request=doc_request
    ).select_related('document', 'print_group').prefetch_related('user_uploads')

    adhoc_docs = []
    individual_docs = []
    needs_list_docs = {}

    for selection in selections:
        doc_data = {
            'selection_id': selection.id,
            'document_id': selection.document.id,
            'document_name': selection.document.name,
            'document_description': selection.document.description,
            'uploads': [
                {
                    'id': upload.id,
                    'file_url': upload.get_file_url(),
                    'file_name': upload.get_file_name(),
                    'uploaded_at': upload.uploaded_at,
                    'accepted': upload.accepted,
                    'accepted_at': upload.accepted_at,
                }
                for upload in selection.user_uploads.all()
            ]
        }
        if selection.section_type == 'adhoc':
            adhoc_docs.append(doc_data)
        elif selection.section_type == 'individual':
            individual_docs.append(doc_data)
        elif selection.section_type == 'needs_list':
            print_group_name = selection.print_group.name if selection.print_group else 'Unknown'
            if print_group_name not in needs_list_docs:
                needs_list_docs[print_group_name] = []
            needs_list_docs[print_group_name].append(doc_data)

    return adhoc_docs, individual_docs, needs_list_docs


@require_http_methods(["GET"])
def download_request_pdf(request, request_id):
    """
    Download a PDF of the document request list: admin-requested documents with descriptions,
    and for each document any user uploads (file name + View link).
    URL: {request_id}/download-pdf/
    """
    try:
        doc_request = DocumentRequest.objects.get(request_id=request_id)
    except DocumentRequest.DoesNotExist:
        raise Http404("Request not found")

    adhoc_docs, individual_docs, needs_list_docs = _build_request_document_data(doc_request)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=inch, leftMargin=inch, topMargin=inch, bottomMargin=inch
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'], fontSize=16, spaceAfter=12
    )
    heading_style = ParagraphStyle(
        'SectionHeading', parent=styles['Heading2'], fontSize=12, spaceAfter=8, spaceBefore=12
    )
    body_style = styles['Normal']
    small_style = ParagraphStyle(
        'Small', parent=styles['Normal'], fontSize=9, spaceAfter=4, leftIndent=12
    )
    link_style = ParagraphStyle(
        'Link', parent=styles['Normal'], fontSize=9, spaceAfter=4, leftIndent=24, textColor=colors.HexColor('#1565c0')
    )

    story = []
    story.append(Paragraph(f"Document Request – {html.escape(request_id)}", title_style))
    story.append(Spacer(1, 0.2 * inch))

    def add_doc_list(docs, section_title):
        if not docs:
            return
        story.append(Paragraph(html.escape(section_title), heading_style))
        for d in docs:
            doc_name = html.escape(d['document_name'] or 'Document')
            story.append(Paragraph(f"<b>{doc_name}</b>", body_style))
            desc = d.get('document_description') or ''
            desc_short = desc[:500] + ("..." if len(desc) > 500 else "")
            story.append(Paragraph(html.escape(desc_short), small_style))
            if d['uploads']:
                for u in d['uploads']:
                    name = html.escape(u.get('file_name') or 'Uploaded file')
                    story.append(Paragraph(f"• {name}", small_style))
                    url = u.get('file_url')
                    if url:
                        story.append(Paragraph(f'View: <a href="{html.escape(url)}">{html.escape(url)}</a>', link_style))
            else:
                story.append(Paragraph("No uploads yet", small_style))
            story.append(Spacer(1, 0.1 * inch))
        story.append(Spacer(1, 0.15 * inch))

    add_doc_list(adhoc_docs, "AD HOC Documents")
    add_doc_list(individual_docs, "Individual Documents")
    for pg_name, docs in sorted(needs_list_docs.items()):
        add_doc_list(docs, f"Needs List – {pg_name}")

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="document-request-{request_id}.pdf"'
    return response


def adhoc_page(request, request_id):
    """
    AD HOC - Request a custom document page
    """
    # Get or create the document request
    doc_request, created = DocumentRequest.objects.get_or_create(request_id=request_id)
    
    # Load existing custom documents for adhoc section
    existing_selections = AdminDocumentSelection.objects.filter(
        request=doc_request,
        section_type='adhoc'
    ).select_related('document', 'document__category')
    
    # Get all categories for the form
    categories = Category.objects.all()
    
    import json as json_module
    context = {
        'request_id': request_id,
        'categories': categories,
        'existing_custom_documents': [
            {
                'id': sel.id,
                'document_id': sel.document.id,
                'name': sel.document.name,
                'description': sel.document.description,
                'category_id': sel.document.category.id,
                'category_name': sel.document.category.name,
            }
            for sel in existing_selections
        ],
    }
    return render(request, 'documents/adhoc.html', context)


def individual_documents_page(request, request_id):
    """
    Individual Documents - Request individual document(s) page
    """
    # Get or create the document request
    doc_request, created = DocumentRequest.objects.get_or_create(request_id=request_id)
    
    # Load existing selections for individual section
    existing_selections = AdminDocumentSelection.objects.filter(
        request=doc_request,
        section_type='individual'
    ).select_related('document', 'document__category')
    
    selected_document_ids = [sel.document.id for sel in existing_selections]
    
    # Get all categories for custom document creation
    categories = Category.objects.all()
    
    import json as json_module
    context = {
        'request_id': request_id,
        'selected_document_ids': json_module.dumps(selected_document_ids),
        'categories': categories,
        'existing_custom_documents': [
            {
                'id': sel.id,
                'document_id': sel.document.id,
                'name': sel.document.name,
                'description': sel.document.description,
                'category_id': sel.document.category.id,
                'category_name': sel.document.category.name,
            }
            for sel in existing_selections
        ],
    }
    return render(request, 'documents/individual_documents.html', context)


def needs_list_page(request, request_id):
    """
    Needs List - Request needs list page
    """
    # Get or create the document request
    doc_request, created = DocumentRequest.objects.get_or_create(request_id=request_id)
    
    # Load existing selections for needs_list section
    existing_selections = AdminDocumentSelection.objects.filter(
        request=doc_request,
        section_type='needs_list'
    ).select_related('document', 'print_group', 'document__category')
    
    # Group by print group
    selected_by_print_group = {}
    custom_print_groups = []
    for sel in existing_selections:
        pg_id = sel.print_group.id if sel.print_group else None
        pg_key = str(pg_id) if pg_id else 'null'
        if pg_key not in selected_by_print_group:
            selected_by_print_group[pg_key] = []
        selected_by_print_group[pg_key].append(sel.document.id)
        
        # Collect custom print groups and their documents
        if sel.print_group:
            pg_exists = any(pg['id'] == sel.print_group.id for pg in custom_print_groups)
            if not pg_exists:
                custom_print_groups.append({
                    'id': sel.print_group.id,
                    'name': sel.print_group.name,
                    'documents': []
                })
            # Add document to the print group
            for pg in custom_print_groups:
                if pg['id'] == sel.print_group.id:
                    pg['documents'].append({
                        'selection_id': sel.id,
                        'document_id': sel.document.id,
                        'name': sel.document.name,
                        'description': sel.document.description,
                        'category_id': sel.document.category.id,
                        'category_name': sel.document.category.name,
                    })
                    break
    
    # Get all categories and print groups for custom creation
    categories = Category.objects.all()
    all_print_groups = PrintGroup.objects.all()
    
    import json as json_module
    context = {
        'request_id': request_id,
        'selected_by_print_group': json_module.dumps(selected_by_print_group),
        'categories': categories,
        'print_groups': all_print_groups,
        'custom_print_groups': custom_print_groups,
    }
    return render(request, 'documents/needs_list.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def create_document(request):
    """
    API endpoint to create a new document
    POST /api/documents/create/
    Body: JSON with name, description, category_id, print_group_ids (optional)
    """
    try:
        data = json.loads(request.body)
        name = data.get('name')
        description = data.get('description')
        category_id = data.get('category_id')
        print_group_ids = data.get('print_group_ids', [])
        
        if not name or not description or not category_id:
            return JsonResponse({'error': 'Missing required fields: name, description, category_id'}, status=400)
        
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return JsonResponse({'error': 'Category not found'}, status=404)
        
        document = Document.objects.create(
            name=name,
            description=description,
            category=category
        )
        
        # Add print groups if provided
        if print_group_ids:
            print_groups = PrintGroup.objects.filter(id__in=print_group_ids)
            document.print_groups.set(print_groups)
        
        return JsonResponse({
            'success': True,
            'document': {
                'id': document.id,
                'name': document.name,
                'description': document.description,
                'category': {
                    'id': document.category.id,
                    'name': document.category.name,
                }
            }
        }, status=201)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def upload_document_file(request, document_id):
    """
    API endpoint to upload a file for a document
    POST /api/documents/<document_id>/upload/
    Body: multipart/form-data with 'file' field
    """
    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        return JsonResponse({'error': 'Document not found'}, status=404)
    
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)
    
    file = request.FILES['file']
    document.file = file
    document.save()
    
    return JsonResponse({
        'success': True,
        'file_url': document.file.url,
        'file_name': document.file.name.split('/')[-1]
    })


def admin_request_page(request, request_id):
    """
    Admin page for selecting documents for a specific request ID.
    URL: {request_id}/request/admin/
    """
    # Get or create the document request
    doc_request, created = DocumentRequest.objects.get_or_create(request_id=request_id)
    
    context = {
        'request_id': request_id,
    }
    return render(request, 'documents/admin_request.html', context)


def user_upload_page(request, request_id):
    """
    User upload page for a specific request ID.
    URL: {request_id}/upload/
    If no document list exists yet, shows a friendly "create the list first" page instead of 404.
    """
    try:
        doc_request = DocumentRequest.objects.get(request_id=request_id)
    except DocumentRequest.DoesNotExist:
        return render(request, 'documents/request_not_found.html', {'request_id': request_id, 'is_user_facing': True})
    adhoc_docs, individual_docs, needs_list_docs = _build_request_document_data(doc_request)
    context = {
        'request_id': request_id,
        'adhoc_documents': adhoc_docs,
        'individual_documents': individual_docs,
        'needs_list_documents': needs_list_docs,
    }
    return render(request, 'documents/user_upload.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def create_adhoc_document(request, request_id):
    """
    API endpoint to create a custom AD HOC document.
    POST /api/{request_id}/admin/adhoc/create/
    Body: JSON with name, description, category_id
    """
    try:
        # Get or create the document request
        doc_request, created = DocumentRequest.objects.get_or_create(request_id=request_id)
        
        data = json.loads(request.body)
        name = data.get('name')
        description = data.get('description')
        category_id = data.get('category_id')
        
        if not name or not description or not category_id:
            return JsonResponse({'error': 'Missing required fields: name, description, category_id'}, status=400)
        
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return JsonResponse({'error': 'Category not found'}, status=404)
        
        # Create the document
        document = Document.objects.create(
            name=name,
            description=description,
            category=category
        )
        
        # Create admin selection for this adhoc document
        selection = AdminDocumentSelection.objects.create(
            request=doc_request,
            section_type='adhoc',
            document=document
        )
        
        return JsonResponse({
            'success': True,
            'selection_id': selection.id,
            'document': {
                'id': document.id,
                'name': document.name,
                'description': document.description,
                'category': {
                    'id': document.category.id,
                    'name': document.category.name,
                }
            }
        }, status=201)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_individual_document(request, request_id):
    """
    API endpoint to create a custom Individual document.
    POST /api/{request_id}/admin/individual/create/
    Body: JSON with name, description, category_id
    """
    try:
        # Get or create the document request
        doc_request, created = DocumentRequest.objects.get_or_create(request_id=request_id)
        
        data = json.loads(request.body)
        name = data.get('name')
        description = data.get('description')
        category_id = data.get('category_id')
        
        if not name or not description or not category_id:
            return JsonResponse({'error': 'Missing required fields: name, description, category_id'}, status=400)
        
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return JsonResponse({'error': 'Category not found'}, status=404)
        
        # Create the document
        document = Document.objects.create(
            name=name,
            description=description,
            category=category
        )
        
        # Create admin selection for this individual document
        selection = AdminDocumentSelection.objects.create(
            request=doc_request,
            section_type='individual',
            document=document
        )
        
        return JsonResponse({
            'success': True,
            'selection_id': selection.id,
            'document': {
                'id': document.id,
                'name': document.name,
                'description': document.description,
                'category': {
                    'id': document.category.id,
                    'name': document.category.name,
                }
            }
        }, status=201)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_needs_list_print_group(request, request_id):
    """
    API endpoint to create a custom print group (parent) for needs list.
    POST /api/{request_id}/admin/needs-list/print-group/create/
    Body: JSON with name, description (optional)
    """
    try:
        # Get or create the document request
        doc_request, created = DocumentRequest.objects.get_or_create(request_id=request_id)
        
        data = json.loads(request.body)
        name = data.get('name')
        description = data.get('description', '')
        
        if not name:
            return JsonResponse({'error': 'Missing required field: name'}, status=400)
        
        # Create the print group
        print_group = PrintGroup.objects.create(
            name=name,
            description=description or f'Print group: {name}'
        )
        
        return JsonResponse({
            'success': True,
            'print_group': {
                'id': print_group.id,
                'name': print_group.name,
                'description': print_group.description,
            }
        }, status=201)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_needs_list_document(request, request_id):
    """
    API endpoint to create a custom document (child) for a print group in needs list.
    POST /api/{request_id}/admin/needs-list/document/create/
    Body: JSON with name, description, category_id, print_group_id
    """
    try:
        # Get or create the document request
        doc_request, created = DocumentRequest.objects.get_or_create(request_id=request_id)
        
        data = json.loads(request.body)
        name = data.get('name')
        description = data.get('description')
        category_id = data.get('category_id')
        print_group_id = data.get('print_group_id')
        
        if not name or not description or not category_id or not print_group_id:
            return JsonResponse({'error': 'Missing required fields: name, description, category_id, print_group_id'}, status=400)
        
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return JsonResponse({'error': 'Category not found'}, status=404)
        
        try:
            print_group = PrintGroup.objects.get(id=print_group_id)
        except PrintGroup.DoesNotExist:
            return JsonResponse({'error': 'Print group not found'}, status=404)
        
        # Create the document
        document = Document.objects.create(
            name=name,
            description=description,
            category=category
        )
        
        # Add document to print group
        document.print_groups.add(print_group)
        
        # Create admin selection for this needs list document
        selection = AdminDocumentSelection.objects.create(
            request=doc_request,
            section_type='needs_list',
            document=document,
            print_group=print_group
        )
        
        return JsonResponse({
            'success': True,
            'selection_id': selection.id,
            'document': {
                'id': document.id,
                'name': document.name,
                'description': document.description,
                'category': {
                    'id': document.category.id,
                    'name': document.category.name,
                },
                'print_group': {
                    'id': print_group.id,
                    'name': print_group.name,
                }
            }
        }, status=201)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_adhoc_document(request, request_id, selection_id):
    """
    API endpoint to delete an AD HOC custom document.
    DELETE /api/{request_id}/admin/adhoc/{selection_id}/delete/
    """
    try:
        # Verify request exists
        doc_request = DocumentRequest.objects.get(request_id=request_id)
        
        # Get the admin selection
        selection = get_object_or_404(
            AdminDocumentSelection,
            id=selection_id,
            request=doc_request,
            section_type='adhoc'
        )
        
        document = selection.document
        selection_id_val = selection.id
        
        # Delete the selection
        selection.delete()
        
        # Optionally delete the document if it's only used for this request
        # (You might want to keep it for history, so we'll leave it for now)
        
        return JsonResponse({
            'success': True,
            'message': 'Custom document deleted successfully',
            'selection_id': selection_id_val
        })
    
    except DocumentRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def save_admin_selections(request, request_id):
    """
    API endpoint to save admin document selections.
    POST /api/{request_id}/admin/selections/
    Body: JSON with section_type and document_ids (and print_group_id for needs_list)
    """
    try:
        # Get or create the document request
        doc_request, created = DocumentRequest.objects.get_or_create(request_id=request_id)
        
        data = json.loads(request.body)
        section_type = data.get('section_type')
        document_ids = data.get('document_ids', [])
        print_group_id = data.get('print_group_id', None)
        
        if not section_type or section_type not in ['adhoc', 'individual', 'needs_list']:
            return JsonResponse({'error': 'Invalid section_type. Must be: adhoc, individual, or needs_list'}, status=400)
        
        if not document_ids:
            return JsonResponse({'error': 'document_ids is required'}, status=400)
        
        if section_type == 'needs_list' and not print_group_id:
            return JsonResponse({'error': 'print_group_id is required for needs_list section'}, status=400)
        
        # Validate documents exist
        documents = Document.objects.filter(id__in=document_ids)
        if documents.count() != len(document_ids):
            return JsonResponse({'error': 'One or more documents not found'}, status=404)
        
        # Validate print group if provided
        print_group = None
        if print_group_id:
            try:
                print_group = PrintGroup.objects.get(id=print_group_id)
            except PrintGroup.DoesNotExist:
                return JsonResponse({'error': 'Print group not found'}, status=404)
        
        # Delete existing selections for this section type and request
        AdminDocumentSelection.objects.filter(
            request=doc_request,
            section_type=section_type
        ).delete()
        
        # Create new selections
        selections = []
        with transaction.atomic():
            for document in documents:
                selection = AdminDocumentSelection.objects.create(
                    request=doc_request,
                    section_type=section_type,
                    document=document,
                    print_group=print_group
                )
                selections.append({
                    'id': selection.id,
                    'document_id': document.id,
                    'document_name': document.name,
                })
        
        return JsonResponse({
            'success': True,
            'selections': selections,
            'count': len(selections)
        }, status=201)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def upload_user_file(request, request_id, selection_id):
    """
    API endpoint to upload a file for a user document.
    POST /api/{request_id}/upload/{selection_id}/
    Body: multipart/form-data with 'file' field
    Uploads file to GHL (GoHighLevel) and stores url/fileId in model (no server storage).
    """
    try:
        from .ghl_service import upload_file as ghl_upload_file

        doc_request = DocumentRequest.objects.get(request_id=request_id)
        selection = get_object_or_404(AdminDocumentSelection, id=selection_id, request=doc_request)

        if 'file' not in request.FILES:
            return JsonResponse({'error': 'No file provided'}, status=400)

        file = request.FILES['file']
        name = file.name or selection.document.name or 'document'

        # Upload to GHL; do not save file on server
        result = ghl_upload_file(file, name=name)

        upload = UserDocumentUpload.objects.create(
            admin_selection=selection,
            file=None,
            ghl_file_id=result.get('fileId'),
            ghl_file_url=result.get('url'),
            file_name=file.name,
        )

        return JsonResponse({
            'success': True,
            'upload_id': upload.id,
            'file_url': upload.get_file_url(),
            'file_name': upload.get_file_name(),
            'uploaded_at': upload.uploaded_at.isoformat(),
        }, status=201)

    except DocumentRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)
    except Exception as e:
        try:
            import requests
            if isinstance(e, requests.HTTPError) and e.response is not None:
                return JsonResponse({'error': f'GHL upload failed: {e.response.text[:500]}'}, status=502)
        except Exception:
            pass
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_user_upload(request, request_id, upload_id):
    """
    API endpoint to delete a user upload.
    DELETE /api/{request_id}/upload/{upload_id}/delete/
    Deletes from GHL if ghl_file_id is set, then removes our record.
    Prevents deletion if the document has been accepted by admin.
    """
    try:
        from django.conf import settings
        from .ghl_service import delete_media as ghl_delete_media

        doc_request = DocumentRequest.objects.get(request_id=request_id)
        upload = get_object_or_404(
            UserDocumentUpload,
            id=upload_id,
            admin_selection__request=doc_request
        )

        if upload.accepted:
            return JsonResponse({
                'error': 'Cannot delete an accepted document',
                'accepted': True
            }, status=403)

        if upload.ghl_file_id:
            alt_type = getattr(settings, 'GHL_ALT_TYPE', 'location')
            alt_id = getattr(settings, 'GHL_ALT_ID', '') or None
            if alt_id:
                try:
                    ghl_delete_media(upload.ghl_file_id, alt_type=alt_type, alt_id=alt_id)
                except Exception:
                    pass  # still delete our record if GHL delete fails

        deleted_id = upload.id
        upload.delete()

        return JsonResponse({
            'success': True,
            'message': 'Upload deleted successfully',
            'upload_id': deleted_id
        })

    except DocumentRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def accept_user_upload(request, request_id, upload_id):
    """
    API endpoint for admin to accept or reject a user upload.
    POST /api/{request_id}/admin/upload/{upload_id}/accept/
    Body: JSON with 'accepted' (boolean) field
    """
    try:
        # Verify request exists
        doc_request = DocumentRequest.objects.get(request_id=request_id)
        
        # Get the upload
        upload = get_object_or_404(
            UserDocumentUpload,
            id=upload_id,
            admin_selection__request=doc_request
        )
        
        data = json.loads(request.body)
        accepted = data.get('accepted', False)
        
        from django.utils import timezone
        upload.accepted = accepted
        if accepted:
            upload.accepted_at = timezone.now()
        else:
            upload.accepted_at = None
        upload.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Document {"accepted" if accepted else "rejected"} successfully',
            'upload_id': upload.id,
            'accepted': upload.accepted,
            'accepted_at': upload.accepted_at.isoformat() if upload.accepted_at else None
        })
    
    except DocumentRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def user_documents_view(request, request_id):
    """
    User view page to see all their uploaded documents and their status.
    URL: {request_id}/view/
    If no document list exists yet, shows a friendly "create the list first" page instead of 404.
    """
    try:
        doc_request = DocumentRequest.objects.get(request_id=request_id)
    except DocumentRequest.DoesNotExist:
        return render(request, 'documents/request_not_found.html', {'request_id': request_id, 'is_user_facing': True})
    
    selections = AdminDocumentSelection.objects.filter(
        request=doc_request
    ).select_related('document', 'print_group').prefetch_related('user_uploads')
    
    adhoc_docs = []
    individual_docs = []
    needs_list_docs = {}
    
    for selection in selections:
        doc_data = {
            'selection_id': selection.id,
            'document_id': selection.document.id,
            'document_name': selection.document.name,
            'document_description': selection.document.description,
            'uploads': [
                {
                    'id': upload.id,
                    'file_url': upload.get_file_url(),
                    'file_name': upload.get_file_name(),
                    'uploaded_at': upload.uploaded_at,
                    'accepted': upload.accepted,
                    'accepted_at': upload.accepted_at,
                }
                for upload in selection.user_uploads.all()
            ]
        }
        
        if selection.section_type == 'adhoc':
            adhoc_docs.append(doc_data)
        elif selection.section_type == 'individual':
            individual_docs.append(doc_data)
        elif selection.section_type == 'needs_list':
            print_group_name = selection.print_group.name if selection.print_group else 'Unknown'
            if print_group_name not in needs_list_docs:
                needs_list_docs[print_group_name] = []
            needs_list_docs[print_group_name].append(doc_data)
    
    context = {
        'request_id': request_id,
        'adhoc_documents': adhoc_docs,
        'individual_documents': individual_docs,
        'needs_list_documents': needs_list_docs,
    }
    return render(request, 'documents/user_documents_view.html', context)
