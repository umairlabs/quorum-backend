from django.conf import settings
from django.db import models


class CompanySettings(models.Model):
    class Currency(models.TextChoices):
        PKR = 'PKR', 'PKR'
        USD = 'USD', 'USD'
        EUR = 'EUR', 'EUR'
        GBP = 'GBP', 'GBP'

    class DateFormat(models.TextChoices):
        DMY = 'DD/MM/YYYY', 'DD/MM/YYYY'
        MDY = 'MM/DD/YYYY', 'MM/DD/YYYY'
        YMD = 'YYYY-MM-DD', 'YYYY-MM-DD'

    # Integer PK fixed to 1 — enforces singleton at the DB level.
    # update_or_create(pk=1, ...) will always target this single row.
    id = models.AutoField(primary_key=True)

    company_name = models.CharField(max_length=200, blank=True, default='')
    logo_url = models.CharField(max_length=500, blank=True, null=True)
    official_email = models.EmailField(blank=True, default='')
    company_phone = models.CharField(max_length=50, blank=True, default='')
    company_address = models.TextField(blank=True, default='')
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.PKR,
    )
    time_zone = models.CharField(max_length=100, default='Asia/Karachi')
    date_format = models.CharField(
        max_length=20,
        choices=DateFormat.choices,
        default=DateFormat.DMY,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='company_settings_updates',
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'company_settings'
        verbose_name = 'Company Settings'
        verbose_name_plural = 'Company Settings'

    def __str__(self):
        return self.company_name or 'Company Settings'
