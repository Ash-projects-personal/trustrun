"""Fetch the 30 Skepthical papers from arXiv by ID.

The benchmark repository redistributes the error manifests (data/,
CC-BY-4.0) but NOT the papers themselves; each paper stays under its
authors' arXiv licence. This script downloads the arXiv source
tarball for every paper in a local corpus checkout into papers/
under the given output directory, verifies each download is a gzip
file (magic bytes), and writes papers/manifest.json with sizes and
sha256 hashes. It never extracts anything: extraction is a separate
local step for whoever runs the full-paper tasks.

Usage:
    python3 evals/skepthical/fetch_papers.py --corpus <checkout>
        --out evals/skepthical/papers [--papers 2604.20080,...]
        [--dry-run]

--dry-run prints the URLs without downloading. Without it, one
tarball per paper is downloaded (about 1-5 MB each for these papers;
30 papers total). The arXiv source URL form used here is
https://arxiv.org/src/<arxiv_id>; it was verified with a 2-byte
range request on 2026-11-19 (HTTP 206, Content-Type
application/gzip, gzip magic bytes, 4,881,248 bytes for
2604.20080). If arXiv changes the endpoint, the script fails
loudly with the manual step named instead of writing a bad file.
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.request

GZIP_MAGIC = b"\x1f\x8b"
USER_AGENT = "trustrun-fetch/0.1 (research eval; contact: trustrun)"


def paper_ids(corpus_dir):
    """arXiv IDs in a corpus checkout, from its data/ directories."""
    data_dir = os.path.join(corpus_dir, "data")
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(
            "corpus at %r has no data/ directory" % corpus_dir
        )
    ids = [
        name
        for name in sorted(os.listdir(data_dir))
        if os.path.isdir(os.path.join(data_dir, name))
    ]
    if not ids:
        raise ValueError("corpus at %r holds no papers" % corpus_dir)
    return ids


def source_url(paper_id):
    return "https://arxiv.org/src/%s" % paper_id


def fetch_one(paper_id, out_dir):
    """Download one source tarball; verify gzip magic; return a record."""
    url = source_url(paper_id)
    path = os.path.join(out_dir, "%s.tar.gz" % paper_id)
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT}
    )
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(request, timeout=120) as response:
        if response.status != 200:
            raise ValueError(
                "%s returned HTTP %d" % (url, response.status)
            )
        with open(path, "wb") as handle:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                if size == 0 and not chunk.startswith(GZIP_MAGIC):
                    raise ValueError(
                        "%s did not return a gzip file "
                        "(first bytes %r); arXiv may have moved the "
                        "source endpoint -- fetch the paper manually "
                        "from %s"
                        % (url, chunk[:16], url)
                    )
                digest.update(chunk)
                handle.write(chunk)
                size += len(chunk)
    if size == 0:
        raise ValueError("%s returned an empty file" % url)
    return {
        "paper_id": paper_id,
        "url": url,
        "path": os.path.basename(path),
        "bytes": size,
        "sha256": digest.hexdigest(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Fetch Skepthical papers from arXiv by ID."
    )
    parser.add_argument(
        "--corpus",
        required=True,
        help="local Skepthical checkout (holds data/<arxiv_id>/)",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="output directory for papers/ (created if missing)",
    )
    parser.add_argument(
        "--papers",
        default=None,
        help="comma-separated paper IDs to fetch (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the URLs without downloading",
    )
    args = parser.parse_args(argv)
    ids = paper_ids(args.corpus)
    if args.papers:
        wanted = [
            item.strip() for item in args.papers.split(",") if item.strip()
        ]
        unknown = [item for item in wanted if item not in ids]
        if unknown:
            raise ValueError(
                "unknown paper(s) in --papers: %s" % ", ".join(unknown)
            )
        ids = wanted
    if args.dry_run:
        for paper_id in ids:
            print(source_url(paper_id))
        return 0
    os.makedirs(args.out, exist_ok=True)
    records = []
    for paper_id in ids:
        record = fetch_one(paper_id, args.out)
        records.append(record)
        print(
            "fetched %s (%d bytes)" % (paper_id, record["bytes"])
        )
    manifest_path = os.path.join(args.out, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(
            {"papers": records, "paper_count": len(records)},
            handle,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")
    print("wrote %s (%d papers)" % (manifest_path, len(records)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
