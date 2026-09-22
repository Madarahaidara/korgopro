"""Verification des bornes de patch (lecture seule)."""
import io
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(ROOT, "ui", "views", "admin_view.py")
with io.open(TARGET, encoding="utf-8") as handle:
    lines = handle.read().split("\n")

print("total lignes:", len(lines))
for start, end in [(1663, 1665), (1722, 1728), (1774, 1780), (1819, 1826),
                   (1875, 1882), (1921, 1926), (1966, 1972), (1977, 1982),
                   (2040, 2046), (2164, 2172)]:
    print(f"--- {start}-{end} ---")
    for n in range(start, end + 1):
        print(f"{n:5d}| {lines[n - 1]}")