from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.users.models import User
from apps.authentication.models import RefreshTokenBlacklist
from apps.authentication.services import AuthService


class AuthenticationModuleTests(APITestCase):
    def setUp(self):
        # Create test users for each role
        self.admin_user = User.objects.create_user(
            email='admin@assettrak.com',
            password='Password123',
            role=User.Role.SYSTEM_ADMIN,
            must_change_password=False
        )

        self.manager_user = User.objects.create_user(
            email='manager@assettrak.com',
            password='Password123',
            role=User.Role.OPERATIONS_MANAGER,
            must_change_password=True
        )
        self.tech_user = User.objects.create_user(
            email='tech@assettrak.com',
            password='Password123',
            role=User.Role.EXTERNAL_TECHNICIAN,
            must_change_password=False
        )

        self.login_url = reverse('authentication:login')
        self.refresh_url = reverse('authentication:refresh')
        self.logout_url = reverse('authentication:logout')
        self.change_password_url = reverse('authentication:change-password')

    def test_login_success(self):
        """Login with valid credentials succeeds — no role field needed."""
        payload = {
            'email': 'admin@assettrak.com',
            'password': 'Password123',
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['role'], User.Role.SYSTEM_ADMIN)
        self.assertFalse(response.data['must_change_password'])

    def test_login_wrong_password_generic_error(self):
        """Wrong password returns exact generic message 'Invalid email or password.'."""
        payload = {
            'email': 'manager@assettrak.com',
            'password': 'WrongPassword123',
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['detail'], "Invalid email or password.")

    def test_login_nonexistent_email_generic_error(self):
        """Unknown email returns the same generic error (no user enumeration)."""
        payload = {
            'email': 'doesnotexist@assettrak.com',
            'password': 'Password123',
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['detail'], "Invalid email or password.")

    def test_login_deactivated_account_generic_error(self):
        """Deactivated account cannot log in even with the correct password."""
        self.tech_user.is_active = False
        self.tech_user.save(update_fields=['is_active'])

        payload = {
            'email': 'tech@assettrak.com',
            'password': 'Password123',
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['detail'], "Invalid email or password.")

    def test_forced_password_change_flag(self):
        """Newly provisioned user has must_change_password=True in response."""
        payload = {
            'email': 'manager@assettrak.com',
            'password': 'Password123',
        }
        response = self.client.post(self.login_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['must_change_password'])

    def test_change_password_success(self):
        """Updating password succeeds, clears must_change_password flag, and invalidates old refresh tokens."""
        login_res = AuthService.login('manager@assettrak.com', 'Password123')
        old_refresh_token = login_res['refresh']

        self.client.force_authenticate(user=self.manager_user)
        payload = {
            'current_password': 'Password123',
            'new_password': 'NewPassword999',
            'confirm_new_password': 'NewPassword999'
        }
        response = self.client.put(self.change_password_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.manager_user.refresh_from_db()
        self.assertFalse(self.manager_user.must_change_password)
        self.assertTrue(self.manager_user.check_password('NewPassword999'))

        # Verify old refresh token fails on /refresh/
        refresh_res = self.client.post(self.refresh_url, {'refresh_token': old_refresh_token}, format='json')
        self.assertEqual(refresh_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_wrong_current_password(self):
        """Wrong current_password is rejected."""
        self.client.force_authenticate(user=self.manager_user)
        payload = {
            'current_password': 'WrongCurrent123',
            'new_password': 'NewPassword999',
            'confirm_new_password': 'NewPassword999'
        }
        response = self.client.put(self.change_password_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_silent_token_refresh(self):
        """Valid refresh token produces a new access token."""
        login_res = AuthService.login('tech@assettrak.com', 'Password123')
        refresh_token = login_res['refresh']

        response = self.client.post(self.refresh_url, {'refresh_token': refresh_token}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_refresh_with_invalid_token(self):
        """Garbage refresh token returns 401."""
        response = self.client.post(self.refresh_url, {'refresh_token': 'not-a-real-token'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_token(self):
        """Logout blacklists refresh token and prevents reuse."""
        login_res = AuthService.login('tech@assettrak.com', 'Password123')
        refresh_token = login_res['refresh']

        self.client.force_authenticate(user=self.tech_user)
        logout_res = self.client.post(self.logout_url, {'refresh_token': refresh_token}, format='json')
        self.assertEqual(logout_res.status_code, status.HTTP_200_OK)

        refresh_res = self.client.post(self.refresh_url, {'refresh_token': refresh_token}, format='json')
        self.assertEqual(refresh_res.status_code, status.HTTP_401_UNAUTHORIZED)