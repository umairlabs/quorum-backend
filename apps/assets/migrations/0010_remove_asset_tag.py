# Generated manually

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0009_clean_asset_names'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='asset',
            name='asset_tag',
        ),
    ]
