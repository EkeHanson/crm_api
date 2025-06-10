# lumina_care/middleware.py
from django_tenants.middleware import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name
from core.models import Domain, Tenant
from django.http import Http404
import logging
from rest_framework_simplejwt.authentication import JWTAuthentication

logger = logging.getLogger(__name__)

class CustomTenantMiddleware(TenantMainMiddleware):
    def process_request(self, request):
        # Allow public endpoints without tenant resolution
        public_paths = ['/api/tenants/', '/api/docs/', '/api/schema/', '/api/token/']
        if any(request.path.startswith(path) for path in public_paths):
            try:
                public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
                request.tenant = public_tenant
                logger.info("Using public tenant for public endpoint")
                return
            except Tenant.DoesNotExist:
                logger.error("Public tenant does not exist")
                raise Http404("Public tenant not configured")

        # Try JWT authentication to get tenant from token
        try:
            auth = JWTAuthentication().authenticate(request)
            if auth:
                user, token = auth
                tenant_id = token.get('tenant_id')
                if tenant_id:
                    tenant = Tenant.objects.get(id=tenant_id)
                    request.tenant = tenant
                    logger.info(f"Tenant set from JWT: {tenant.schema_name}")
                    return
        except Exception as e:
            logger.debug(f"JWT tenant resolution failed: {str(e)}")

        # Fallback to hostname-based resolution
        hostname = request.get_host().split(':')[0]
        domain = Domain.objects.filter(domain=hostname).first()
        if domain:
            request.tenant = domain.tenant
            logger.info(f"Tenant set from domain: {domain.tenant.schema_name}")
            return

        # Fallback for app.mydomain.com or localhost
        if hostname in ['app.mydomain.com', '127.0.0.1', 'localhost']:
            try:
                public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
                request.tenant = public_tenant
                logger.info("Using public tenant as fallback")
                return
            except Tenant.DoesNotExist:
                tenant = Tenant.objects.first()
                if tenant:
                    request.tenant = tenant
                    logger.info(f"No public tenant, using first tenant: {tenant.schema_name}")
                    return

        logger.error(f"No tenant found for hostname: {hostname}")
        raise Http404(f"No tenant found for hostname: {hostname}")