import uuid
import hashlib
from django.db import models
from django.conf import settings
from django.utils import timezone


class PasswordResetToken(models.Model):
    """
    Stores time-limited, single-use password reset tokens hashed via SHA-256.
    Raw token is never stored in DB.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens'
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = 'auth_password_reset_tokens'
        ordering = ['-created_at']

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Computes SHA-256 hex digest of raw token."""
        return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    def is_valid(self) -> bool:
        return not self.is_used and timezone.now() < self.expires_at

    def __str__(self):
        return f"ResetToken for {self.user.email} (used={self.is_used})"


class RefreshTokenBlacklist(models.Model):
    """
    Stores blacklisted refresh token JWT identifiers (jti).
    Immutability constraint: insert-only.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    jti = models.CharField(max_length=255, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blacklisted_tokens'
    )
    blacklisted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'auth_refresh_token_blacklist'
        ordering = ['-blacklisted_at']

    def __str__(self):
        return f"Blacklisted JTI {self.jti} for {self.user.email}"