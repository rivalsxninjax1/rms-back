# FILE: orders/middleware.py
class EnsureCartInitializedMiddleware:
    """
    For anonymous users, ensure 'cart' exists and starts empty on first hit.
    We also mark a small flag to avoid re-initializing on every request.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            user = getattr(request, "user", None)
            if not user or getattr(user, "is_anonymous", True):
                if not request.session.get("_cart_init_done"):
                    request.session["cart"] = []
                    request.session["_cart_init_done"] = True
                    request.session.modified = True
        except Exception:
            # Never break page load
            pass
        return self.get_response(request)
