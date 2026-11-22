#!/usr/bin/env python3
"""Regenerates the Zathroth Trader price list from every NPC shop table.

Run from the repository root: python3 tools/generate_trader_prices.py --write
Without --write it only prints the item count and the shop packet size.
"""
import re, glob, sys

# The trader pays this many times the best NPC price for loot, so players get rich quickly.
LOOT_MULTIPLIER = 30
# Shop prices are 32-bit in the engine.
MAX_PRICE = 4_000_000_000
pat = re.compile(r'\{\s*itemName\s*=\s*"([^"]+)"\s*,\s*clientId\s*=\s*(\d+)\s*,([^}]*)\}')
sources = sorted(f for f in glob.glob("data-otservbr-global/npc/*.lua") if not f.endswith("zathroth_trader.lua")) + ["data/scripts/lib/shops.lua"]
names, plain = {}, set()
max_pay, min_cost = {}, {}          # bounds from every NPC entry, including quest, charge and library shops
for f in sources:
    for name, cid, rest in pat.findall(open(f, encoding="utf-8", errors="replace").read()):
        cid = int(cid); names.setdefault(cid, name)
        b = re.search(r'\bbuy\s*=\s*(\d+)', rest); s = re.search(r'\bsell\s*=\s*(\d+)', rest)
        if b and int(b[1]) > 0: min_cost[cid] = min(min_cost.get(cid, 1 << 62), int(b[1]))
        if s and int(s[1]) > 0: max_pay[cid] = max(max_pay.get(cid, 0), int(s[1]))
        if not (set(re.findall(r'(\w+)\s*=', rest)) - {"buy", "sell"}) and (b or s):
            plain.add(cid)           # only entries without charges or conditions are offered
rows = []
for cid in sorted(plain, key=lambda c: (names[c].lower(), c)):
    pay, cost = max_pay.get(cid, 0), min_cost.get(cid, 0)
    if pay and cost:
        sell = min(pay * LOOT_MULTIPLIER, cost)   # never pays more than the cheapest NPC charges
        buy = max(cost, pay)                      # normal NPC price, never less than the best NPC pays
    elif pay:
        sell = min(pay * LOOT_MULTIPLIER, MAX_PRICE // 2)
        buy = max(sell * 2, sell + 1)             # sold at double what he pays, so no buy-and-resell profit
    else:
        sell, buy = max(1, cost // 4), cost
    assert sell <= buy and buy >= pay and (not cost or sell <= cost)
    rows.append((names[cid], cid, buy, sell))
size = sum(2 + 1 + 2 + len(n) + 12 for n, *_ in rows)
print(f"{len(rows)} items, packet about {size} bytes of 65500 ({100 * size // 65500}%)", file=sys.stderr)
if "--write" in sys.argv:
    shop = "\n".join(f'\t{{ itemName = "{n}", clientId = {c}, buy = {b}, sell = {s} }},' for n, c, b, s in rows)
    p = "data-otservbr-global/npc/zathroth_trader.lua"
    src = open(p).read()
    a = src.index("npcConfig.shop = {\n") + len("npcConfig.shop = {\n")
    z = src.index("\n}\n-- On buy npc shop message")
    open(p, "w").write(src[:a] + shop + src[z:])
    print("written", file=sys.stderr)
