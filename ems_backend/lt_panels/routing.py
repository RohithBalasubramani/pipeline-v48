"""WebSocket route table — derived from `page_registry._PAGES`.

Single source of truth for `ws/mfm/{id}/<endpoint>/` URLs is the
`_PAGES` list in `page_registry.py`. This file walks it and builds
Django Channels `path` entries programmatically so adding a new
endpoint never requires editing two lists in lock-step.

The catch-all `re_path` at the end produces a clean 4404 close for
any `ws/mfm/<id>/<unknown_page>/` instead of Daphne's HTTP 500.
"""
from django.urls import path, re_path

from .consumers._notfound import PageNotFoundDispatcher
from .page_registry import iter_websocket_endpoints


websocket_urlpatterns = [
    path(f'ws/mfm/<int:mfm_id>/{endpoint}/', dispatcher.as_asgi())
    for endpoint, dispatcher in iter_websocket_endpoints()
]

# Catch-all — any unknown `ws/mfm/{id}/<page>/` closes cleanly with 4404
# instead of Daphne's HTTP 500 default. MUST be last.
websocket_urlpatterns.append(
    re_path(r'^ws/mfm/(?P<mfm_id>\d+)/[\w-]+/$', PageNotFoundDispatcher.as_asgi()),
)
