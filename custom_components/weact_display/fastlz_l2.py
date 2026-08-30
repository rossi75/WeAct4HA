# FastLZ-Level-2-Format-Logik portiert nach dem MIT-lizenzierten Referenz-
# Code von ariya/FastLZ (https://github.com/ariya/FastLZ), Copyright (C)
# Ariya Hidayat.
#
# FastLZ Level 2 (byte-aligned LZ77) - reine Python-Implementierung, plus das
# "4K-FastLZ"-Wire-Format des Displays.

# Reverse-engineered und an zwei echten USB-Captures verifiziert (Schwarz- und
# Rot-Fuellung, siehe Analyse) - beide decodieren byte-exakt auf die erwarteten,
# gleichfoermigen RGB565-Werte:

#  Wire-Format pro Chunk:
#    [unkomprimierte Laenge u16 LE][komprimierte Laenge u16 LE][FastLZ-Level-2-Daten]

# Die FastLZ-Level-2-Bytestream-Logik selbst folgt 1:1 dem offiziellen
# Referenz-Quellcode: https://github.com/ariya/FastLZ/blob/master/fastlz.c
# (MIT-Lizenz, Ariya Hidayat) - hier als eigenstaendige Python-Portierung ohne
# Abhaengigkeiten.

from __future__ import annotations

MAX_COPY = 32
MAX_L2_DISTANCE = 8191
MAX_FARDISTANCE = 65535 + MAX_L2_DISTANCE - 1  # 73725
MIN_MATCH = 3


# ---------------------------------------------------------------------------
# Kompression
# ---------------------------------------------------------------------------

def _emit_literals(data: bytes, start: int, end: int, out: bytearray) -> None:
    pos = start
    while end - pos >= MAX_COPY:
        out.append(MAX_COPY - 1)
        out.extend(data[pos:pos + MAX_COPY])
        pos += MAX_COPY
    if end > pos:
        run = end - pos
        out.append(run - 1)
        out.extend(data[pos:end])


def _emit_match(total_length: int, distance: int, out: bytearray) -> None:
    # total_length = tatsaechliche Kopierlaenge (>=3). Kurze Matches (3..8)
    # kodieren m = total_length-2 direkt in die oberen 3 Bit (wie Level 1);
    # ab 9 Byte wird ueber beliebig viele 0xFF-Fortsetzungsbytes verlaengert.
    d = distance - 1
    far = d >= MAX_L2_DISTANCE
    if far:
        d -= MAX_L2_DISTANCE

    if total_length < 9:
        m = total_length - 2  # 1..6
        out.append((m << 5) | (31 if far else (d >> 8)))
    else:
        out.append((7 << 5) | (31 if far else (d >> 8)))
        rem = total_length - 9
        while rem >= 255:
            out.append(255)
            rem -= 255
        out.append(rem)

    if far:
        out.append(255)
        out.append(d >> 8)
        out.append(d & 0xFF)
    else:
        out.append(d & 0xFF)


# ---------------------------------------------------------------------------
# Komprimiert `data` in echtes FastLZ-Level-2-Format (ohne Wire-Header)
# ---------------------------------------------------------------------------
def fastlz2_compress(data: bytes) -> bytes:
    n = len(data)
    out = bytearray()
    if n == 0:
        return bytes(out)

    hash_table: dict[bytes, int] = {}
    literal_start = 0
    i = 0

    while i < n:
        match_len = 0
        match_dist = 0

        if i + MIN_MATCH <= n:
            key = bytes(data[i:i + 3])
            cand = hash_table.get(key)
            hash_table[key] = i

            if cand is not None:
                dist = i - cand
                if dist <= MAX_FARDISTANCE:
                    # bei sehr weiten Distanzen (>= MAX_L2_DISTANCE) verlangt
                    # das Format mindestens 5 uebereinstimmende Bytes
                    min_needed = MIN_MATCH if dist < MAX_L2_DISTANCE else 5
                    max_len = n - i
                    length = 0
                    while length < max_len and data[cand + length] == data[i + length]:
                        length += 1
                    if length >= min_needed:
                        match_len = length
                        match_dist = dist

        if match_len >= MIN_MATCH:
            _emit_literals(data, literal_start, i, out)
            _emit_match(match_len, match_dist, out)

            # Hash-Tabelle innerhalb des Matches nachpflegen (sparsam, fuer
            # bessere Trefferquote danach, ohne jede Position einzeln zu hashen)
            for j in range(i + 1, i + match_len - MIN_MATCH, 7):
                hash_table[bytes(data[j:j + 3])] = j

            i += match_len
            literal_start = i
        else:
            i += 1

    _emit_literals(data, literal_start, n, out)

    # FastLZ-Level-2-Marker: oberste 3 Bit des allerersten Bytes auf 001 setzen
    if out:
        out[0] |= (1 << 5)

    return bytes(out)


# ---------------------------------------------------------------------------
# Dekompression (nur fuer Selbsttests - entpackt wird ja auf dem Display)
# ---------------------------------------------------------------------------

def fastlz2_decompress(data: bytes) -> bytes:
    ip = 0
    n = len(data)
    op = bytearray()

    ctrl = data[ip] & 31
    ip += 1

    while True:
        if ctrl >= 32:
            length = (ctrl >> 5) - 1
            ofs = (ctrl & 31) << 8
            ref = len(op) - ofs - 1

            if length == 7 - 1:
                while True:
                    code = data[ip]
                    ip += 1
                    length += code
                    if code != 255:
                        break

            code = data[ip]
            ip += 1
            ref -= code
            length += 3

            if code == 255 and ofs == (31 << 8):
                ofs = data[ip] << 8
                ip += 1
                ofs += data[ip]
                ip += 1
                ref = len(op) - ofs - MAX_L2_DISTANCE - 1

            if ref < 0:
                raise ValueError(f"ungueltige Rueckreferenz ref={ref}")
            for k in range(length):
                op.append(op[ref + k])
        else:
            ctrl += 1
            op.extend(data[ip:ip + ctrl])
            ip += ctrl

        if ip >= n:
            break
        ctrl = data[ip]
        ip += 1

    return bytes(op)


# ---------------------------------------------------------------------------
# Display-Wire-Format
# ---------------------------------------------------------------------------
# Baut EINEN sendefertigen FastLZ-Chunk im Wire-Format des Displays:
# [unkomprimierte Laenge u16 LE][komprimierte Laenge u16 LE][FastLZ-Level-2-Daten]
# ---------------------------------------------------------------------------
def build_display_chunk(rgb565_data: bytes) -> bytes:

    compressed = fastlz2_compress(rgb565_data)
    header = bytes([
        len(rgb565_data) & 0xFF, (len(rgb565_data) >> 8) & 0xFF,
        len(compressed) & 0xFF, (len(compressed) >> 8) & 0xFF,
    ])
    return header + compressed

# ---------------------------------------------------------------------------
# Wie build_display_payload(), aber gibt eine LISTE einzelner, vollstaendiger
# Chunks zurueck (statt einem verketteten Blob). WICHTIG: Jeder Eintrag
# sollte als EIGENER Serial.write()-Aufruf gesendet werden - nicht nach
# einer festen Bytegroesse neu zusammengeschnitten! Sonst koennen Header
# oder Opcodes mitten durchgeschnitten werden, was die Firmware zum
# Absturz bringen kann (genau das reale Symptom, das zum Auffinden dieses
# Hinweises gefuehrt hat).
# ---------------------------------------------------------------------------
def build_display_chunks(rgb565_data: bytes, max_chunk_size: int = 2560) -> list[bytes]:
    chunks = []
    for start in range(0, len(rgb565_data), max_chunk_size):
        chunk_data = rgb565_data[start:start + max_chunk_size]
        chunks.append(build_display_chunk(chunk_data))
    return chunks
 

# ---------------------------------------------------------------------------
# Teilt `rgb565_data` bei Bedarf in mehrere Chunks (Default 2560 Byte
# unkomprimiert pro Chunk, wie im WeAct-Referenztreiber) und haengt daraus
# den kompletten Bytestream fuer CMD_SET_BITMAP_FASTLZ zusammen.
# ---------------------------------------------------------------------------
def build_display_payload(rgb565_data: bytes, max_chunk_size: int = 2560) -> bytes:
    out = bytearray()
    for start in range(0, len(rgb565_data), max_chunk_size):
        chunk = rgb565_data[start:start + max_chunk_size]
        out.extend(build_display_chunk(chunk))
    return bytes(out)


if __name__ == "__main__":
    import os
    import time

    random_gen = os.urandom

    # 1) Verifikation gegen die ECHTEN Captures (Schwarz und Rot)
    print("=== Verifikation gegen echte USB-Captures ===")
    captures = {
        "schwarz (Init 80x160 komplett)":
            (bytes.fromhex("40010f00010000e0fd01e02a01040000000000"), 320, bytes(320)),
        "rot (40x Wiederholung, 4 Zeilen)":
            (bytes.fromhex("8002120001e4e8e0fd01e0fd01e0640104e8e4e8e4e8"), 640,
             (b"\xe4\xe8") * 320),
    }
    for name, (raw, expected_len, expected_out) in captures.items():
        uncompressed_len = raw[0] | (raw[1] << 8)
        compressed_len = raw[2] | (raw[3] << 8)
        body = raw[4:4 + compressed_len]
        out = fastlz2_decompress(body)
        ok = (len(out) == expected_len == uncompressed_len) and out == expected_out
        print(f"{name}: decodiert={len(out)} Byte, erwartet={expected_len}  {'OK' if ok else 'FEHLER'}")

    # 2) Roundtrip-Selbsttest fuer den eigenen Compressor
    print("\n=== Roundtrip-Selbsttest (eigener Compressor + eigener Decoder) ===")
    tests = [
        b"",
        b"A",
        b"\x00" * 320,                       # wie "schwarz"
        (b"\xe4\xe8") * 320,                 # wie "rot"
        bytes(range(256)) * 4,
        random_gen(5000),
        (b"\x00\x00" * 2000 + random_gen(400)) * 10,
    ]
    for t in tests:
        c = fastlz2_compress(t)
        d = fastlz2_decompress(c) if c else b""
        assert d == t, f"Roundtrip fehlgeschlagen (len={len(t)})"
        ratio = (len(c) / len(t) * 100) if t else 0
        print(f"len={len(t):>7}  compressed={len(c):>7}  ratio={ratio:5.1f}%")

    # 3) Realistische Framegroesse: grosses Display 320x480 RGB565
    big = (b"\x1f\x00" * 30000 + random_gen(4000) + b"\x00\xf8" * 20000) * 2
    big = big[:320 * 480 * 2]
    start = time.time()
    payload = build_display_payload(big)
    elapsed = time.time() - start
    print(f"\n320x480-Frame: {len(big)} Byte RGB565 -> {len(payload)} Byte Wire-Payload "
          f"({len(payload)/len(big)*100:.1f}%) in {elapsed:.2f}s")
