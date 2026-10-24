"""Política común para contenido nuevo e histórico, incluidas fórmulas."""
import nh3

TAGS = set("a img br strong b code pre p div em span h1 h2 h3 h4 h5 h6 blockquote ul ol tr th td hr li u s table thead tbody caption small q sup sub font del strike".split())
ATTRS = {"*": {"class", "style"}, "img": {"src", "width", "height", "alt"},
         "a": {"href", "target", "title"}, "table": {"border", "cellpadding", "cellspacing"},
         "td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan"}, "font": {"color"}}
STYLES = {"color", "background-color", "text-align", "font-size", "font-weight", "font-style", "text-decoration", "white-space", "vertical-align", "border", "border-color", "border-width", "border-style", "padding", "margin-left"}


def clean_html(value):
    return nh3.clean(value or "", tags=TAGS, attributes=ATTRS, url_schemes={"http", "https", "mailto"},
                     filter_style_properties=STYLES, link_rel="noopener noreferrer")
