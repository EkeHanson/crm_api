# lumina_care/middleware.py
from django_tenants.middleware import TenantMainMiddleware
from django_tenants.utils import get_public_schema_name
from core.models import Domain, Tenant
from django.http import Http404
import logging
from rest_framework_simplejwt.authentication import JWTAuthentication

logger = logging.getLogger(__name__)


# lumina_care/middleware.py
class CustomTenantMiddleware(TenantMainMiddleware):
    def process_request(self, request):
        public_paths = [
            '/api/tenants/', '/api/docs/', '/api/schema/',
            '/api/token/', '/accounts/', '/api/social/callback/', '/api/admin/create/'
        ]
        if any(request.path.startswith(path) for path in public_paths):
            try:
                public_tenant = Tenant.objects.get(schema_name=get_public_schema_name())
                request.tenant = public_tenant
                logger.info("Using public tenant for public endpoint")
                return
            except Tenant.DoesNotExist:
                logger.error("Public tenant does not exist")
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
            return

        # Development fallback
        if hostname in ['127.0.0.1', 'localhost']:
            try:
                tenant = Tenant.objects.get(schema_name='abraham_ekene_onwon')
                request.tenant = tenant
                logger.info(f"Using tenant {tenant.schema_name} for local development")
                return
            except Tenant.DoesNotExist:
                logger.error("Development tenant abraham_ekene_onwon does not exist")
                raise Http404("Development tenant not configured")

        logger.error(f"No tenant found for hostname: {hostname}")
        raise Http404(f"No tenant found for hostname: {hostname}")