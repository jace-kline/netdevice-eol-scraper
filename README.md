# ReluTech EOL/EOSL Scraper

A Python web scraper that automatically collects End of Life (EOL) and End of Service Life (EOSL) dates for network device models from multiple vendors on the ReluTech website. This tool helps IT professionals, procurement teams, and asset managers track product lifecycle information to make informed decisions about hardware purchases and maintenance planning.

## Overview

This scraper extracts EOL and EOSL information from [ReluTech's EOL/EOSL directory](https://relutech.com/eol-eosl/) for various network equipment vendors. It automatically discovers available vendors, scrapes paginated data tables, normalizes date formats, and outputs structured CSV files ready for analysis.

## Features

- **Automatic Vendor Discovery**: Dynamically discovers available vendors by parsing the site's XML sitemap
- **Multi-Vendor Support**: Scrapes data from multiple network equipment vendors in a single run
- **Pagination Handling**: Automatically handles paginated results across multiple pages
- **Robust Date Parsing**: Intelligently parses dates in various formats (abbreviated and full month names)
- **Data Normalization**: Converts all dates to UTC ISO 8601 format for consistency
- **Duplicate Removal**: Automatically removes duplicate entries and merges date information
- **Error Resilience**: Continues scraping other vendors even if one fails
- **Timestamped Output**: Saves CSV files with timestamps to prevent overwriting previous runs

## Requirements

### Python Version
- Python 3.8 or higher (uses type hints with `int | None` syntax)

### Required Dependencies
- `requests` - HTTP library for making web requests
- `beautifulsoup4` - HTML parsing library
- `pandas` - Data manipulation and CSV export
- `urllib3` - HTTP client library (usually comes with requests)

### Optional Dependencies
- `python-dateutil` - Enhanced date parsing (recommended for better date format support)

## Installation

1. **Clone or download this repository**

2. **Install required packages using pip:**

```bash
pip install requests beautifulsoup4 pandas urllib3
```

3. **Install optional date parsing library (recommended):**

```bash
pip install python-dateutil
```

## Usage

### Basic Usage

Run the scraper with default settings:

```bash
python relutech_scraper.py
```

This will:
- Automatically discover all available vendors from the sitemap
- Scrape all pages for each vendor (up to 100 pages per vendor by default)
- Process and normalize the data
- Save results to a timestamped CSV file (e.g., `relutech_eol_eosl_20240115_143022.csv`)

### Programmatic Usage

You can also import and use the scraper functions in your own Python scripts:

```python
from relutech_scraper import scrape_eol_data

# Scrape all vendors with default settings
df = scrape_eol_data()

# Scrape specific vendors only
df = scrape_eol_data(vendors=['cisco', 'dell', 'hpe'])

# Limit pages per vendor
df = scrape_eol_data(max_pages=50)

# Combine both options
df = scrape_eol_data(vendors=['cisco', 'juniper'], max_pages=25)
```

### Function Reference

#### `scrape_eol_data(vendors=None, max_pages=100)`

Main entry point for scraping EOL/EOSL data.

**Parameters:**
- `vendors` (list[str] | None): Optional list of vendor names to scrape. If `None`, all vendors are discovered automatically.
- `max_pages` (int): Maximum number of pages to scrape per vendor (default: 100)

**Returns:**
- `pd.DataFrame`: A pandas DataFrame with columns: `vendor`, `model`, `eol_date`, `eosl_date`

#### `get_unique_eol_vendors()`

Discovers available vendors from the ReluTech sitemap.

**Returns:**
- `list[str]`: Sorted list of vendor names

**Note:** Falls back to a hardcoded vendor list if sitemap parsing fails.

#### `scrape_vendor_eol_url(base_url, max_pages=50)`

Scrapes all pages for a single vendor URL.

**Parameters:**
- `base_url` (str): Base URL for the vendor's EOL/EOSL page
- `max_pages` (int): Maximum number of pages to scrape

**Returns:**
- `pd.DataFrame`: DataFrame with `model`, `eol_date`, `eosl_date` columns

## How It Works

### Architecture Overview

The scraper follows a multi-stage pipeline:

1. **Vendor Discovery** → 2. **Data Scraping** → 3. **Data Processing** → 4. **Output Generation**

### Detailed Workflow

#### 1. Vendor Discovery (`get_unique_eol_vendors()`)

- Fetches the XML sitemap from `https://relutech.com/sitemap-1.xml`
- Parses XML to extract URLs under the `/eol-eosl/` path
- Extracts vendor names from URL structure (e.g., `https://relutech.com/eol-eosl/cisco` → `cisco`)
- Falls back to a hardcoded vendor list if XML parsing fails

#### 2. Data Scraping (`scrape_vendor_eol_url()`)

For each vendor:
- Constructs the vendor URL: `https://relutech.com/eol-eosl/{vendor}`
- Iterates through paginated pages (page 1, 2, 3, ...)
- For each page:
  - Makes HTTP GET request with browser-like headers
  - Parses HTML using BeautifulSoup
  - Locates the data table by searching for headers containing "Model", "EOL Date", "EOSL Date"
  - Extracts rows from the table body
  - Stops when an empty page is encountered or `max_pages` is reached

#### 3. Data Processing (`post_process_eol_df()`)

The raw scraped data undergoes several transformations:

- **Vendor Normalization**: Converts vendor names to uppercase (e.g., `cisco` → `CISCO`)
- **Date Parsing**: Robust multi-strategy date parsing:
  - Tries abbreviated month format: `"Aug 31, 2022"`
  - Tries full month format: `"August 31, 2022"`
  - Falls back to pandas flexible parsing
  - Uses `python-dateutil` if available for maximum compatibility
- **Date Conversion**: Converts all dates to UTC ISO 8601 format (e.g., `"2022-08-31T00:00:00+00:00"`)
- **Column Reordering**: Places `vendor` as the first column
- **Deduplication**: Removes duplicate rows based on `vendor` and `model`, merging date information when duplicates exist

#### 4. Output Generation

- Combines all vendor data into a single DataFrame
- Saves to CSV with timestamp: `relutech_eol_eosl_YYYYMMDD_HHMMSS.csv`
- Prints summary statistics and preview of the data

## Output Format

The scraper generates CSV files with the following structure:

| Column | Description | Format | Example |
|--------|-------------|--------|---------|
| `vendor` | Vendor name | Uppercase string | `CISCO` |
| `model` | Device model name | String | `Catalyst 2960-X` |
| `eol_date` | End of Life date | UTC ISO 8601 datetime or null | `2022-08-31T00:00:00+00:00` |
| `eosl_date` | End of Service Life date | UTC ISO 8601 datetime or null | `2027-08-31T00:00:00+00:00` |

### Date Format Details

- **Format**: ISO 8601 with UTC timezone (`YYYY-MM-DDTHH:MM:SS+00:00`)
- **Null Values**: Empty or invalid dates are stored as empty strings in CSV
- **Timezone**: All dates are normalized to UTC

## Supported Vendors

The scraper supports the following vendors (discovered automatically, but typically includes):

- Cisco
- Dell
- EMC
- EMC-Ecomm
- HPE (Hewlett Packard Enterprise)
- IBM
- Juniper
- NetApp-Ecomm
- Nimble
- Sun-Oracle

**Note:** The actual list of vendors is dynamically discovered from the sitemap and may change over time.

## Configuration

### Constants

You can modify these constants in the script to customize behavior:

- `SITEMAP_URL`: URL of the sitemap XML (default: `"https://relutech.com/sitemap-1.xml"`)
- `BASE_PATH`: Base path for EOL/EOSL pages (default: `"https://relutech.com/eol-eosl/"`)
- `HEADERS`: HTTP headers used for requests (mimics a real browser)
- `max_pages`: Maximum pages per vendor (default: 100 in `scrape_eol_data()`, 50 in `scrape_vendor_eol_url()`)

### SSL Verification

The scraper currently disables SSL verification (`verify=False`) to handle potential certificate issues. For production use, consider enabling SSL verification and handling certificates properly.

## Error Handling

The scraper includes several error handling mechanisms:

- **Sitemap Parsing Failures**: Falls back to hardcoded vendor list
- **Individual Vendor Failures**: Continues scraping other vendors if one fails
- **Empty Pages**: Automatically stops pagination when empty pages are encountered
- **Date Parsing Failures**: Invalid dates are stored as `null`/empty values
- **Network Timeouts**: 20-second timeout per request prevents indefinite hangs

## Example Output

```
Found 10 vendors: ['cisco', 'dell', 'emc', 'emc-ecomm', 'hpe', 'ibm', 'juniper', 'netapp-ecomm', 'nimble', 'sun-oracle']

Scraping vendor: cisco (https://relutech.com/eol-eosl/cisco)
Page 1 fetched
Page 2 fetched
...
  Scraped 245 rows for cisco

Scraping vendor: dell (https://relutech.com/eol-eosl/dell)
Page 1 fetched
...
  Scraped 189 rows for dell

...

Total rows scraped: 1234

First few rows:
  vendor              model              eol_date                    eosl_date
0 CISCO    Catalyst 2960-X    2022-08-31T00:00:00+00:00  2027-08-31T00:00:00+00:00
1 CISCO    Catalyst 3750-X    2021-06-30T00:00:00+00:00  2026-06-30T00:00:00+00:00
...

Data saved to relutech_eol_eosl_20240115_143022.csv
```

## Limitations

- **Rate Limiting**: The scraper does not implement rate limiting. Be respectful of the target website's resources.
- **Website Changes**: If ReluTech changes their HTML structure, the scraper may need updates.
- **SSL Verification**: Currently disabled for compatibility; consider enabling for production use.
- **Pagination Detection**: Stops at first empty page; may miss data if pagination structure changes.
