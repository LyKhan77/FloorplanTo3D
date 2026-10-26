import pytest
from jinja2 import Template


def test_jinja_html_renders_to_pdf():
    # Import here: a missing pango must fail this test only, not abort collection of the suite.
    try:
        from weasyprint import HTML
    except OSError as exc:
        pytest.fail(
            "WeasyPrint cannot load pango. Run `brew install pango` and run tests with "
            f"`uv run --env-file .env pytest` (DYLD_FALLBACK_LIBRARY_PATH). {exc}"
        )
    html = Template("<h1>{{ title }}</h1><p>Luas {{ area }} m²</p>").render(
        title="MSC Gatsu", area=57.62
    )
    pdf = HTML(string=html).write_pdf()
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000
