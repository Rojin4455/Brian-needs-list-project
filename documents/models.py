from django.db import models


class Category(models.Model):
    """
    Represents a document category (e.g., Assets, Credit, Entity, Income, Property)
    """
    name = models.CharField(max_length=100, unique=True, help_text="Category name (e.g., Assets, Credit, Entity)")
    description = models.TextField(blank=True, null=True, help_text="Optional description of the category")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class PrintGroup(models.Model):
    """
    Represents a print group that documents can belong to.
    Examples: Profit & Loss, Conventional Refinance (W-2), FHA Refinance (W-2), VA Refinance (W-2), etc.
    """
    name = models.CharField(max_length=200, unique=True, help_text="Print group name")
    description = models.TextField(blank=True, null=True, help_text="Optional description of the print group")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Document(models.Model):
    """
    Represents a document that may be required for loan processing.
    Each document belongs to a category and can be associated with multiple print groups.
    """
    name = models.CharField(
        max_length=300,
        help_text="Document name (e.g., Bank Statements, Gift Letter)"
    )
    description = models.TextField(
        help_text="Detailed description of what the document is and its purpose"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='documents',
        help_text="The category this document belongs to"
    )
    print_groups = models.ManyToManyField(
        PrintGroup,
        related_name='documents',
        blank=True,
        help_text="Print groups this document belongs to"
    )
    file = models.FileField(
        upload_to='documents/%Y/%m/%d/',
        blank=True,
        null=True,
        help_text="Uploaded document file"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return self.name


class DocumentRequest(models.Model):
    """
    Represents a document request session identified by a unique request ID from the URL.
    """
    request_id = models.CharField(max_length=255, unique=True, help_text="Unique identifier from URL (e.g., gfgwgvffrffgggrg)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Request: {self.request_id}"


class AdminDocumentSelection(models.Model):
    """
    Stores admin's document selections for a specific request.
    """
    SECTION_CHOICES = [
        ('adhoc', 'AD HOC'),
        ('individual', 'Individual Documents'),
        ('needs_list', 'Needs List'),
    ]

    request = models.ForeignKey(
        DocumentRequest,
        on_delete=models.CASCADE,
        related_name='admin_selections',
        help_text="The document request this selection belongs to"
    )
    section_type = models.CharField(
        max_length=20,
        choices=SECTION_CHOICES,
        help_text="Type of section: adhoc, individual, or needs_list"
    )
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='admin_selections',
        help_text="The document selected by admin"
    )
    print_group = models.ForeignKey(
        PrintGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_selections',
        help_text="Print group (only for needs_list section type)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['request', 'section_type', 'document', 'print_group']
        ordering = ['section_type', 'created_at']

    def __str__(self):
        return f"{self.request.request_id} - {self.get_section_type_display()} - {self.document.name}"


class UserDocumentUpload(models.Model):
    """
    Stores user uploads for documents selected by admin.
    """
    admin_selection = models.ForeignKey(
        AdminDocumentSelection,
        on_delete=models.CASCADE,
        related_name='user_uploads',
        help_text="The admin selection this upload belongs to"
    )
    file = models.FileField(
        upload_to='user_uploads/%Y/%m/%d/',
        help_text="User uploaded file (image, PDF, document, etc.)"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Upload for {self.admin_selection.document.name} - {self.file.name}"
