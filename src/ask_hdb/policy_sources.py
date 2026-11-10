"""Fixed official policy pages, taken from the dated rules. The app links to them; it never fetches them."""

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
