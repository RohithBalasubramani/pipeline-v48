"""Catch-all WebSocket consumer for unknown ws/asset/{id}/<x>/ paths.

Without this, Daphne rejects unmatched WS routes with HTTP 500 — a clean
4404 close (with an `error` frame first) is friendlier for the frontend.
Mounted as the last entry in routing.py.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer


class PageNotFoundDispatcher(AsyncWebsocketConsumer):
    """Accepts the connection, sends a single `error` frame, then closes 4404."""

    async def connect(self):
        await self.accept()
        asset_id = self.scope['url_route']['kwargs'].get('asset_id', '?')
        path = self.scope.get('path', '')
        page = path.rstrip('/').rsplit('/', 1)[-1] or '<unknown>'
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': f"Page '{page}' not registered for asset_id={asset_id}",
        }))
        await self.close(code=4404)

    async def disconnect(self, code):
        pass

    async def receive(self, text_data=None, bytes_data=None):
        pass
