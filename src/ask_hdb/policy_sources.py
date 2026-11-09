"""Fixed policy sources, taken from the dated rules. No crawling."""

from urllib.parse import urlsplit

BASE = "https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility"
POLICY_URLS = (
    f"{BASE}/couples-and-families",
    f"{BASE}/couples-and-families/cpf-housing-grants",
    f"{BASE}/couples-and-families/enhanced-cpf-housing-grant",
    f"{BASE}/couples-and-families/proximity-housing-grant",
    f"{BASE}/singles",
    f"{BASE}/singles/cpf-housing-grant",
    f"{BASE}/singles/enhanced-cpf-housing-grant",
    f"{BASE}/singles/proximity-housing-grant",
    f"{BASE}/housing-loan/housing-loan-from-hdb",
    "https://www.hdb.gov.sg/managing-my-home/finances/loan-matters/interest-rate",
)
# There are no CPF HTML sources in the current rules. Add one only with a source review.
HOSTS = {"hdb.gov.sg", "www.hdb.gov.sg", "cpf.gov.sg", "www.cpf.gov.sg"}


def validate_url(url):
    """Check redirects too, before any request can leave the official sites."""
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname not in HOSTS or parts.username
            or parts.password or parts.port not in {None, 443} or parts.fragment):
        raise ValueError("Policy URL must use an official HDB or CPF HTTPS domain")
    return url
