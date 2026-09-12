# NSE Bhavcopy Downloader

Downloads official NSE CM UDiFF daily bhavcopy ZIP files for **01-Jun-2026 through
11-Sep-2026** and bundles them into `NSE_Bhavcopy_Jun_Sep_2026.zip`.

## Install

```bash
python3 -m pip install -r requirements.txt
```

On Windows, if `python3` is not available, use `python` instead.

## Run

```bash
python3 download_nse_bhavcopy_claude.py
```

## Output

- `NSE_Bhavcopy_Jun_Sep_2026/` — one verified ZIP per trading day
- `NSE_Bhavcopy_Jun_Sep_2026.zip` — the bundle, plus a `manifest.csv` listing each date and file

## Behaviour

- The date range is fixed in the script and is not configurable.
- Weekends are skipped. Market holidays are discovered from a 404 and reported as missing.
- Each download is verified: it must be a valid ZIP whose members pass a CRC check
  and which contains a non-empty CSV. Anything else, including an HTML block page
  served with a `.zip` name, is deleted and reported as missing.
- Two archive endpoints are tried in order, `nsearchives.nseindia.com` then
  `archives.nseindia.com`, with backoff between attempts.
- Missing files are never fabricated or synthesised.
- Re-running reuses files already downloaded and verified, so an interrupted run resumes.

## Network requirement

The script needs direct outbound HTTPS access to `nseindia.com`. Sandboxed or
proxied environments that restrict egress will fail on every date.
