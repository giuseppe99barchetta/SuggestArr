import os
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

from api_service.frontend_routes import SubpathMiddleware, normalize_subpath, register_routes


class TestFrontendRoutes(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        static_root = self.tempdir.name
        os.makedirs(os.path.join(static_root, "js"), exist_ok=True)
        os.makedirs(os.path.join(static_root, "css"), exist_ok=True)

        with open(os.path.join(static_root, "index.html"), "w", encoding="utf-8") as handle:
            handle.write(
                '<html><head></head><body>'
                '<script src="js/app.123.js"></script>'
                '<link href="css/app.123.css" rel="stylesheet">'
                "</body></html>"
            )

        with open(os.path.join(static_root, "js", "app.123.js"), "w", encoding="utf-8") as handle:
            handle.write("console.log('ok');")

        with open(os.path.join(static_root, "css", "app.123.css"), "w", encoding="utf-8") as handle:
            handle.write("body { color: red; }")

        with open(os.path.join(static_root, "favicon.ico"), "wb") as handle:
            handle.write(b"\x00\x00\x01\x00")

        app = Flask(__name__, static_folder=static_root)
        app.config["TESTING"] = True
        register_routes(app)
        self.client = app.test_client()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_normalize_subpath_enforces_single_leading_slash(self):
        self.assertEqual(normalize_subpath("suggestarr/"), "/suggestarr")
        self.assertEqual(normalize_subpath("/suggestarr/"), "/suggestarr")
        self.assertEqual(normalize_subpath(""), "")
        self.assertEqual(normalize_subpath(None), "")

    def test_subpath_root_returns_html_with_injected_tags(self):
        with patch("api_service.frontend_routes.load_env_vars", return_value={"SUBPATH": "/suggestarr/"}):
            response = self.client.get("/suggestarr/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        body = response.get_data(as_text=True)
        self.assertIn('<meta name="suggestarr-subpath" content="/suggestarr">', body)
        self.assertIn('<base href="/suggestarr/">', body)
        self.assertIn('src="js/app.123.js"', body)
        self.assertIn('href="css/app.123.css"', body)

    def test_subpath_env_var_drives_index_tags(self):
        with patch.dict(os.environ, {"SUBPATH": "/suggestarr"}), \
             patch("api_service.frontend_routes.load_env_vars", return_value={"SUBPATH": None}):
            response = self.client.get("/suggestarr/")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('<meta name="suggestarr-subpath" content="/suggestarr">', body)
        self.assertIn('<base href="/suggestarr/">', body)

    def test_subpath_js_asset_serves_javascript_not_html(self):
        with patch("api_service.frontend_routes.load_env_vars", return_value={"SUBPATH": "/suggestarr"}):
            response = self.client.get("/suggestarr/js/app.123.js")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("text/html", response.content_type)
        self.assertIn("javascript", response.content_type)
        self.assertEqual(response.get_data(as_text=True), "console.log('ok');")

    def test_subpath_css_asset_serves_css_not_html(self):
        with patch("api_service.frontend_routes.load_env_vars", return_value={"SUBPATH": "/suggestarr"}):
            response = self.client.get("/suggestarr/css/app.123.css")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "text/css; charset=utf-8")
        self.assertEqual(response.get_data(as_text=True), "body { color: red; }")

    def test_missing_frontend_route_falls_back_to_index(self):
        with patch("api_service.frontend_routes.load_env_vars", return_value={"SUBPATH": "/suggestarr"}):
            response = self.client.get("/suggestarr/settings")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        self.assertIn('<base href="/suggestarr/">', response.get_data(as_text=True))

    def test_subpath_favicon_serves_file_not_html(self):
        with patch("api_service.frontend_routes.load_env_vars", return_value={"SUBPATH": "/suggestarr"}):
            response = self.client.get("/suggestarr/favicon.ico")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("text/html", response.content_type)
        self.assertEqual(response.get_data(), b"\x00\x00\x01\x00")

    def test_missing_asset_returns_404(self):
        with patch("api_service.frontend_routes.load_env_vars", return_value={"SUBPATH": "/suggestarr"}):
            response = self.client.get("/suggestarr/js/missing.js")

        self.assertEqual(response.status_code, 404)

    def test_middleware_strips_env_subpath_before_routing_assets(self):
        app = Flask(__name__, static_folder=self.tempdir.name)
        app.config["TESTING"] = True
        register_routes(app)
        app.wsgi_app = SubpathMiddleware(app.wsgi_app)
        client = app.test_client()

        with patch.dict(os.environ, {"SUBPATH": "/suggestarr"}), \
             patch("api_service.frontend_routes.load_env_vars", return_value={"SUBPATH": None}):
            response = client.get("/suggestarr/js/app.123.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.content_type)
        self.assertEqual(response.get_data(as_text=True), "console.log('ok');")

    def test_root_deployment_asset_still_serves(self):
        with patch("api_service.frontend_routes.load_env_vars", return_value={"SUBPATH": None}):
            response = self.client.get("/js/app.123.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.content_type)


if __name__ == "__main__":
    unittest.main()
