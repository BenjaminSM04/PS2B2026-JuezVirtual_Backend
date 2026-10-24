from utils.sanitize import clean_html


class XSSHtml:
    def __init__(self, allows=None):
        self.content = ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def clean(self, content):
        return clean_html(content)

    def feed(self, content):
        self.content += content

    def close(self):
        pass

    def get_html(self):
        return clean_html(self.content)


def filter_html(content):
    return clean_html(content)
