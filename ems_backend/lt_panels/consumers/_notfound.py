"""Catch-all WebSocket consumer for unknown ws/mfm/{id}/<x>/ paths.

Without this, Daphne rejects unmatched WS routes with HTTP 500 — a clean
4404 close (with an `error` frame first) is much friendlier for the
frontend to handle. Mounted as the last entry in routing.py.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer


class PageNotFoundDispatcher(AsyncWebsocketConsumer):
    """Accepts the connection, sends a single `error` frame, then closes 4404."""

    async def connect(self):
        await self.accept()
        mfm_id = self.scope['url_route']['kwargs'].get('mfm_id', '?')
        # Pull the page slug out of the path for a useful error message
        path = self.scope.get('path', '')
        page = path.rstrip('/').rsplit('/', 1)[-1] or '<unknown>'
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': f"Page '{page}' not registered for mfm_id={mfm_id}",
        }))
        await self.close(code=4404)

    async def disconnect(self, code):
        pass

    async def receive(self, text_data=None, bytes_data=None):
        pass
