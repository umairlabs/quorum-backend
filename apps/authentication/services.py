from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from apps.users.models import User
from .models import RefreshTokenBlacklist


class AuthService:
    GENERIC_LOGIN_ERROR = "Invalid email or password."

    @staticmethod
    def login(email: str, password: str) -> dict:
        """
        Authenticates user by email and password only.
        Role is NOT part of the request -- it is looked up from the user
        record and returned in the response for the frontend to redirect on.
        Raises AuthenticationFailed with the exact generic message
        "Invalid email or password." on any failure.
        """
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise AuthenticationFailed(AuthService.GENERIC_LOGIN_ERROR)

        if not user.is_active:
            raise AuthenticationFailed(AuthService.GENERIC_LOGIN_ERROR)

        if not user.check_password(password):
            raise AuthenticationFailed(AuthService.GENERIC_LOGIN_ERROR)

        # Update last login timestamp
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        # Issue SimpleJWT tokens with custom claims
        refresh = RefreshToken.for_user(user)
        refresh['role'] = user.role
        refresh['email'] = user.email

        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'role': user.role,
            'must_change_password': user.must_change_password,
            'user': user
        }

    @staticmethod
    def refresh(refresh_token_str: str) -> dict:
        """
        Validates refresh token and returns new access token.
        Rejects blacklisted tokens and tokens issued before tokens_valid_after.
        """
        try:
            token = RefreshToken(refresh_token_str)
            jti = token.payload.get('jti')

            if RefreshTokenBlacklist.objects.filter(jti=jti).exists():
                raise AuthenticationFailed("Token is invalid or blacklisted.")

            user_id = token.payload.get('user_id')
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                    if user.tokens_valid_after:
                        iat = token.payload.get('iat')
                        if iat is not None and iat < user.tokens_valid_after.timestamp():
                            raise AuthenticationFailed("Token is invalid or expired.")
                except User.DoesNotExist:
                    raise AuthenticationFailed("Token is invalid or expired.")

            return {
                'access': str(token.access_token)
            }
        except TokenError:
            raise AuthenticationFailed("Token is invalid or expired.")

    @staticmethod
    def logout(user, refresh_token_str: str) -> None:
        """
        Blacklists the provided refresh token.
        """
        if not refresh_token_str:
            return
        try:
            token = RefreshToken(refresh_token_str)
            jti = token.payload.get('jti')
            if jti and not RefreshTokenBlacklist.objects.filter(jti=jti).exists():
                RefreshTokenBlacklist.objects.create(jti=jti, user=user)
        except Exception:
            pass  # Even if token is already invalid, logout succeeds

    @staticmethod
    def blacklist_all_refresh_tokens(user) -> None:
        """
        Invalidates all outstanding refresh tokens for a user by updating
        tokens_valid_after. Used after password reset / forced change.
        """
        user.tokens_valid_after = timezone.now()
        user.save(update_fields=['tokens_valid_after'])
        revocation_jti = f"all_tokens_revoked_{user.id}_{timezone.now().timestamp()}"
        RefreshTokenBlacklist.objects.create(jti=revocation_jti, user=user)

    @staticmethod
    def change_password(user, current_password: str, new_password: str) -> None:
        """
        Changes user password, sets tokens_valid_after, and clears
        must_change_password flag.
        """
        if not user.check_password(current_password):
            raise ValidationError({"current_password": "Current password is incorrect."})

        user.set_password(new_password)
        user.must_change_password = False
        user.tokens_valid_after = timezone.now()
        user.save()
