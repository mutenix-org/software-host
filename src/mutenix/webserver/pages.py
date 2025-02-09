import logging
import pathlib
from collections import defaultdict

import markdown
import yaml
from aiohttp import web
from mutenix.models.state import State
from mutenix.webserver.helper import Helper


_logger = logging.getLogger(__name__)


class PageHandler:
    def __init__(self, state: State) -> None:
        self._state = state

    async def help(self, request: web.Request) -> web.Response:
        return Helper.render_template("help.html", request, {})

    def _read_markdown(self, filename: str) -> str:
        base_path = pathlib.Path(__file__).parent
        src_root = base_path.parent.parent.parent
        paths = [base_path, src_root]
        for path in paths:
            try:
                content = (path / filename).open().read()
            except Exception as e:
                _logger.info(f"{filename} not found: Exception {e}")
                continue
        else:
            content = f"{filename} not found"

        html_content = markdown.markdown(
            content,
            extensions=["fenced_code", "tables"],
        )

        return html_content

    async def about(self, request: web.Request) -> web.Response:
        html_readme_content = self._read_markdown("README.md")
        html_license_content = self._read_markdown("LICENSE")
        context = {
            "readme_content": html_readme_content,
            "license_content": html_license_content,
        }
        return Helper.render_template("about.html", request, context)

    async def config(self, request: web.Request) -> web.Response:
        button_actions: defaultdict[int, dict] = defaultdict(dict)

        for action in self._state.config.actions:
            button_actions[action.button_id]["action"] = action

        for longpress_action in self._state.config.longpress_action:
            button_actions[longpress_action.button_id]["longpress_action"] = (
                longpress_action
            )
        context = {
            "button_actions": button_actions,
            "leds": self._state.config.leds,
            "yaml_config": yaml.dump(
                self._state.config.model_dump(
                    mode="json",
                    exclude_none=True,
                    exclude_unset=True,
                ),
            ),
        }
        return Helper.render_template("config.html", request, context)

    async def device(self, request: web.Request) -> web.Response:
        return Helper.render_template(
            "version.html",
            request,
            {
                "version": self._state.hardware.version,
                "hardware": self._state.hardware.variant,
            },
        )

    def setup_routes(self, app: web.Application, prefix: str = "/pages") -> None:
        app.router.add_route("GET", f"{prefix}/help", self.help)
        app.router.add_route("GET", f"{prefix}/about", self.about)
        app.router.add_route("GET", f"{prefix}/config", self.config)
        app.router.add_route("GET", f"{prefix}/device", self.device)
