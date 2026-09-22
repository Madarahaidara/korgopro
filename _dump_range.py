# -*- coding: utf-8 -*-
"""Outil temporaire : dump d'une plage de lignes numérotées vers un fichier.

Usage: python _dump_range.py <src> <start> <end> <out>   (1-based, inclusif)
"""
import sys


def main():
    src, start, end, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    with open(src, encoding='utf-8') as fh:
        lines = fh.readlines()
    chunk = lines[start - 1:end]
    with open(out, 'w', encoding='utf-8') as fh:
        for i, line in enumerate(chunk, start=start):
            fh.write(f"{i}| {line.rstrip(chr(10) + chr(13))}\n")
    print(f"{out}: {len(chunk)} lignes")


if __name__ == '__main__':
    main()