from typing import Optional, Any, Dict

from fastapi import Request

from app.repository.order_meta import OrderMetaRepository
from app.logging.utils import get_app_logger
from app.middlewares.request_context import request_context

logger = get_app_logger("app.services.order_meta_service")


def _extract_client_ip(request: Request) -> Optional[str]:
    try:
        xff = request.headers.get('x-forwarded-for') or request.headers.get('X-Forwarded-For')
        if xff:
            # Take the first IP in the list
            return xff.split(',')[0].strip()
        client = getattr(request, 'client', None)
        if client and getattr(client, 'host', None):
            return client.host
    except Exception:
        return None
    return None


def _detect_platform(user_agent: Optional[str]) -> Optional[str]:
    if not user_agent:
        return None
    ua = user_agent.lower()
    if 'android' in ua:
        return 'Android'
    if 'iphone' in ua or 'ipad' in ua or 'ios' in ua:
        return 'iOS'
    if 'windows' in ua:
        return 'Windows'
    if 'mac os' in ua or 'macintosh' in ua:
        return 'MacOS'
    if 'linux' in ua:
        return 'Linux'
    return 'Unknown'


class OrderMetaService:
    @staticmethod
    def save_order_metadata(order_internal_id: int, request: Request, origin: str, metadata: Optional[Dict[str, Any]]) -> None:
        """Best-effort persistence of order metadata. Never raises to caller."""
        try:
            client_ip = _extract_client_ip(request)
            user_agent = request.headers.get('user-agent')
            device = metadata.get("device_id")
            longitude = metadata.get("longitude")
            latitude = metadata.get("latitude")
            platform = _detect_platform(user_agent)
            app_version = request_context.app_version or ''
            web_version = request_context.web_version or ''

            repository = OrderMetaRepository()
            repository.create_order_meta(order_id=order_internal_id, client_ip=client_ip, user_agent=user_agent, device=device,
                                                platform=platform, app_version=app_version, web_version=web_version, longitude=longitude, latitude=latitude)
        except Exception:
            # Do not block main flow on metadata errors
            logger.debug("order_metadata_persist_fail", exc_info=True)


