# Services package.
#
# Each module exposes a focused set of async functions that encapsulate
# business logic and database access for a single domain aggregate:
#
#   article_service  — CRUD + pagination + cache for Article
#   comment_service  — append-only comment creation for Article
#   user_service     — CRUD for User
#
# All service functions accept an AsyncSession as their first argument
# so that the router layer controls the transaction boundary via the
# ``get_db`` dependency.
