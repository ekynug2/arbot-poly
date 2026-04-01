"""Quick script to debug Gamma API event discovery."""
import requests

for offset in range(0, 3000, 500):
    url = f"https://gamma-api.polymarket.com/events?limit=500&offset={offset}&active=true&closed=false"
    events = requests.get(url).json()
    for e in events:
        s = e.get("slug", "")
        if "btc-updown-5m" in s:
            t = e.get("title", "")
            print(f"FOUND at offset {offset}!")
            print(f"  slug: {s}")
            print(f"  title: {t}")
            print(f"  active: {e.get('active')}")
            m_list = e.get("markets", [])
            print(f"  markets count: {len(m_list)}")
            if m_list:
                m = m_list[0]
                print(f"  market active: {m.get('active')}")
                print(f"  market closed: {m.get('closed')}")
                print(f"  clobTokenIds: {m.get('clobTokenIds')}")
            exit(0)
    if len(events) < 500:
        print(f"Exhausted at offset {offset}, checked {offset + len(events)} events")
        break

print("NOT FOUND in 3000 events")
