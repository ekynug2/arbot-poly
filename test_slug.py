"""Test slug-based market discovery."""
import time
import requests

now = int(time.time())
window = now - (now % 300)

for offset in [-300, 0, 300]:
    ts = window + offset
    slug = f"btc-updown-5m-{ts}"
    res = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}").json()
    if res:
        e = res[0]
        title = e.get("title", "")
        active = e.get("active")
        m_list = e.get("markets", [])
        print(f"FOUND! slug={slug}")
        print(f"  title: {title}")
        print(f"  active: {active}")
        if m_list:
            m = m_list[0]
            print(f"  market active: {m.get('active')}")
            print(f"  market closed: {m.get('closed')}")
            tokens = m.get("clobTokenIds", [])
            print(f"  clobTokenIds: {tokens}")
    else:
        print(f"Not found: {slug}")
