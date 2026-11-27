"""Check legacy handoff pages on this host.

Every page under a handoff prefix must send people, crawlers and agents to one
exact live URL: one canonical, one zero-delay refresh and visible links, all to
the same https URL on the product host, with no query or fragment. Pages must
not carry robots rules or scripts that conflict with that canonical. Each
handoff path P is published as both P.html and P/index.html, byte-identical.
A prefix may also keep an llms.txt whose only URL is the product's llms.txt.
A page may send people on to its canonical plus one ?entry_surface=<slug>
attribution parameter. The two product roots keep one exact script that forwards the query and hash
to the same target, so old campaign links keep their attribution.
"""
import pathlib
import re
import sys

HOSTS = {
    "anymd": "anymd.sylphx.com",
    "lockdocs": "lockdocs.sylphx.com",
    "citra": "anymd.sylphx.com",
    "pdf-reader-mcp": "anymd.sylphx.com",
}
FORWARDING_ROOTS = {"anymd/index.html", "lockdocs/index.html"}
FORWARDER = "<script>window.location.replace('{}' + window.location.search + window.location.hash);</script>\n"

errors = []
for prefix, host in HOSTS.items():
    target_re = re.compile(rf"https://{re.escape(host)}/[A-Za-z0-9._~/-]*")
    for page in sorted(pathlib.Path(prefix).rglob("*")):
        rel = page.as_posix()
        if page.is_dir():
            continue
        if rel == f"{prefix}/llms.txt":
            urls = re.findall(r"https?://[^\s)>\]]+", page.read_text(encoding="utf-8"))
            if not urls or set(urls) != {f"https://{host}/llms.txt"}:
                errors.append(f"{rel}: must point only to https://{host}/llms.txt")
            continue
        if page.suffix != ".html":
            errors.append(f"{rel}: only .html handoff pages belong here")
            continue
        html = page.read_text(encoding="utf-8")
        canonical = re.findall(r'<link rel="canonical" href="([^"]*)">', html)
        refresh = re.findall(r'<meta http-equiv="refresh" content="0;url=([^"]*)">', html)
        hrefs = re.findall(r'href="([^"]*)"', html)
        if len(canonical) != 1 or html.count('rel="canonical"') != 1:
            errors.append(f"{rel}: needs exactly one canonical")
            continue
        target = canonical[0]
        if rel in FORWARDING_ROOTS:
            if html.count(FORWARDER.format(target)) != 1:
                errors.append(f"{rel}: needs exactly one query and hash forwarder to {target}")
            html = html.replace(FORWARDER.format(target), "", 1)
        if not target_re.fullmatch(target):
            errors.append(f"{rel}: target {target} is not a plain https://{host}/ URL")
        dest = refresh[0] if len(refresh) == 1 else target
        if len(refresh) != 1 or html.lower().count("http-equiv") != 1:
            errors.append(f"{rel}: needs exactly one zero-delay refresh to {target}")
        elif dest != target and not re.fullmatch(re.escape(target) + r"\?entry_surface=[a-z][a-z0-9_]*", dest):
            errors.append(f"{rel}: refresh may add only ?entry_surface=<slug> to {target}")
        links = re.findall(r'<a href="([^"]*)">', html)
        if not links or set(links) != {dest} or len(hrefs) != len(links) + 1:
            errors.append(f"{rel}: every link must point to {dest}")
        if re.search(r"<script|name=\"(robots|googlebot)\"|noindex", html, re.I):
            errors.append(f"{rel}: robots rules or scripts conflict with the canonical")
        if rel == f"{prefix}/index.html":
            continue
        twin = pathlib.Path(rel[: -len("/index.html")] + ".html" if rel.endswith("/index.html") else rel[: -len(".html")] + "/index.html")
        if not twin.is_file() or twin.read_bytes() != page.read_bytes():
            errors.append(f"{rel}: {twin} must exist with identical content")

print("\n".join(errors) or "handoff pages OK")
sys.exit(1 if errors else 0)
