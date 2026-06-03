# 11 · B0 payload codec and decoded fields

What the chlorinator actually says to the cloud, byte by byte. This
chapter documents the codec we reverse-engineered empirically from a
1000+ sample corpus and the field-by-field semantics we have pinned
down so far.

## The codec

### Digit alphabet (confirmed)

Each character of a numeric field encodes one base-10 digit, but the
alphabet is **custom** — not the usual `0..9`:

| Digit | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| Char | `a` | `b` | `c` | `d` | `e` | `f` | `U` | `V` | `W` | `X` |

So `bVWaedfcbc` decodes to `1780435212`, which is the Unix epoch for
2026-06-02T23:20:12 UTC — and that matches the wall-clock time the
sample was captured at, to the second.

### Decimal point

The character `g` between two digit groups is the **decimal point**.
A trailing fractional part is padded to its on-wire width:

| Raw value | Decoded |
|---|---|
| `aVgef` | `07.45` → 7.45 |
| `abgVM` | `01.7` + marker `M` → 1.7 g/L |
| `acXgaI` | `029.0` + marker `I` → 29.0 °C |

### Unit markers

Trailing **uppercase letters that are not in the digit set** are unit
markers — they signal what physical quantity the field represents:

| Marker | Field | Quantity | Sample |
|---|---|---|---|
| (none) | `SG` | pH | `aVgef` → 7.45 |
| `M` | `IT` | salinity (g/L) | `abgfM` → 1.5 g/L |
| `I` | `CY` | temperature (°C) | `acUgcI` → 26.2 °C |

### Categorical values

A handful of fields use **single uppercase letters as categories**
(not digits). They appear without `g` and without trailing markers:

| Field | Values seen | Likely role |
|---|---|---|
| `9D` | `a`, `N` | binary state with named value |
| `9G` | `a`, `O` | binary state with named value |
| `YD` | `a`, `N`, `R` | tri-valued status |

The semantic labels for `N`, `R` and `O` are not yet known.

## Field census

### Read.php payload

A `read.php` is a *heartbeat poll* from the device asking the cloud
for pending commands. It only ships identity and timekeeping:

| Field | Type | Decoded role |
|---|---|---|
| (prefix) `JS4fUX2d24UWcVbXJYfYfd` | constant | device identity token |
| `TD` | 13-digit base10 | device serial number |
| `CI` | constant `a` | channel index = 0 |
| `LI` | 5-digit base10 | per-request session counter |
| `CD` | 10-digit base10 | Unix timestamp of the request (UTC) |

### Write.php payload

A `write.php` is a *telemetry push*. The base set is the same as
read.php, plus a variable subset of telemetry/state fields. The subset
varies write-to-write — not every write carries every field.

#### Measurements (confirmed)

| Field | Quantity | Unit | Format | Example |
|---|---|---|---|---|
| `SG` | water pH | pH | `dd g dd` | `aVgef` → 7.45 |
| `IT` | salinity | g/L | `dd g dd M` | `abgfM` → 1.5 g/L |
| `CY` | water temperature | °C | `ddd g d I` | `acXgcI` → 29.2 °C |
| `GY` | chlorine production | % | `ddd` | `aXX` → 99 % |

These are the four values that flow through to Home Assistant via the
`measurements` block of `/api/idegis/state`.

#### Boolean flags

All single-character base-10 (`a` = false, `b` = true):

| Field | Notes |
|---|---|
| `9C` | unknown |
| `Jb` | unknown |
| `SI` | unknown |
| `YI` | unknown |
| `Y9` | unknown |
| `DL` | unknown |
| `RB` | unknown |

#### Counters (likely)

| Field | Range observed | Notes |
|---|---|---|
| `AJ` | 0..90 | slow counter |
| `MK` | 0..47 | rolls over (~48 ticks per cycle, period not pinned) |
| `OI` | 0..119 | slow counter |
| `OB` | ~3500 | almost-constant counter or embedded timestamp |
| `TB` | ~3500 | parallel to OB |
| `NB` | one sample | counter |
| `ND` | one sample | counter |

#### Cloud response

The cloud replies with a payload of the **same form** as the request:
plain ASCII `00#B0=<payload>&H=<hash>`. The `B0` decomposes with the
exact same codec, so the cloud round-trips device identity (`TD`,
`CI`, `LI`) and stamps its own `CD` (a few seconds later than the
request `CD` — that's the cloud-side delay). Other fields the cloud
may add (commands, setpoints) are not yet observed in our corpus.

## What is still missing

- `ORP` (redox in mV) doesn't appear in B0. The Neolysis SKU on the
  reference installation does not have the ORP probe slot populated,
  so the field is probably gated by `ID_Technologies_implemented` bit
  `cl-orp`. Equipments with the ORP probe should expose it; we will
  know when someone else captures with that config.
- Hash `H` formula. We can read and decode but we cannot **forge**
  requests to the cloud — the hash uses an unknown shared secret.
  Without it we cannot inject setpoints via the cloud channel.
- Several categorical values (`N`, `R`, `O`) have not been mapped to
  semantics yet. They are probably alarm or mode codes.

## Validation summary

| What | How verified |
|---|---|
| Alphabet | `CD` decoded as Unix seconds matches wall clock to ~1 s |
| Decimal point `g` | `SG` decodes to 5.72..7.51, exact pool pH band |
| Marker `M` for g/L | `IT` decodes to 0.0..3.8, matches Neolysis low-salinity range |
| Marker `I` for °C | `CY` decodes to 24.6..34.2, shows day/night curve |
| `LI` is a counter | strictly monotonic, increments by 1 per request |
| `TD` is a serial | constant across all 1000+ requests of the same device |
