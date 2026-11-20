import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CompanySettings',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('company_name', models.CharField(blank=True, default='', max_length=200)),
                ('logo_url', models.CharField(blank=True, max_length=500, null=True)),
                ('official_email', models.EmailField(blank=True, default='', max_length=254)),
                ('company_phone', models.CharField(blank=True, default='', max_length=50)),
                ('company_address', models.TextField(blank=True, default='')),
                ('currency', models.CharField(
                    choices=[('PKR', 'PKR'), ('USD', 'USD'), ('EUR', 'EUR'), ('GBP', 'GBP')],
                    default='PKR',
                    max_length=3,
                )),
                ('time_zone', models.CharField(default='Asia/Karachi', max_length=100)),
                ('date_format', models.CharField(
                    choices=[('DD/MM/YYYY', 'DD/MM/YYYY'), ('MM/DD/YYYY', 'MM/DD/YYYY'), ('YYYY-MM-DD', 'YYYY-MM-DD')],
                    default='DD/MM/YYYY',
                    max_length=20,
                )),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='company_settings_updates',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Company Settings',
                'verbose_name_plural': 'Company Settings',
                'db_table': 'company_settings',
            },
        ),
    ]
