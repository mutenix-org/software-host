# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger matthias@bilger.info
import aiohttp.web as web
from aiohttp_jinja2 import get_env
from mutenix.version import MAJOR
from mutenix.version import MINOR
from mutenix.version import PATCH


class Helper:
    @staticmethod
    def render_template(template_name, request, context, status=200):
        context["mutenix_version"] = f"{MAJOR}.{MINOR}.{PATCH}"
        content = get_env(request.app).get_template(template_name).render(context)
        return web.Response(text=content, content_type="text/html", status=status)
