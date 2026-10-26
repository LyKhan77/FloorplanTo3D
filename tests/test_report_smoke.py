from jinja2 import Template
from weasyprint import HTML


def test_jinja_html_renders_to_pdf():
    html = Template("<h1>{{ title }}</h1><p>Luas {{ area }} m²</p>").render(
        title="MSC Gatsu", area=57.62
    )
    pdf = HTML(string=html).write_pdf()
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000
