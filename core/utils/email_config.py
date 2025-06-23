# core/utils/email_config.py

from django.conf import settings
from django.core.mail import get_connection
from django_tenants.utils import get_tenant

def get_email_connection():
    try:
        tenant = get_tenant()
        if tenant and tenant.email_host and tenant.email_host_user:
            return get_connection(
                backend='django.core.mail.backends.smtp.EmailBackend',
                host=tenant.email_host,
                port=tenant.email_port,
                username=tenant.email_host_user,
                password=tenant.email_host_password,
                use_ssl=tenant.email_use_ssl,
            )
    except Exception as e:
        pass

    # fallback to global settings
    return get_connection()



#SENDING EMAILS
# anywhere in your app where you want to send email
# from django.core.mail import EmailMessage
# from core.utils.email_config import get_email_connection

# def send_email(subject, body, to):
#     connection = get_email_connection()
#     from_email = get_tenant().default_from_email if get_tenant().default_from_email else settings.DEFAULT_FROM_EMAIL

#     email = EmailMessage(
#         subject=subject,
#         body=body,
#         from_email=from_email,
#         to=[to],
#         connection=connection
#     )
#     email.send()
