
def app_url_valid(url):
    """Check whether an app's authorize URL is OK to put in a browser window.

    In short, this means that it starts with http:// or https://"""
    return url.startswith("http://") or url.startswith("https://")

def app_url(url):
    """Filter for unsafe app authorize URL.

    Safe URLs are passed through, unsafe URLs are replaced by a url to a page with an explanation
    instead."""

    if app_url_valid(url):
        return url
    return "/bad_url.html"
