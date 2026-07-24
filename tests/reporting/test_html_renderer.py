from src.reporting.html_renderer import render_html_report


def test_html_renderer_writes_template(tmp_path):
    template = tmp_path / "t.html.j2"
    template.write_text("Hello {{ name }}", encoding="utf-8")
    output = render_html_report({"name": "Wolf"}, template, tmp_path / "out.html")
    assert output.read_text(encoding="utf-8") == "Hello Wolf"
