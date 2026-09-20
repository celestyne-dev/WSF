# Flask-RESTful resources / blueprints, one module per versioned API
# namespace, mirroring frontend/src/api/*.js exactly:
#
#   /api/v1/auth/            /api/v1/articles/        /api/v1/topics/
#   /api/v1/categories/      /api/v1/tags/            /api/v1/series/
#   /api/v1/authors/         /api/v1/people/          /api/v1/organizations/
#   /api/v1/resources/       /api/v1/events/          /api/v1/opportunities/
#   /api/v1/jobs/            /api/v1/newsletter/      /api/v1/submissions/
#   /api/v1/nominations/     /api/v1/partnerships/    /api/v1/search/
#   /api/v1/media/           /api/v1/products/        /api/v1/payments/
#   /api/v1/admin/           /api/v1/analytics/       /api/v1/public/
#
# Public article URLs are flat (womenshapingfutures.org/{slug}) on the
# frontend, but the API stays namespaced: GET /api/v1/articles/{slug}.
