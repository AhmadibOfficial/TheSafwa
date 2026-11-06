"""Per-request canonical origin; caller supplies an explicitly validated public URL."""
from contextvars import ContextVar

PUBLIC_ORIGIN = ContextVar('safwa_public_origin', default='https://thesafwa.onrender.com')
