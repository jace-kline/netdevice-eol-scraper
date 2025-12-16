import requests
from bs4 import BeautifulSoup
import pandas as pd
import urllib3
import xml.etree.ElementTree as ET
from datetime import timezone

# Optional import for dateutil parser (fallback for date parsing)
try:
    from dateutil import parser as date_parser
    HAS_DATEUTIL = True
except ImportError:
    HAS_DATEUTIL = False

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

# Derive vendor names from sitemap
# Should be ['cisco', 'dell', 'emc', 'emc-ecomm', 'hpe', 'ibm', 'juniper', 'netapp-ecomm', 'nimble', 'sun-oracle']
def get_unique_eol_vendors():
    """
    Get list of EOL vendor names by parsing the sitemap XML.
    Falls back to a hardcoded list if XML parsing fails.
    
    Returns:
        Sorted list of vendor names
    """
    # Fallback list if XML parsing fails
    fallback_vendors = ['cisco', 'dell', 'emc', 'emc-ecomm', 'hpe', 'ibm', 'juniper', 'netapp-ecomm', 'nimble', 'sun-oracle']
    
    try:
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

        # If we successfully parsed vendors from XML, return them
        if children:
            return sorted(children)
        else:
            # If parsing succeeded but no vendors found, use fallback
            print("Warning: XML parsing succeeded but no vendors found. Using fallback list.")
            return fallback_vendors
            
    except Exception as e:
        # If XML parsing fails for any reason, use fallback list
        print(f"Warning: Failed to parse sitemap XML ({e}). Using fallback vendor list.")
        return fallback_vendors


def scrape_vendor_eol_url(base_url: str, max_pages: int = 50) -> pd.DataFrame:
    """
    Scrape all pages from a given base URL and return a DataFrame with model, eol_date, eosl_date.
    
    Args:
        base_url: The base URL to scrape from
        max_pages: Maximum number of pages to scrape (default: 50)
    
    Returns:
        DataFrame containing all scraped data
    """
    def fetch_page(page: int | None = None) -> pd.DataFrame:
        """Fetch one page and return a DataFrame with model, eol_date, eosl_date."""
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
            return pd.DataFrame(columns=["model", "eol_date", "eosl_date"])

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
                    "model": model,
                    "eol_date": eol_date,
                    "eosl_date": eosl_date,
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
        return pd.DataFrame(columns=["model", "eol_date", "eosl_date"])

    return pd.concat(all_dfs, ignore_index=True)


def scrape_eol_data(vendors: list[str] | None = None, max_pages: int = 100) -> pd.DataFrame:
    """
    Main driver function that scrapes EOL/EOSL data for all vendors.
    
    Args:
        max_pages: Maximum number of pages to scrape per vendor (default: 50)
    
    Returns:
        Combined DataFrame with all EOL/EOSL data including a "vendor" column, post-processed
    """
    # Get all vendor names
    if vendors is None:
        vendors = get_unique_eol_vendors()
    print(f"Found {len(vendors)} vendors: {vendors}")
    
    all_dfs = []
    
    # Scrape each vendor
    for vendor in vendors:
        vendor_url = f"{BASE_PATH}{vendor}"
        print(f"\nScraping vendor: {vendor} ({vendor_url})")
        
        try:
            df = scrape_vendor_eol_url(vendor_url, max_pages=max_pages)
            if not df.empty:
                # Add vendor column
                df["vendor"] = vendor
                all_dfs.append(df)
                print(f"  Scraped {len(df)} rows for {vendor}")
            else:
                print(f"  No data found for {vendor}")
        except Exception as e:
            print(f"  Error scraping {vendor}: {e}")
            continue
    
    # Combine all dataframes
    if not all_dfs:
        return pd.DataFrame(columns=["vendor", "model", "eol_date", "eosl_date"])
    
    combined_df = pd.concat(all_dfs, ignore_index=True)
    
    # Post-process the dataframe
    processed_df = post_process_eol_df(combined_df)
    return processed_df


def post_process_eol_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Post-process the combined dataframe by:
    - Making vendor the first column
    - Converting vendor to uppercase
    - Converting date columns (eol_date, eosl_date) to UTC ISO datetime format (or null if invalid)
    - Removing duplicate rows based on vendor and model, merging date columns when duplicates exist
    
    Args:
        df: The combined DataFrame from scrape_all_vendors()
    
    Returns:
        Post-processed DataFrame with vendor first, uppercase vendor names, ISO datetime dates, and duplicates removed
    """
    # Create a copy to avoid modifying the original
    processed_df = df.copy()
    
    # Convert vendor to uppercase
    if "vendor" in processed_df.columns:
        processed_df["vendor"] = processed_df["vendor"].str.upper()
    
    # Convert date columns to UTC ISO datetime format
    date_columns = ["eol_date", "eosl_date"]
    for col in date_columns:
        if col in processed_df.columns:
            # Robust date parsing function that handles both abbreviated and full month names
            def parse_date_robust(date_str):
                """Parse date string with multiple fallback strategies."""
                if pd.isna(date_str) or not date_str or str(date_str).strip() == "":
                    return None
                
                date_str = str(date_str).strip()
                
                # Try pandas to_datetime with abbreviated month format: "Aug 31, 2022", "Jun 21, 2021"
                dt = pd.to_datetime(date_str, format="%b %d, %Y", errors="coerce")
                if pd.notna(dt):
                    return dt
                
                # Try with full month names: "August 31, 2022", "June 21, 2021"
                dt = pd.to_datetime(date_str, format="%B %d, %Y", errors="coerce")
                if pd.notna(dt):
                    return dt
                
                # Try pandas flexible parsing (handles various formats without specifying format)
                dt = pd.to_datetime(date_str, errors="coerce")
                if pd.notna(dt):
                    return dt
                
                # Fallback to dateutil parser (very flexible, handles both abbreviated and full months)
                if HAS_DATEUTIL:
                    try:
                        dt = date_parser.parse(date_str, fuzzy=False)
                        if dt:
                            return pd.Timestamp(dt)
                    except (ValueError, TypeError, AttributeError):
                        pass
                
                # If all parsing attempts fail, return None
                return None
            
            # Apply robust date parsing
            processed_df[col] = processed_df[col].apply(parse_date_robust)
            
            # Convert to UTC and format as ISO string
            # If NaT, keep as None/null
            def convert_to_utc_iso(x):
                if pd.isna(x):
                    return None
                # If timezone-aware, convert to UTC; if naive, assume UTC and attach timezone
                if x.tzinfo is None:
                    x = x.replace(tzinfo=timezone.utc)
                else:
                    x = x.astimezone(timezone.utc)
                return x.isoformat()
            
            processed_df[col] = processed_df[col].apply(convert_to_utc_iso)
    
    # Reorder columns to put vendor first
    if "vendor" in processed_df.columns:
        other_columns = [col for col in processed_df.columns if col != "vendor"]
        column_order = ["vendor"] + other_columns
        processed_df = processed_df[column_order]
    
    # Remove duplicates based on vendor and model, merging date columns
    processed_df = remove_duplicates_and_merge(processed_df)
    
    return processed_df


def remove_duplicates_and_merge(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove duplicate rows based on vendor and model columns.
    When duplicates are found, merge them by filling in missing eol_date and eosl_date values.
    
    Args:
        df: DataFrame with vendor, model, eol_date, eosl_date columns
    
    Returns:
        DataFrame with duplicates removed and date columns merged
    """
    if "vendor" not in df.columns or "model" not in df.columns:
        return df
    
    date_columns = ["eol_date", "eosl_date"]
    
    # Helper function to get first non-null value from a series
    def first_non_null(series):
        """Return the first non-null, non-None value from a series."""
        for val in series:
            if pd.notna(val) and val is not None and str(val).strip() != "":
                return val
        return None
    
    # Group by vendor and model
    grouped = df.groupby(["vendor", "model"])
    
    # Define aggregation strategy
    agg_dict = {}
    
    # For date columns, use custom function to get first non-null value
    for col in date_columns:
        if col in df.columns:
            agg_dict[col] = first_non_null
    
    # For other columns, take the first value
    for col in df.columns:
        if col not in ["vendor", "model"] + date_columns:
            agg_dict[col] = "first"
    
    # Apply aggregation
    deduplicated = grouped.agg(agg_dict)
    
    # Reset index to include vendor and model as columns
    deduplicated = deduplicated.reset_index()
    
    return deduplicated


if __name__ == "__main__":
    df = scrape_eol_data()
    print(f"\nTotal rows scraped: {len(df)}")
    print("\nFirst few rows:")
    print(df.head())
    
    # Save to CSV
    output_file = "relutech_eol_eosl.csv"
    df.to_csv(output_file, index=False)
    print(f"\nData saved to {output_file}")
