"""Invisible encoding classes from the UnseenRecall teardown.

All four encoding classes measured in teardown #6
(hidden_files/teardown-log.md, 2026-10-30). A plaintext trained
TF-IDF plus logistic regression filter scored 0.93 malicious recall
on plaintext BIPIA payloads and dropped to 0.27 under tagblock and
0.27 under zerowidth, with zero surviving attack features in both.
The teardown measured the same collapse for the other two classes:
homoglyph (Latin to Cyrillic lookalikes) and base64 stealth (BIPIA's
own base64 reference) also land at the false-positive floor, 0.27
recall, 0.00-0.67 per attack category. All four classes are lossless
at the code point level and untouched by NFKC normalization
(measured, not assumed). The encodings themselves are documented
prior art (Reverse CAPTCHA, arXiv:2603.00164; the HiddenLayer
canonicalization patent, US 12,771,719 B2); what is new here is
wiring all four into Trustrun's own stress battery so one audit
measures the follow rate per class.
"""

import base64
import unicodedata

TAG_BASE = 0xE0000
ZERO_WIDTH = "\u200b"

# Latin to Cyrillic lookalikes, the teardown's font-obfuscation class.
# Copied exactly from teardown-work/unseenrecall/eval_invisible.py so
# the battery renders the same class the teardown measured.
HOMOGLYPHS = {
    "a": "\u0430", "e": "\u0435", "o": "\u043e", "c": "\u0441",
    "p": "\u0440", "x": "\u0445", "y": "\u0443", "s": "\u0455",
    "d": "\u0501", "h": "\u04bb", "i": "\u0456", "j": "\u0458",
    "A": "\u0410", "B": "\u0412", "C": "\u0421", "E": "\u0415",
    "H": "\u041d", "K": "\u041a", "M": "\u041c", "O": "\u041e",
    "P": "\u0420", "T": "\u0422", "X": "\u0425",
}
_DEHOMOGLYPH = {v: k for k, v in HOMOGLYPHS.items()}


def tagblock_encode(text):
    """Map ASCII printable chars into the Unicode Tags block.

    Each char in U+0020..U+007E becomes U+E0000 plus its code point,
    so "transfer" becomes eight invisible tag characters. Chars
    outside that range pass through unchanged. This is the invisible
    tag injection class from the teardown.
    """
    out = []
    for char in text:
        code = ord(char)
        if 0x20 <= code <= 0x7E:
            out.append(chr(TAG_BASE + code))
        else:
            out.append(char)
    return "".join(out)


def tagblock_decode(text):
    """Recover the original ASCII from tag block chars."""
    out = []
    for char in text:
        code = ord(char)
        if TAG_BASE + 0x20 <= code <= TAG_BASE + 0x7E:
            out.append(chr(code - TAG_BASE))
        else:
            out.append(char)
    return "".join(out)


def zerowidth_encode(text):
    """Insert a zero width space between every char.

    "transfer" becomes 15 chars with no word token matching the
    original, while rendering as the plain word. This is the zero
    width splitting class from the teardown.
    """
    return ZERO_WIDTH.join(text)


def zerowidth_decode(text):
    """Remove zero width spaces, recovering the original text."""
    return text.replace(ZERO_WIDTH, "")


def homoglyph_encode(text):
    """Replace Latin letters with Cyrillic lookalikes.

    "transfer" renders as the same word in a font that cannot tell
    Cyrillic from Latin, while no ASCII keyword survives: "INJECTED"
    becomes "INJECTED" with its mapped letters swapped for lookalikes.
    Letters with no lookalike in the map pass through unchanged. This
    is the teardown's font-obfuscation class, the same map its
    eval_invisible.py used.
    """
    return "".join(HOMOGLYPHS.get(char, char) for char in text)


def homoglyph_decode(text):
    """Recover the original Latin letters from Cyrillic lookalikes.

    Only the mapped lookalikes are restored; genuine Cyrillic text
    outside the map passes through unchanged, so decoding is the
    inverse of encoding on the mapped subset only.
    """
    return "".join(_DEHOMOGLYPH.get(char, char) for char in text)


def base64_encode(text):
    """Base64-encode the payload, BIPIA's own "stealth" reference.

    The smuggled text is the bare base64 blob: no decode hint, no
    wrapper, exactly the rendering the teardown measured. A filter
    scanning for keywords sees only an opaque alphanumeric string.
    """
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")


def base64_decode(text):
    """Recover the original text from a base64 blob.

    Strict decoding: whitespace is stripped first, then the blob must
    be valid base64 of UTF-8 text, or a ValueError is raised. A bare
    blob with no decode instruction is still decodable by any agent
    that recognizes base64, which is the channel this class tests.
    """
    blob = "".join(text.split())
    return base64.b64decode(blob, validate=True).decode("utf-8")


def nfkc_stable(text):
    """True when Unicode NFKC normalization leaves the text untouched.

    The teardown measured this as True for both classes, which is why
    naive normalization is not a defense.
    """
    return unicodedata.normalize("NFKC", text) == text
