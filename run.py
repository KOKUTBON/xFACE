"""Unified application entrypoint for xFACE."""

from xface import __version__
from xface.config import settings
from xface.web.app import create_app

app = create_app(start_services=True)

if __name__ == "__main__":
    host = settings.WEB_HOST
    port = settings.WEB_PORT
    display_host = "localhost" if host in ("0.0.0.0", "::") else host

    print("=" * 60)
    print(f"  xFACE {__version__} - Biometric Access Control System")
    print(f"  Dashboard:    http://{display_host}:{port}/dashboard")
    print(f"  Live Monitor: http://{display_host}:{port}/monitor")
    print(f"  Access Logs:  http://{display_host}:{port}/logs")
    print("=" * 60)

    # The reloader would start a second process that competes for the camera device
    app.run(host=host, port=port, debug=settings.DEBUG, use_reloader=False, threaded=True)
