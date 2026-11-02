"""Invisible encoding classes from the UnseenRecall teardown.

Two of the four encoding classes measured in teardown #6
(hidden_files/teardown-log.md, 2026-10-30). A plaintext trained
TF-IDF plus logistic regression filter scored 0.93 malicious recall
on plaintext BIPIA payloads and dropped to 0.27 under tagblock and
0.27 under zerowidth, with zero surviving attack features in both.
Both encodings are lossless at the code point level and untouched
by NFKC normalization (measured, not assumed). The teardown's other
two classes, homoglyph and base64 stealth, are documented there and
are not implemented here.
"""

import unicodedata

TAG_BASE = 0xE0000
ZERO_WIDTH = "\u200b"


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


def nfkc_stable(text):
    """True when Unicode NFKC normalization leaves the text untouched.

    The teardown measured this as True for both classes, which is why
    naive normalization is not a defense.
    """
    return unicodedata.normalize("NFKC", text) == text
