"""ERPNext UI navigation helper."""

class Navigator:
    def __init__(self, page):
        self.page = page

    def go_home(self, base_url):
        self.page.goto(base_url)

    def search_doctype(self, doctype):
        # Global Search should be used for exact DocType navigation.
        return doctype
