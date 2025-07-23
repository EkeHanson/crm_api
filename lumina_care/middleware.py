# # lumina_care/middleware.py
# from django_tenants.middleware import TenantMainMiddleware
# from django_tenants.utils import get_public_schema_name
# from core.models import Domain, Tenant
# from django.http import Http404
# from django.db import connection
# import logging
# from rest_framework_simplejwt.authentication import JWTAuthentication

# logger = logging.getLogger(__name__)
# # lumina_care/middleware.py
# from django_tenants.middleware import TenantMainMiddleware
# from django_tenants.utils import get_public_schema_name
# from core.models import Domain, Tenant
# from django.http import Http404, JsonResponse
# from django.db import connection
# import logging
# from rest_framework_simplejwt.authentication import JWTAuthentication

# logger = logging.getLogger(__name__)

# class CustomTenantMiddleware(TenantMainMiddleware):
#     def process_request(self, request):
#         logger.debug(f"Processing request: {request.path}, Host: {request.get_host()}")
#         public_paths = [
#             '/api/tenants/', '/api/docs/', '/api/schema/',
#             '/api/token/', '/accounts/', '/api/social/callback/', '/api/admin/create/'
#             '/api/password/reset/', '/api/password/reset/confirm/'
#         ]
#         if any(request.path.startswith(path) for path in public_paths):
#             try:
#                 public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
#                 request.tenant = public_tenant
#                 logger.info(f"Using public tenant for public endpoint: {public_tenant.schema_name}")
#                 with connection.cursor() as cursor:
#                     cursor.execute("SHOW search_path;")
#                     logger.debug(f"Search_path: {cursor.fetchone()[0]}")
#                 return
#             except Tenant.DoesNotExist:
#                 logger.error("Public tenant does not exist")
#                 if request.path.startswith('/api/'):
#                     return JsonResponse({'error': 'Public tenant not configured'}, status=404)
#                 raise Http404("Public tenant not configured")

#         # Try JWT authentication
#         try:
#             auth = JWTAuthentication().authenticate(request)
#             if auth:
#                 user, token = auth
#                 tenant_id = token.get('tenant_id')
#                 if tenant_id:
#                     tenant = Tenant.objects.get(id=tenant_id)
#                     request.tenant = tenant
#                     logger.info(f"Tenant set from JWT: {tenant.schema_name}")
#                     with connection.cursor() as cursor:
#                         cursor.execute("SHOW search_path;")
#                         logger.debug(f"Search_path: {cursor.fetchone()[0]}")
#                     return
#                 else:
#                     logger.warning("No tenant_id in JWT token")
#         except Exception as e:
#             logger.debug(f"JWT tenant resolution failed: {str(e)}")

#         # Fallback to hostname
#         hostname = request.get_host().split(':')[0]
#         domain = Domain.objects.filter(domain=hostname).first()
#         if domain:
#             request.tenant = domain.tenant
#             logger.info(f"Tenant set from domain: {domain.tenant.schema_name}")
#             with connection.cursor() as cursor:
#                 cursor.execute("SHOW search_path;")
#                 logger.debug(f"Search_path: {cursor.fetchone()[0]}")
#             return

#         # Development fallback
#         if hostname in ['127.0.0.1', 'localhost']:
#             try:
#                 tenant = Tenant.objects.get(schema_name='abraham_ekene_onwon')
#                 request.tenant = tenant
#                 logger.info(f"Using tenant {tenant.schema_name} for local development")
#                 with connection.cursor() as cursor:
#                     cursor.execute("SHOW search_path;")
#                     logger.debug(f"Search_path: {cursor.fetchone()[0]}")
#                 return
#             except Tenant.DoesNotExist:
#                 logger.error("Development tenant abraham_ekene_onwon does not exist")
#                 if request.path.startswith('/api/'):
#                     return JsonResponse({'error': 'Development tenant not configured'}, status=404)
#                 raise Http404("Development tenant not configured")

#         logger.error(f"No tenant found for hostname: {hostname}")
#         if request.path.startswith('/api/'):
#             return JsonResponse({'error': f'No tenant found for hostname: {hostname}'}, status=404)
#         raise Http404(f"No tenant found for hostname: {hostname}")

# # class CustomTenantMiddleware(TenantMainMiddleware):
#     def process_request(self, request):
#         logger.debug(f"Processing request: {request.path}, Host: {request.get_host()}")
#         public_paths = [
#             '/api/tenants/', '/api/docs/', '/api/schema/',
#             '/api/token/', '/accounts/', '/api/social/callback/', '/api/admin/create/'
#         ]
#         if any(request.path.startswith(path) for path in public_paths):
#             try:
#                 public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
#                 request.tenant = public_tenant
#                 logger.info(f"Using public tenant for public endpoint: {public_tenant.schema_name}")
#                 with connection.cursor() as cursor:
#                     cursor.execute("SHOW search_path;")
#                     logger.debug(f"Search_path: {cursor.fetchone()[0]}")
#                 return
#             except Tenant.DoesNotExist:
#                 logger.error("Public tenant does not exist")
#                 raise Http404("Public tenant not configured")

#         # Try JWT authentication
#         try:
#             auth = JWTAuthentication().authenticate(request)
#             if auth:
#                 user, token = auth
#                 tenant_id = token.get('tenant_id')
#                 if tenant_id:
#                     tenant = Tenant.objects.get(id=tenant_id)
#                     request.tenant = tenant
#                     logger.info(f"Tenant set from JWT: {tenant.schema_name}")
#                     with connection.cursor() as cursor:
#                         cursor.execute("SHOW search_path;")
#                         logger.debug(f"Search_path: {cursor.fetchone()[0]}")
#                     return
#                 else:
#                     logger.warning("No tenant_id in JWT token")
#         except Exception as e:
#             logger.debug(f"JWT tenant resolution failed: {str(e)}")

#         # Fallback to hostname
#         hostname = request.get_host().split(':')[0]
#         domain = Domain.objects.filter(domain=hostname).first()
#         if domain:
#             request.tenant = domain.tenant
#             logger.info(f"Tenant set from domain: {domain.tenant.schema_name}")
#             with connection.cursor() as cursor:
#                 cursor.execute("SHOW search_path;")
#                 logger.debug(f"Search_path: {cursor.fetchone()[0]}")
#             return

#         # Development fallback
#         if hostname in ['127.0.0.1', 'localhost']:
#             try:
#                 tenant = Tenant.objects.get(schema_name='abraham_ekene_onwon')
#                 request.tenant = tenant
#                 logger.info(f"Using tenant {tenant.schema_name} for local development")
#                 with connection.cursor() as cursor:
#                     cursor.execute("SHOW search_path;")
#                     logger.debug(f"Search_path: {cursor.fetchone()[0]}")
#                 return
#             except Tenant.DoesNotExist:
#                 logger.error("Development tenant abraham_ekene_onwon does not exist")
#                 raise Http404("Development tenant not configured")

#         logger.error(f"No tenant found for hostname: {hostname}")
#         raise Http404(f"No tenant found for hostname: {hostname}")


from django_tenants.middleware import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name
from core.models import Domain, Tenant
from users.models import PasswordResetToken
from django.http import Http404, JsonResponse
from django.db import connection
import logging
import json
from rest_framework_simplejwt.authentication import JWTAuthentication

logger = logging.getLogger(__name__)

class CustomTenantMiddleware(TenantMainMiddleware):
    def process_request(self, request):
        logger.debug(f"Processing request: {request.path}, Host: {request.get_host()}")
        public_paths = [
            '/api/tenants/', '/api/docs/', '/api/schema/',
            '/api/token/', '/accounts/', '/api/social/callback/', '/api/admin/create/',
            '/api/user/password/reset/', '/api/user/password/reset/confirm/'  # Add password reset endpoints
        ]

        # Handle public paths and password reset endpoints
        if any(request.path.startswith(path) for path in public_paths):
            try:
                public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
                request.tenant = public_tenant
                logger.info(f"Using public tenant for public endpoint: {public_tenant.schema_name}")

                # For password reset request, identify tenant from email
                if request.path.startswith('/api/user/password/reset/') and request.method == 'POST':
                    try:
                        email = request.POST.get('email') or (request.body and json.loads(request.body).get('email'))
                        if email:
                            email_domain = email.split('@')[1]
                            domain = Domain.objects.filter(domain=email_domain).first()
                            if domain:
                                request.tenant = domain.tenant
                                logger.info(f"Tenant set from email domain {email_domain}: {domain.tenant.schema_name}")
                            else:
                                logger.error(f"No domain found for email: {email_domain}")
                                return JsonResponse({'error': f'No tenant found for email domain: {email_domain}'}, status=404)
                        else:
                            logger.error("No email provided in password reset request")
                            return JsonResponse({'error': 'Email is required'}, status=400)
                    except (ValueError, KeyError, json.JSONDecodeError) as e:
                        logger.error(f"Error extracting email from request: {str(e)}")
                        return JsonResponse({'error': 'Invalid request format'}, status=400)

                # For password reset confirmation, identify tenant from token
                elif request.path.startswith('/api/user/password/reset/confirm/') and request.method == 'POST':
                    try:
                        token = request.POST.get('token') or (request.body and json.loads(request.body).get('token'))
                        if token:
                            reset_token = PasswordResetToken.objects.filter(token=token).first()
                            if reset_token:
                                request.tenant = reset_token.tenant
                                logger.info(f"Tenant set from reset token: {reset_token.tenant.schema_name}")
                            else:
                                logger.error(f"Invalid or missing reset token: {token}")
                                return JsonResponse({'error': 'Invalid or missing token'}, status=400)
                        else:
                            logger.error("No token provided in password reset confirm request")
                            return JsonResponse({'error': 'Token is required'}, status=400)
                    except (ValueError, KeyError, json.JSONDecodeError) as e:
                        logger.error(f"Error extracting token from request: {str(e)}")
                        return JsonResponse({'error': 'Invalid request format'}, status=400)

                with connection.cursor() as cursor:
                    cursor.execute("SHOW search_path;")
                    logger.debug(f"Search_path: {cursor.fetchone()[0]}")
                return
            except Tenant.DoesNotExist:
                logger.error("Public tenant does not exist")
                if request.path.startswith('/api/'):
                    return JsonResponse({'error': 'Public tenant not configured'}, status=404)
                raise Http404("Public tenant not configured")

        # Try JWT authentication
        try:
            auth = JWTAuthentication().authenticate(request)
            if auth:
                user, token = auth
                tenant_id = token.get('tenant_id')
                if tenant_id:
                    tenant = Tenant.objects.get(id=tenant_id)
                    request.tenant = tenant
                    logger.info(f"Tenant set from JWT: {tenant.schema_name}")
                    with connection.cursor() as cursor:
                        cursor.execute("SHOW search_path;")
                        logger.debug(f"Search_path: {cursor.fetchone()[0]}")
                    return
                else:
                    logger.warning("No tenant_id in JWT token")
        except Exception as e:
            logger.debug(f"JWT tenant resolution failed: {str(e)}")

        # Fallback to hostname
        hostname = request.get_host().split(':')[0]
        domain = Domain.objects.filter(domain=hostname).first()
        if domain:
            request.tenant = domain.tenant
            logger.info(f"Tenant set from domain: {domain.tenant.schema_name}")
            with connection.cursor() as cursor:
                cursor.execute("SHOW search_path;")
                logger.debug(f"Search_path: {cursor.fetchone()[0]}")
            return

        # Development fallback
        if hostname in ['127.0.0.1', 'localhost']:
            try:
                tenant = Tenant.objects.get(schema_name='abraham_ekene_onwon')
                request.tenant = tenant
                logger.info(f"Using tenant {tenant.schema_name} for local development")
                with connection.cursor() as cursor:
                    cursor.execute("SHOW search_path;")
                    logger.debug(f"Search_path: {cursor.fetchone()[0]}")
                return
            except Tenant.DoesNotExist:
                logger.error("Development tenant abraham_ekene_onwon does not exist")
                if request.path.startswith('/api/'):
                    return JsonResponse({'error': 'Development tenant not configured'}, status=404)
                raise Http404("Development tenant not configured")

        logger.error(f"No tenant found for hostname: {hostname}")
        if request.path.startswith('/api/'):
            return JsonResponse({'error': f'No tenant found for hostname: {hostname}'}, status=404)
        raise Http404(f"No tenant found for hostname: {hostname}")