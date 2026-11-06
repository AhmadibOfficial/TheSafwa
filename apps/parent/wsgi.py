"""Production WSGI boundary. Only an explicit public origin is trusted."""
from email.message import Message
from http import HTTPStatus
from types import SimpleNamespace
from urllib.parse import urlsplit

from apps.parent.server import Response, Routes, error_page
from packages.content.contracts import Invalid
from packages.config.site import PUBLIC_ORIGIN


class Application:
    def __init__(self, database, origin, *, public_preview=False):
        parsed = urlsplit(origin)
        local = parsed.hostname in {'127.0.0.1', 'localhost'}
        if (parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.path not in {'', '/'}
                or parsed.query or parsed.fragment or parsed.username or parsed.password
                or (parsed.scheme != 'https' and not local)):
            raise Invalid('Use an HTTPS public origin, or HTTP on localhost for local development.')
        self.settings = SimpleNamespace(database=database, secure=parsed.scheme=='https',
                                        hosts={parsed.netloc.lower()},
                                        origins={f'{parsed.scheme}://{parsed.netloc.lower()}'},
                                        public_preview=public_preview)
        self.origin = f'{parsed.scheme}://{parsed.netloc.lower()}'

    def __call__(self, environ, start_response):
        request = Routes()
        request.server = self.settings
        request.command = environ.get('REQUEST_METHOD', 'GET')
        request.path = environ.get('PATH_INFO', '/')
        if environ.get('QUERY_STRING'):
            request.path += '?' + environ['QUERY_STRING']
        request.headers = Message()
        for name, value in environ.items():
            if name.startswith('HTTP_'):
                request.headers[name[5:].replace('_', '-')] = value
        for name in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            if name in environ:
                request.headers[name.replace('_', '-')] = environ[name]
        request.rfile = environ['wsgi.input']
        if request.command not in {'GET', 'HEAD', 'POST'}:
            response, editorial = Response(status=405, headers=(('Allow', 'GET, HEAD, POST'),)), True
        else:
            origin_token = PUBLIC_ORIGIN.set(self.origin)
            try:
                response, editorial = request.dispatch()
            except Exception:
                # Application failures do not disclose records, SQL, filesystem paths or credentials.
                environ['wsgi.errors'].write('Safwa CMS: request failed; inspect service health.\n')
                response, editorial = error_page(500, 'This request could not be completed.'), True
            finally:
                PUBLIC_ORIGIN.reset(origin_token)
        headers, body = request.response_headers(response, editorial=editorial)
        start_response(f'{response.status} {HTTPStatus(response.status).phrase}', headers)
        return [] if request.command == 'HEAD' else [body]
