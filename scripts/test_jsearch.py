import os
import requests
from dotenv import load_dotenv

def main():
    load_dotenv()

    api_key = os.getenv("JSEARCH_API_KEY", "").strip()
    rapidapi_host = os.getenv("JSEARCH_RAPIDAPI_HOST", "jsearch.p.rapidapi.com").strip()

    url = f"https://{rapidapi_host}/search"
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": rapidapi_host,
    }
    params = {
        "query": "developer jobs in chicago",
        "page": "1",
        "num_pages": "1",
    }

    print("=== JSEARCH STANDALONE DEBUG SCRIPT ===")
    print(f"Target URL: {url}")
    print(f"Host Header (repr): {repr(rapidapi_host)}")
    print(f"API Key Length: {len(api_key)}")

    safe_headers = {k: ("[REDACTED]" if "Key" in k else v) for k, v in headers.items()}
    print(f"Headers: {safe_headers}")
    print(f"Query Params: {params}")

    req = requests.Request("GET", url, headers=headers, params=params).prepare()
    print(f"\nExact Prepared Resolved URL:\n  {req.url}")

    resp = requests.get(url, headers=headers, params=params, timeout=15)

    print(f"\nHTTP Status Code: {resp.status_code}")
    print(f"Response Headers: {dict(resp.headers)}")
    print(f"Response Body:\n  {resp.text}")

if __name__ == "__main__":
    main()
