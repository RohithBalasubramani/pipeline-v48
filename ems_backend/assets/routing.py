"""WebSocket route table — derived from `page_registry._PAGES`.

Single source of truth for `ws/asset/{id}/<endpoint>/` URLs is the `_PAGES`
list in `page_registry.py`. This walks it and builds Channels `path` entries
programmatically, so adding an endpoint never means editing two lists.

The catch-all `re_path` at the end produces a clean 4404 close for any
`ws/asset/<id>/<unknown_page>/`. MUST be last.
"""
from django.urls import path, re_path

from .consumers._notfound import PageNotFoundDispatcher
from .page_registry import iter_websocket_endpoints


websocket_urlpatterns = [
    path(f'ws/asset/<int:asset_id>/{endpoint}/', dispatcher.as_asgi())
    for endpoint, dispatcher in iter_websocket_endpoints()
]

websocket_urlpatterns.append(
    re_path(r'^ws/asset/(?P<asset_id>\d+)/[\w-]+/$', PageNotFoundDispatcher.as_asgi()),
)
