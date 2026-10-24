import sys
import socket
import smtplib
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import send_mail, get_connection


class Command(BaseCommand):
    help = "Diagnose and verify Gmail / SMTP connectivity, authentication, and dispatch."

    def add_arguments(self, parser):
        parser.add_argument(
            'recipient',
            nargs='?',
            default=None,
            help="Target email address to receive the test message (defaults to SMTP_USER / EMAIL_HOST_USER)."
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Passli SMTP & Gmail Integration Diagnostic ==="))

        host = getattr(settings, 'EMAIL_HOST', 'smtp.gmail.com')
        port = getattr(settings, 'EMAIL_PORT', 465)
        use_ssl = getattr(settings, 'EMAIL_USE_SSL', False)
        use_tls = getattr(settings, 'EMAIL_USE_TLS', False)
        user = getattr(settings, 'EMAIL_HOST_USER', '')
        password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '')
        app_url = getattr(settings, 'APP_URL', '')

        recipient = options['recipient'] or user
        if not recipient:
            recipient = "test@example.com"

        # 1. Environment Variable Inspection
        self.stdout.write("\n1. Configuration Settings:")
        self.stdout.write(f"   • EMAIL_HOST:       {host}")
        self.stdout.write(f"   • EMAIL_PORT:       {port}")
        self.stdout.write(f"   • EMAIL_USE_SSL:    {use_ssl}")
        self.stdout.write(f"   • EMAIL_USE_TLS:    {use_tls}")
        self.stdout.write(f"   • EMAIL_HOST_USER:  {user or '(NOT SET - EMPTY)'}")
        self.stdout.write(f"   • EMAIL_HOST_PASS:  {'*' * len(password)} ({len(password)} chars)")
        self.stdout.write(f"   • DEFAULT_FROM:     {from_email}")
        self.stdout.write(f"   • APP_URL:          {app_url}")

        if not user:
            self.stdout.write(self.style.ERROR(
                "\n❌ ERROR: SMTP_USER / EMAIL_HOST_USER is not configured in environment variables (.env)!"
            ))
            return

        if not password:
            self.stdout.write(self.style.ERROR(
                "\n❌ ERROR: SMTP_PASS / EMAIL_HOST_PASSWORD is not configured in environment variables (.env)!"
            ))
            return

        if len(password) != 16 and 'gmail' in host.lower():
            self.stdout.write(self.style.WARNING(
                f"\n⚠️ WARNING: Your Google App Password is {len(password)} characters long. "
                "Google App Passwords are normally exactly 16 characters (e.g. 'abcdefghijklmnop'). "
                "Make sure you did not enter a regular Google account password!"
            ))

        # 2. DNS & Socket Connectivity
        self.stdout.write(f"\n2. Testing Network Socket Connection to {host}:{port}...")
        try:
            s = socket.create_connection((host, port), timeout=10)
            s.close()
            self.stdout.write(self.style.SUCCESS(f"   ✅ Successfully established TCP connection to {host}:{port}"))
        except Exception as sock_err:
            self.stdout.write(self.style.ERROR(
                f"   ❌ Network connection to {host}:{port} failed: {sock_err}\n"
                f"   TIP: If port {port} is blocked by your hosting firewall, switch SMTP_PORT to 587 with STARTTLS in environment variables."
            ))
            return

        # 3. SMTP Handshake & Authentication
        self.stdout.write("\n3. Authenticating with SMTP Server...")
        try:
            if use_ssl:
                server = smtplib.SMTP_SSL(host, port, timeout=12)
            else:
                server = smtplib.SMTP(host, port, timeout=12)
                if use_tls:
                    server.starttls()

            server.ehlo()
            server.login(user, password)
            self.stdout.write(self.style.SUCCESS(f"   ✅ SMTP Authentication successful as '{user}'!"))
            server.quit()
        except smtplib.SMTPAuthenticationError as auth_err:
            self.stdout.write(self.style.ERROR(
                f"   ❌ SMTP Authentication Failed (code {auth_err.smtp_code}): {auth_err.smtp_error.decode('utf-8', 'ignore')}\n\n"
                "   👉 HOW TO FIX:\n"
                "   1. Ensure 2-Step Verification is enabled on your Google Account.\n"
                "   2. Go to https://myaccount.google.com/apppasswords\n"
                "   3. Create an App Password for 'Passli'.\n"
                "   4. Copy the 16 characters (remove spaces) and paste into SMTP_PASS in your environment."
            ))
            return
        except Exception as smtp_err:
            self.stdout.write(self.style.ERROR(f"   ❌ SMTP Protocol error: {smtp_err}"))
            return

        # 4. End-to-End Test Dispatch
        self.stdout.write(f"\n4. Sending Test Email to {recipient}...")
        try:
            send_mail(
                subject="Passli SMTP Test Email",
                message=(
                    f"Hello,\n\n"
                    f"This is a test email sent from your Passli instance.\n\n"
                    f"Configuration Details:\n"
                    f"- Host: {host}:{port}\n"
                    f"- Mode: {'SSL' if use_ssl else ('STARTTLS' if use_tls else 'Plain')}\n"
                    f"- Sender: {from_email}\n"
                    f"- App URL: {app_url}\n\n"
                    f"Your email integration is fully operational!\n"
                ),
                from_email=from_email,
                recipient_list=[recipient],
                fail_silently=False
            )
            self.stdout.write(self.style.SUCCESS(f"\n🎉 SUCCESS! Test email was successfully sent to '{recipient}'. Check your inbox!"))
        except Exception as send_err:
            self.stdout.write(self.style.ERROR(f"\n❌ Failed to dispatch email message: {send_err}"))
