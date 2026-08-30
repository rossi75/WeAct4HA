"""
Reine Python-Implementierung eines FastLZ-Level-1-Compressors.

Erzeugt Bytestreams im offiziellen FastLZ-Blockformat (Level 1), wie es
unter https://ariya.github.io/FastLZ/ beschrieben ist. Damit kompatibel zu
jedem standardkonformen FastLZ-Dekompressor - also auch zu der Firmware,
die auf dem Display via CMD_SET_BITMAP_FASTLZ die Daten entpackt.

Es wird ausschließlich komprimiert (Level 1: 8-KB-Fenster, Matches bis
264 Byte). Für 320x480-RGB565-Frames (~300 KB) bedeutet das 8-KB-Fenster,
dass nur Wiederholungen innerhalb der letzten 8 KB gefunden werden - für
Displayinhalte mit vielen lokal wiederkehrenden Farbwerten/Flächen reicht
das in der Regel für eine brauchbare Kompression.

Enthält zusätzlich einen minimalen Referenz-Decompressor NUR für
Selbsttests (Round-Trip-Prüfung), nicht für den produktiven Einsatz -
entpackt wird ja auf dem Display selbst.
"""

from __future__ import annotations

MAX_DISTANCE = 8192      # 13-Bit-Fenster (Level-1-Format)
MAX_SHORT_LEN = 8         # kurze Matches: 3..8 Byte
MAX_LONG_LEN = 264        # lange Matches: 9..264 Byte
MIN_MATCH = 3              # kürzeste erkennbare Wiederholung
MAX_LITERAL_RUN = 32       # max. Literal-Byte pro Opcode


def fastlz1_compress(data: bytes) -> bytes:
    """Komprimiert `data` in ein FastLZ-Level-1-Blockformat."""
    n = len(data)
    out = bytearray()
    if n == 0:
        return bytes(out)

    hash_table: dict[bytes, int] = {}
    literal_start = 0
    i = 0

    def emit_literals(start: int, end: int) -> None:
        pos = start
        while pos < end:
            run = min(MAX_LITERAL_RUN, end - pos)
            out.append(run - 1)  # obere 3 Bit sind implizit 0 (Literal-Tag)
            out.extend(data[pos:pos + run])
            pos += run

    def emit_match(length: int, offset: int) -> None:
        # offset = R (0..8191 = MAX_DISTANCE-1), length = 3..264
        if length <= MAX_SHORT_LEN:
            m = length - 2  # 1..6
            out.append((m << 5) | (offset >> 8))
            out.append(offset & 0xFF)
        else:
            out.append((7 << 5) | (offset >> 8))
            out.append(length - 9)  # 0..255
            out.append(offset & 0xFF)

    while i < n:
        match_len = 0
        match_off = 0

        if i + MIN_MATCH <= n:
            key = bytes(data[i:i + 3])
            cand = hash_table.get(key)
            hash_table[key] = i

            if cand is not None:
                dist = i - cand
                if dist <= MAX_DISTANCE:
                    max_len = min(MAX_LONG_LEN, n - i)
                    length = 0
                    while length < max_len and data[cand + length] == data[i + length]:
                        length += 1
                    if length >= MIN_MATCH:
                        match_len = length
                        match_off = dist - 1

        if match_len >= MIN_MATCH:
            emit_literals(literal_start, i)

            remaining = match_len
            while remaining > 0:
                chunk = min(MAX_LONG_LEN, remaining)
                # keinen 1-2-Byte-Rest hinterlassen, der kein gültiges
                # Match mehr wäre (Minimum ist 3 Byte)
                if 0 < remaining - chunk < MIN_MATCH:
                    chunk -= (MIN_MATCH - (remaining - chunk))
                emit_match(chunk, match_off)
                remaining -= chunk

            # Hash-Tabelle für ein paar Positionen innerhalb des Matches
            # nachpflegen (bessere Trefferquote danach, ohne jede einzelne
            # Position im Match einzeln zu hashen)
            for j in range(i + 1, i + match_len - MIN_MATCH, 7):
                hash_table[bytes(data[j:j + 3])] = j

            i += match_len
            literal_start = i
        else:
            i += 1

    emit_literals(literal_start, n)
    return bytes(out)


def _fastlz1_decompress(data: bytes) -> bytes:
    """NUR für Selbsttests: Referenz-Decompressor für das Level-1-Format."""
    out = bytearray()
    src = 0
    n = len(data)
    while src < n:
        opcode = data[src]
        typ = opcode >> 5
        if typ == 0:
            run = 1 + opcode
            src += 1
            out.extend(data[src:src + run])
            src += run
        elif typ < 7:
            ofs = 256 * (opcode & 31) + data[src + 1]
            length = 2 + typ
            src += 2
            ref = len(out) - ofs - 1
            for _ in range(length):
                out.append(out[ref])
                ref += 1
        else:
            ofs = 256 * (opcode & 31) + data[src + 2]
            length = 9 + data[src + 1]
            src += 3
            ref = len(out) - ofs - 1
            for _ in range(length):
                out.append(out[ref])
                ref += 1
    return bytes(out)


if __name__ == "__main__":
    import os
    import random
    import time

    random.seed(42)

    tests = [
        b"",
        b"A",
        b"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        bytes(range(256)) * 4,
        os.urandom(5000),
        (b"\x00\x00" * 240 + os.urandom(400)) * 50,  # Muster ähnlich RGB565-Flächen
    ]
    for t in tests:
        c = fastlz1_compress(t)
        d = _fastlz1_decompress(c)
        assert d == t, f"Roundtrip fehlgeschlagen (len={len(t)})"
        ratio = (len(c) / len(t) * 100) if t else 0
        print(f"len={len(t):>7}  compressed={len(c):>7}  ratio={ratio:5.1f}%")

    # Realistischere Größenordnung: großes Display, 320x480 RGB565
    big = (b"\x1f\x00" * 30000 + os.urandom(4000) + b"\x00\xf8" * 20000) * 2
    big = big[:320 * 480 * 2]
    start = time.time()
    c = fastlz1_compress(big)
    elapsed = time.time() - start
    d = _fastlz1_decompress(c)
    assert d == big
    print(f"\n320x480-Frame: {len(big)} -> {len(c)} Byte "
          f"({len(c)/len(big)*100:.1f}%) in {elapsed:.2f}s")
