
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_fcmdevice'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='related_request_id',
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='related_request_number',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
    ]
