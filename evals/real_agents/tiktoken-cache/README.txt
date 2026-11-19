Vendored tiktoken encoding cache (TRUSTRUN-TiktokenPrecache).

The file 9b5ad71b2ce5302211f9c61530b329a4922fc6a4 is the cl100k_base
BPE ranks file downloaded from
https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken
(1,681,126 bytes, 100,256 lines; sha256
223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7).

tiktoken names its cache entries by sha1 of the download URL, not
by encoding name: sha1("https://openaipublic.blob.core.windows.net/
encodings/cl100k_base.tiktoken") = 9b5ad71b...fc6a4. That is why
the file has this name; do not rename it.

The AgentGPT platform backend counts tokens with tiktoken and
downloads this file on first use. An intermittent TLS failure on
that download turned the suite red 9 times (Nov 13-15, 2026).
The adapter points TIKTOKEN_CACHE_DIR here when it spawns the
driver, so no download happens at session time. If this file is
ever deleted, tiktoken downloads it into this directory once and
reuses it afterwards; re-fetch from the URL above to restore it.
