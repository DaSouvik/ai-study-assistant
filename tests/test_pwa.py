from html.parser import HTMLParser
import json
from pathlib import Path
import struct
import unittest
from urllib.parse import parse_qs, urlparse


PWA_DIRECTORY = Path(__file__).resolve().parents[1] / "pwa"


class _PwaDocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.manifest_links: list[str] = []
        self.app_frames: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "link" and attributes.get("rel") == "manifest":
            href = attributes.get("href")
            if href is not None:
                self.manifest_links.append(href)
        if tag == "iframe":
            src = attributes.get("src")
            if src is not None:
                self.app_frames.append(src)


class PwaTests(unittest.TestCase):
    def test_manifest_has_install_metadata_and_valid_icons(self) -> None:
        manifest = json.loads(
            (PWA_DIRECTORY / "manifest.webmanifest").read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["name"], "Study Desk")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["scope"], "/")

        icon_sizes = {icon["sizes"] for icon in manifest["icons"]}
        self.assertTrue({"192x192", "512x512"}.issubset(icon_sizes))
        for icon in manifest["icons"]:
            image = (PWA_DIRECTORY / icon["src"].lstrip("/")).read_bytes()
            self.assertEqual(image[:8], b"\x89PNG\r\n\x1a\n")
            dimensions = struct.unpack(">II", image[16:24])
            self.assertEqual(dimensions, tuple(map(int, icon["sizes"].split("x"))))

    def test_wrapper_links_manifest_and_uses_streamlit_embed_url(self) -> None:
        parser = _PwaDocumentParser()
        parser.feed((PWA_DIRECTORY / "index.html").read_text(encoding="utf-8"))

        self.assertEqual(parser.manifest_links, ["/manifest.webmanifest"])
        self.assertEqual(len(parser.app_frames), 1)
        app_url = urlparse(parser.app_frames[0])
        self.assertEqual(app_url.scheme, "https")
        self.assertEqual(app_url.netloc, "dasouvik-ai-study-assistant-app-ho0the.streamlit.app")
        self.assertEqual(parse_qs(app_url.query).get("embed"), ["true"])


if __name__ == "__main__":
    unittest.main()
