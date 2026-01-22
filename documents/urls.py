from django.urls import path
from . import views

urlpatterns = [
    # Request-based URLs (with request_id)
    path('<str:request_id>/request/admin/', views.homepage, name='admin-homepage'),
    path('<str:request_id>/request/admin/adhoc/', views.adhoc_page, name='adhoc'),
    path('<str:request_id>/request/admin/individual-documents/', views.individual_documents_page, name='individual-documents'),
    path('<str:request_id>/request/admin/needs-list/', views.needs_list_page, name='needs-list'),
    path('<str:request_id>/upload/', views.user_upload_page, name='user-upload'),
    # API endpoints
    path('api/categories/', views.get_categories, name='categories'),
    path('api/documents/', views.get_documents, name='documents'),
    path('api/documents/create/', views.create_document, name='create-document'),
    path('api/documents/<int:document_id>/upload/', views.upload_document_file, name='upload-document'),
    path('api/print-groups/', views.get_print_groups, name='print-groups'),
    path('api/<str:request_id>/admin/adhoc/create/', views.create_adhoc_document, name='create-adhoc-document'),
    path('api/<str:request_id>/admin/adhoc/<int:selection_id>/delete/', views.delete_adhoc_document, name='delete-adhoc-document'),
    path('api/<str:request_id>/admin/selections/', views.save_admin_selections, name='save-admin-selections'),
    path('api/<str:request_id>/upload/<int:selection_id>/', views.upload_user_file, name='upload-user-file'),
    path('api/<str:request_id>/upload/<int:upload_id>/delete/', views.delete_user_upload, name='delete-user-upload'),
]

