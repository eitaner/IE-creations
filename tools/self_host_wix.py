#!/usr/bin/env python3
"""Download every Wix-hosted picture used by index.html into ./photos and point index.html at the local copies.

All-or-nothing: if any picture fails to download, index.html is left untouched.
Run with --offline-test to skip the network (writes 1-byte placeholder files) when testing the rewrite only.
"""
import os, re, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
PHOTOS = os.path.join(ROOT, "photos")
OFFLINE = "--offline-test" in sys.argv
FOUNDER_ID = "7cc125_5b3a703bda824378ab06bda738b7db5d"
UA = {"User-Agent": "Mozilla/5.0 (self-host-wix-images)"}

html = open(INDEX, encoding="utf-8").read()

# every picture id the page uses, and whether it is a normal photo (~mv2.jpg) or a video poster frame (f000.jpg)
photo_ids, poster_ids = set(), set()
for m in re.finditer(r"(7cc125_[0-9a-f]{32})(~mv2\.jpg|f000\.jpg)", html):
    (poster_ids if m.group(2) == "f000.jpg" else photo_ids).add(m.group(1))
photo_ids.discard(FOUNDER_ID)
todo = [(i, i + "~mv2.jpg") for i in sorted(photo_ids)] + [(i, i + "f000.jpg") for i in sorted(poster_ids - photo_ids)]
print(f"{len(todo)} pictures + founder photo to save")

os.makedirs(PHOTOS, exist_ok=True)

def fetch(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return True
    if OFFLINE:
        open(dest, "wb").write(b"x"); return True
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if len(data) < 1000:
                raise ValueError("suspiciously small file")
            open(dest, "wb").write(data); return True
        except Exception as e:
            print(f"  retry {attempt+1} for {os.path.basename(dest)}: {e}")
            time.sleep(2 + attempt * 2)
    return False

failed = []
founder_url = ("https://static.wixstatic.com/media/" + FOUNDER_ID + "~mv2.png/v1/crop/x_73,y_0,w_801,h_801/"
               "fill/w_900,h_900,al_c,q_88/founder.jpg")
if not fetch(founder_url, os.path.join(PHOTOS, "founder.jpg")):
    failed.append("founder")
for pid, src in todo:
    url = f"https://static.wixstatic.com/media/{src}/v1/fit/w_1600,h_1600,q_85/photo.jpg"
    if not fetch(url, os.path.join(PHOTOS, pid + ".jpg")):
        failed.append(pid)
if failed:
    print("FAILED:", failed)
    print("index.html was NOT changed. Re-run the workflow to retry.")
    sys.exit(1)

counts = {"founder": 0, "absolute": 0, "prefix": 0}
html, counts["founder"] = re.subn(r"https://static\.wixstatic\.com/media/" + FOUNDER_ID + r"[^\"'\s]*", "photos/founder.jpg", html)
html, counts["absolute"] = re.subn(r"https://static\.wixstatic\.com/media/(7cc125_[0-9a-f]{32})~mv2\.jpg[^\"'\s]*",
                                   lambda m: "photos/" + m.group(1) + ".jpg", html)
html, counts["prefix"] = re.subn(r"WIX\s*\+\s*([\"'`])(7cc125_[0-9a-f]{32})(?:~mv2\.jpg|f000\.jpg)[^\"'`]*\1",
                                 lambda m: m.group(1) + "photos/" + m.group(2) + ".jpg" + m.group(1), html)
if not re.search(r"\bWIX\s*\+\s*[\"'`]", html):
    html = html.replace("const WIX = 'https://static.wixstatic.com/media/';", "const WIX = '';")
open(INDEX, "w", encoding="utf-8", newline="").write(html)

left = len(re.findall(r"wixstatic", html))
print("rewrote:", counts, "| 'wixstatic' references left:", left)
sys.exit(0 if left == 0 else 2)
