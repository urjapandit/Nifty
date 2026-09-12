#!/usr/bin/env python3
"""Download NSE CM UDiFF daily bhavcopy ZIPs for 01-Jun-2026 .. 11-Sep-2026.

Creates NSE_Bhavcopy_Jun_Sep_2026/ (one ZIP per trading day) and bundles the
verified files into NSE_Bhavcopy_Jun_Sep_2026.zip.

Every downloaded file is verified to be a real ZIP archive containing at least
one non-empty CSV member. Files that fail verification are deleted and reported
as missing. Nothing is ever fabricated or synthesised.
"""

import datetime as dt
import os
import shutil
import sys
import time
import zipfile

try:
    import requests
except ImportError:
    sys.exit(
        "The 'requests' package is required.\n"
        "Install it with:  python3 -m pip install requests"
    )

# --- Fixed date range. Do not modify. ---------------------------------------
START_DATE = dt.date(2026, 6, 1)
END_DATE = dt.date(2026, 9, 11)

OUT_DIR = "NSE_Bhavcopy_Jun_Sep_2026"
OUT_ZIP = "NSE_Bhavcopy_Jun_Sep_2026.zip"

FILENAME = "BhavCopy_NSE_CM_0_0_0_{stamp}_F_0000.csv.zip"

# Primary archive endpoint, then the fallback used when NSE blocks the first.
ENDPOINTS = (
    "https://nsearchives.nseindia.com/content/cm/{name}",
    "https://archives.nseindia.com/content/cm/{name}",
)

HOME_URL = "https://www.nseindia.com/all-reports"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/zip,application/octet-stream,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/all-reports",
    "Connection": "keep-alive",
}

MAX_ATTEMPTS = 3
TIMEOUT = 45


def trading_weekdays(start, end):
    """Yield every Mon-Fri date in the range. Holidays are discovered by a 404."""
    day = start
    while day <= end:
        if day.weekday() < 5:
            yield day
        day += dt.timedelta(days=1)


def make_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        # Warm up so NSE issues the cookies its archive hosts expect.
        session.get(HOME_URL, timeout=TIMEOUT)
    except requests.RequestException as exc:
        print(f"  ! cookie warm-up failed ({exc}); continuing anyway")
    return session


def verify_zip(path):
    """Return (ok, detail). A valid file is a ZIP holding a non-empty CSV."""
    if not zipfile.is_zipfile(path):
        return False, "not a ZIP archive"
    try:
        with zipfile.ZipFile(path) as zf:
            if zf.testzip() is not None:
                return False, "corrupt ZIP member"
            csvs = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not csvs:
                return False, "no CSV inside ZIP"
            with zf.open(csvs[0]) as fh:
                header = fh.readline()
            if not header.strip():
                return False, f"empty CSV ({csvs[0]})"
    except zipfile.BadZipFile as exc:
        return False, f"bad ZIP ({exc})"
    return True, csvs[0]


def download_day(session, day, dest_dir):
    """Download and verify one day. Returns (status, detail)."""
    stamp = day.strftime("%Y%m%d")
    name = FILENAME.format(stamp=stamp)
    dest = os.path.join(dest_dir, name)

    if os.path.exists(dest):
        ok, detail = verify_zip(dest)
        if ok:
            return "cached", detail
        os.remove(dest)

    last = "no endpoint responded"
    for template in ENDPOINTS:
        url = template.format(name=name)
        host = url.split("/")[2]
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                resp = session.get(url, timeout=TIMEOUT, stream=True)
            except requests.RequestException as exc:
                last = f"{host}: {exc}"
                time.sleep(2 * attempt)
                continue

            if resp.status_code == 404:
                resp.close()
                last = f"{host}: 404 (market holiday or file not published)"
                break  # A 404 will not change on retry; try the next endpoint.

            if resp.status_code != 200:
                resp.close()
                last = f"{host}: HTTP {resp.status_code}"
                time.sleep(2 * attempt)
                continue

            tmp = dest + ".part"
            with open(tmp, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        fh.write(chunk)
            resp.close()

            ok, detail = verify_zip(tmp)
            if ok:
                os.replace(tmp, dest)
                return "ok", detail
            os.remove(tmp)
            last = f"{host}: {detail}"
            time.sleep(2 * attempt)

    return "missing", last


def main():
    base = os.path.abspath(os.path.dirname(__file__) or ".")
    dest_dir = os.path.join(base, OUT_DIR)
    os.makedirs(dest_dir, exist_ok=True)

    days = list(trading_weekdays(START_DATE, END_DATE))
    print(
        f"NSE CM UDiFF bhavcopy: {START_DATE:%d-%b-%Y} to {END_DATE:%d-%b-%Y} "
        f"({len(days)} weekdays)\n"
    )

    valid, missing = [], []
    session = make_session()

    for day in days:
        status, detail = download_day(session, day, dest_dir)
        if status in ("ok", "cached"):
            valid.append(day)
            mark = "ok    " if status == "ok" else "cached"
            print(f"  {day:%d-%b-%Y}  {mark}  {detail}")
        else:
            missing.append((day, detail))
            print(f"  {day:%d-%b-%Y}  --      {detail}")
        time.sleep(0.4)  # Stay polite to NSE.

    zip_path = os.path.join(base, OUT_ZIP)
    if valid:
        if os.path.exists(zip_path):
            os.remove(zip_path)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as bundle:
            for day in valid:
                name = FILENAME.format(stamp=day.strftime("%Y%m%d"))
                bundle.write(os.path.join(dest_dir, name), arcname=name)
            manifest = "\n".join(
                f"{d:%Y-%m-%d},{FILENAME.format(stamp=d.strftime('%Y%m%d'))}"
                for d in valid
            )
            bundle.writestr("manifest.csv", "date,file\n" + manifest + "\n")

    print(f"\nValid trading-day files: {len(valid)}")
    print(f"Weekdays with no file:   {len(missing)}")
    for day, detail in missing:
        print(f"  {day:%d-%b-%Y}  {detail}")

    if valid:
        size = os.path.getsize(zip_path)
        print(f"\nBundle: {zip_path}  ({size / 1_048_576:.2f} MiB)")
    else:
        print("\nNo valid files downloaded, so no bundle was created.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
