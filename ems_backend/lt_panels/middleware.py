"""Lightweight middleware for the lt_panels app.

`CacheImmutableMediaMiddleware` stamps long-lived, immutable cache headers
on `/media/3d/*` responses. GLB files are large and content-addressed by
filename, so once a UA fetches one it can cache it forever.
"""


class CacheImmutableMediaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith('/media/3d/'):
            response['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response
