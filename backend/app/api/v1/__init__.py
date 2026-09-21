# Flask-RESTful resources / blueprints, one module per versioned API
# namespace, mirroring frontend/src/api/*.js. Each module builds its own
# Blueprint + Flask-RESTful Api pair and is registered with its url_prefix
# in app/__init__.py:create_app(). Public article URLs are flat
# (womenshapingfutures.org/{slug}) on the frontend, but the API stays
# namespaced: GET /api/v1/articles/{slug}.
