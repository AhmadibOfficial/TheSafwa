"""Institute routes use the shared approved-template publishing adapter."""
from apps.parent.views import page


def institute(db):
    return page(db, "/institute")
