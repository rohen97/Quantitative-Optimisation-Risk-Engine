from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape


class ICReportRenderer:
    def __init__(self, template_directory: Path) -> None:
        self.environment = Environment(
            loader=FileSystemLoader(str(template_directory)),
            autoescape=select_autoescape(["html", "xml"]),
            undefined=StrictUndefined,
        )

    def render(self, template_name: str, context: dict, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        template = self.environment.get_template(template_name)
        output_path.write_text(template.render(**context), encoding="utf-8")
        return output_path


def render_html_report(context: dict[str, object], template_path: Path, output_path: Path) -> Path:
    renderer = ICReportRenderer(template_path.parent)
    return renderer.render(template_path.name, context, output_path)
