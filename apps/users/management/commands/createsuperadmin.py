from django.core.management.base import BaseCommand, CommandError
from apps.users.models import User
from apps.authentication.validators import validate_password_complexity


class Command(BaseCommand):
    help = 'Provision the initial System Admin account out-of-band per SDS Section 2.1.'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Email for System Admin account')
        parser.add_argument('--password', type=str, help='Password for System Admin account')

    def handle(self, *args, **options):
        email = options.get('email')
        password = options.get('password')

        if not email:
            email = input("Email: ").strip()
        if not password:
            import getpass
            password = getpass.getpass("Password: ").strip()

        if not email or not password:
            raise CommandError("Email and password are required.")

        try:
            validate_password_complexity(password)
        except Exception as e:
            raise CommandError(f"Password validation error: {str(e)}")

        email = email.lower()
        if User.objects.filter(email=email).exists():
            raise CommandError(f"User with email {email} already exists.")

        user = User.objects.create_superuser(
            email=email,
            password=password,
            first_name='System',
            last_name='Admin'
        )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully provisioned System Admin account: {user.email}")
        )