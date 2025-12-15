import requests
from bs4 import BeautifulSoup
import pandas as pd
import urllib3
import xml.etree.ElementTree as ET

# Disable SSL warnings when verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Headers to mimic a real browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    # "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://relutech.com/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

SITEMAP_URL = "https://relutech.com/sitemap-1.xml"
BASE_PATH = "https://relutech.com/eol-eosl/"

def get_unique_children():
    # Fetch sitemap XML
    resp = requests.get(SITEMAP_URL, headers=HEADERS, timeout=20, verify=False)
    resp.raise_for_status()
    xml_text = resp.text

    # Parse XML
    root = ET.fromstring(xml_text)

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    children = set()

    # Each URL entry is in <urlset><url><loc>...</loc></url>
    for url_elem in root.findall("sm:url", ns):
        loc_elem = url_elem.find("sm:loc", ns)
        if loc_elem is None or not loc_elem.text:
            continue

        loc = loc_elem.text.strip()
        if not loc.startswith(BASE_PATH):
            continue

        # Remove base path and any leading slash
        tail = loc[len(BASE_PATH):].lstrip("/")
        if not tail:
            continue

        # First segment is the direct child
        child = tail.split("/", 1)[0]
        if child:
            children.add(child)

    return sorted(children)

def scrape_url(base_url: str, max_pages: int = 50) -> pd.DataFrame:
    """
    Scrape all pages from a given base URL and return a DataFrame with Model, EOL Date, EOSL Date.
    
    Args:
        base_url: The base URL to scrape from
        max_pages: Maximum number of pages to scrape (default: 50)
    
    Returns:
        DataFrame containing all scraped data
    """
    def fetch_page(page: int | None = None) -> pd.DataFrame:
        """Fetch one page and return a DataFrame with Model, EOL Date, EOSL Date."""
        params = {}
        if page is not None and page > 1:
            params["page"] = page

        resp = requests.get(base_url, params=params, headers=HEADERS, timeout=20, verify=False)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find the main table (first table with header containing 'Model', 'EOL Date', 'EOSL Date')
        table = None
        for t in soup.find_all("table"):
            header_cells = [th.get_text(strip=True) for th in t.find_all("th")]
            if {"Model", "EOL Date", "EOSL Date"}.issubset(set(header_cells)):
                table = t
                break
        if table is None:
            # No table found on this page
            return pd.DataFrame(columns=["Model", "EOL Date", "EOSL Date"])

        rows = []
        for tr in table.find("tbody").find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue

            # Model is a link in the first column
            model = tds[0].get_text(strip=True)
            eol_date = tds[1].get_text(strip=True)
            eosl_date = tds[2].get_text(strip=True)

            rows.append(
                {
                    "Model": model,
                    "EOL Date": eol_date,
                    "EOSL Date": eosl_date,
                }
            )

        return pd.DataFrame(rows)

    # Iterate paginated pages until an empty page is encountered or max_pages reached
    all_dfs = []
    page = 1
    while page <= max_pages:
        df = fetch_page(page)
        if df.empty:
            break
        all_dfs.append(df)
        print(f"Page {page} fetched")
        page += 1

    if not all_dfs:
        return pd.DataFrame(columns=["Model", "EOL Date", "EOSL Date"])

    return pd.concat(all_dfs, ignore_index=True)


def scrape_all_vendors(max_pages: int = 50) -> pd.DataFrame:
    """
    Main driver function that scrapes EOL/EOSL data for all vendors.
    
    Args:
        max_pages: Maximum number of pages to scrape per vendor (default: 50)
    
    Returns:
        Combined DataFrame with all EOL/EOSL data including a "Vendor" column
    """
    # Get all vendor names
    vendors = get_unique_children()
    print(f"Found {len(vendors)} vendors: {vendors}")
    
    all_dfs = []
    
    # Scrape each vendor
    for vendor in vendors:
        vendor_url = f"{BASE_PATH}{vendor}"
        print(f"\nScraping vendor: {vendor} ({vendor_url})")
        
        try:
            df = scrape_url(vendor_url, max_pages=max_pages)
            if not df.empty:
                # Add Vendor column
                df["Vendor"] = vendor
                all_dfs.append(df)
                print(f"  Scraped {len(df)} rows for {vendor}")
            else:
                print(f"  No data found for {vendor}")
        except Exception as e:
            print(f"  Error scraping {vendor}: {e}")
            continue
    
    # Combine all dataframes
    if not all_dfs:
        return pd.DataFrame(columns=["Model", "EOL Date", "EOSL Date", "Vendor"])
    
    combined_df = pd.concat(all_dfs, ignore_index=True)
    return combined_df


if __name__ == "__main__":
    df = scrape_all_vendors(max_pages=50)
    print(f"\nTotal rows scraped: {len(df)}")
    print("\nFirst few rows:")
    print(df.head())
    
    # Save to CSV
    output_file = "all_vendors_eol_eosl.csv"
    df.to_csv(output_file, index=False)
    print(f"\nData saved to {output_file}")
