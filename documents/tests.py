from unittest.mock import patch

from django.test import Client, TestCase

from documents.models import (
    AdminDocumentSelection,
    Category,
    Document,
    DocumentRequest,
    PrintGroup,
    UserDocumentUpload,
)


class SaveAdminSelectionsPreserveUploadsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(name="Entity")
        self.print_group = PrintGroup.objects.create(name="DSCR")
        self.doc_old = Document.objects.create(
            name="Valid Driver's License",
            description="ID",
            category=self.category,
        )
        self.doc_empty = Document.objects.create(
            name="Articles",
            description="Articles",
            category=self.category,
        )
        self.doc_new = Document.objects.create(
            name="IRS EIN Page",
            description="EIN",
            category=self.category,
        )
        self.doc_old.print_groups.add(self.print_group)
        self.doc_empty.print_groups.add(self.print_group)
        self.doc_new.print_groups.add(self.print_group)
        self.doc_request = DocumentRequest.objects.create(request_id="test-opp-preserve")

        self.sel_uploaded = AdminDocumentSelection.objects.create(
            request=self.doc_request,
            section_type="needs_list",
            document=self.doc_old,
            print_group=self.print_group,
        )
        UserDocumentUpload.objects.create(
            admin_selection=self.sel_uploaded,
            file_name="license.jpg",
            ghl_file_url="https://example.com/license.jpg",
        )
        self.sel_empty = AdminDocumentSelection.objects.create(
            request=self.doc_request,
            section_type="needs_list",
            document=self.doc_empty,
            print_group=self.print_group,
        )

    @patch("documents.views._sync_needs_list_upload_status_to_ghl")
    @patch("documents.ghl_service.update_opportunity_custom_fields")
    @patch("documents.ghl_service.get_opportunity", return_value={})
    def test_resend_keeps_uploaded_docs_and_drops_empty_ones(self, _opp, _fields, _sync):
        response = self.client.post(
            f"/api/{self.doc_request.request_id}/admin/selections/",
            data={
                "section_type": "needs_list",
                "document_ids": [self.doc_new.id],
                "print_group_id": self.print_group.id,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)

        remaining = AdminDocumentSelection.objects.filter(request=self.doc_request)
        remaining_doc_ids = set(remaining.values_list("document_id", flat=True))
        self.assertIn(self.doc_old.id, remaining_doc_ids)
        self.assertIn(self.doc_new.id, remaining_doc_ids)
        self.assertNotIn(self.doc_empty.id, remaining_doc_ids)
        self.assertTrue(
            UserDocumentUpload.objects.filter(admin_selection=self.sel_uploaded).exists()
        )
