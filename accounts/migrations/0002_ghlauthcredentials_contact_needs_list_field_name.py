from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="ghlauthcredentials",
            name="contact_needs_list_field_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Optional. Exact name of a contact custom field in GHL (must exist in "
                    "GHLCustomField after sync), e.g. 'Send Needs List'. When set, admin needs-list "
                    "saves also update that contact field with the numbered list and upload link."
                ),
                max_length=255,
            ),
        ),
    ]
