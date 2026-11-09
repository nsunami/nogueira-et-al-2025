#!/usr/bin/env python3
"""Build the static article page from the publisher's JATS XML.

Usage:
    python3 scripts/build.py
    python3 scripts/build.py --base-url https://example.github.io/repo

Requires Pandoc 3.x with the JATS reader.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
XML_PATH = ROOT / "source" / "article.xml"
TEMPLATE_PATH = ROOT / "scripts" / "template.html"
OUTPUT_PATH = ROOT / "index.html"

DEFAULT_BASE_URL = "https://nsunami.github.io/nogueira-et-al-2025"
REPO_URL = "https://github.com/nsunami/nogueira-et-al-2025"

JOURNAL_TITLE = "LIBER Quarterly: The Journal of the Association of European Research Libraries"
JOURNAL_URL = "https://liberquarterly.eu/"
ARTICLE_URL = "https://liberquarterly.eu/article/view/22604"
PDF_URL = "https://liberquarterly.eu/article/view/22604/25770"
XML_URL = "https://liberquarterly.eu/article/view/22604/25771"
DOI = "10.53377/lq.22604"
DOI_URL = f"https://doi.org/{DOI}"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
ISSN = "2213-056X"
PUBLISHED_ISO = "2025-06-16"
PUBLISHED_DISPLAY = "16 June 2025"

XLINK_HREF = "{http://www.w3.org/1999/xlink}href"

FIGURE_ALT = (
    "A circle divided into two halves. The left half is labelled Open Science "
    "and contains the words “Research data as a public good”; the right half is "
    "labelled Resource Based View and contains the words “Research data as a "
    "private asset”. Circular arrows connect the two halves."
)


def esc(value: str) -> str:
    return html.escape(value or "", quote=True)


def text_of(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def split_number(title: str) -> tuple[str, str]:
    """Split '2.1. Some title' into ('2.1', 'Some title')."""
    match = re.match(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$", title.strip())
    if match:
        return match.group(1), match.group(2)
    return "", title.strip()


def render_inline(element: ET.Element | None) -> str:
    """Render a JATS inline element tree as HTML."""
    if element is None:
        return ""

    parts: list[str] = [esc(element.text or "")]

    for child in element:
        tag = child.tag
        inner = render_inline(child)

        if tag == "italic":
            parts.append(f"<em>{inner}</em>")
        elif tag == "bold":
            parts.append(f"<strong>{inner}</strong>")
        elif tag == "sup":
            parts.append(f"<sup>{inner}</sup>")
        elif tag == "sub":
            parts.append(f"<sub>{inner}</sub>")
        elif tag == "break":
            parts.append("<br>")
        elif tag in {"ext-link", "uri"}:
            href = child.get(XLINK_HREF) or child.get("href") or inner
            if child.get("ext-link-type") == "doi" and not href.startswith(("http://", "https://")):
                href = f"https://doi.org/{href}"
            parts.append(
                f'<a href="{esc(href)}" target="_blank" rel="noopener">{inner}</a>'
            )
        else:
            parts.append(inner)

        parts.append(esc(child.tail or ""))

    return "".join(parts)


def load_article():
    tree = ET.parse(XML_PATH)
    root = tree.getroot()
    meta = root.find("front/article-meta")
    if meta is None:
        raise ValueError("Could not find front/article-meta in the XML")

    title = text_of(meta.find("title-group/article-title"))
    doi = text_of(meta.find("article-id[@pub-id-type='doi']")) or DOI
    abstract_paras = meta.findall("abstract/p")
    abstract_text = " ".join(text_of(p) for p in abstract_paras)
    keywords = [text_of(k) for k in meta.findall("kwd-group/kwd") if text_of(k)]

    affs = {
        aff.get("id"): text_of(aff)
        for aff in meta.findall("contrib-group/aff")
        if aff.get("id")
    }

    authors = []
    for contrib in meta.findall("contrib-group/contrib"):
        if contrib.get("contrib-type") != "author":
            continue
        name_el = contrib.find("name")
        if name_el is None:
            continue
        given = text_of(name_el.find("given-names"))
        surname = text_of(name_el.find("surname"))
        full_name = f"{given} {surname}".strip()
        orcid = text_of(contrib.find("contrib-id[@contrib-id-type='orcid']"))
        aff_rids = [
            xref.get("rid")
            for xref in contrib.findall("xref[@ref-type='aff']")
            if xref.get("rid")
        ]
        authors.append(
            {
                "given": given,
                "surname": surname,
                "name": full_name,
                "orcid": orcid,
                "affs": aff_rids,
            }
        )

    return root, meta, {
        "title": title,
        "doi": doi,
        "abstract_paras": abstract_paras,
        "abstract_text": abstract_text,
        "keywords": keywords,
        "affs": affs,
        "authors": authors,
    }


def render_authors(authors: list[dict]) -> str:
    rendered = []
    for author in authors:
        aff_sups = "".join(
            f'<sup>{esc(rid.replace("aff", ""))}</sup>' for rid in author["affs"]
        )
        orcid = ""
        if author["orcid"]:
            orcid = (
                f'<a class="orcid" href="{esc(author["orcid"])}" '
                f'aria-label="ORCID profile for {esc(author["name"])}" '
                f'target="_blank" rel="noopener">iD</a>'
            )
        rendered.append(
            f'<span class="author">{esc(author["name"])}{aff_sups}{orcid}</span>'
        )
    return ", ".join(rendered)


def render_affiliations(authors: list[dict], affs: dict[str, str]) -> str:
    seen: list[str] = []
    for author in authors:
        for rid in author["affs"]:
            if rid not in seen:
                seen.append(rid)
    return "".join(
        f'<li id="{esc(rid)}"><sup>{esc(rid.replace("aff", ""))}</sup>'
        f'{esc(affs.get(rid, ""))}</li>'
        for rid in seen
    )


def render_keywords(keywords: list[str]) -> str:
    return "".join(f"<li>{esc(keyword)}</li>" for keyword in keywords)


def render_meta_card() -> str:
    return f"""<dl>
  <div><dt>DOI</dt><dd><a href="{DOI_URL}" target="_blank" rel="noopener">{DOI}</a></dd></div>
  <div><dt>Published</dt><dd><time datetime="{PUBLISHED_ISO}">{PUBLISHED_DISPLAY}</time></dd></div>
  <div><dt>Volume</dt><dd>Vol. 35, No. 1 · pp. 1–28</dd></div>
  <div><dt>License</dt><dd><a href="{LICENSE_URL}" target="_blank" rel="noopener">CC BY 4.0</a></dd></div>
</dl>"""


def render_abstract(abstract_paras: list[ET.Element]) -> str:
    return "".join(f"<p>{render_inline(p)}</p>" for p in abstract_paras)


def render_toc(sections: list[ET.Element]) -> str:
    items: list[str] = []

    for sec in sections:
        sec_id = sec.get("id", "")
        title = text_of(sec.find("title"))
        number, label = split_number(title)
        children = sec.findall("sec")
        submenu = ""
        if children:
            submenu = (
                '<ul class="toc__list toc__list--nested">'
                + render_toc(children)
                + "</ul>"
            )
        items.append(
            f'<li><a class="toc__link" href="#{esc(sec_id)}">'
            f'<span class="toc__num">{esc(number)}</span>'
            f'<span class="toc__title">{esc(label)}</span></a>{submenu}</li>'
        )

    return "".join(items)


def render_reference(ref: ET.Element) -> str:
    ref_id = ref.get("id", "")
    citation = ref.find("mixed-citation")
    content = render_inline(citation) if citation is not None else ""
    return f'<li id="ref-{esc(ref_id)}">{content}</li>'


def run_pandoc() -> str:
    command = [
        "pandoc",
        str(XML_PATH),
        "-f",
        "jats",
        "-t",
        "html5",
        "--shift-heading-level-by=1",
        "--wrap=none",
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=True
        )
    except FileNotFoundError:
        sys.exit(
            "Pandoc is required to rebuild the page. "
            "Install it from https://pandoc.org/ and run this script again."
        )
    except subprocess.CalledProcessError as error:
        sys.stderr.write(error.stderr)
        sys.exit("Pandoc failed to convert the JATS XML.")
    return result.stdout


def add_target_blank(body: str) -> str:
    def repl(match: re.Match) -> str:
        tag = match.group(0)
        if "target=" in tag:
            return tag
        return tag[:-1] + ' target="_blank" rel="noopener">'

    return re.sub(r'<a\s[^>]*href="https?://[^"]*"[^>]*>', repl, body)


def process_body(body: str, root: ET.Element) -> str:
    # --- Figure 1 -------------------------------------------------------
    figure_pattern = re.compile(
        r'<figure id="fg001">\s*<p><img src="[^"]+" /></p>\s*'
        r"<figcaption>(.*?)</figcaption>\s*</figure>",
        re.S,
    )
    body = figure_pattern.sub(
        lambda m: (
            '<figure id="fg001" class="article-figure">\n'
            f'  <img src="assets/figure-1.svg" alt="{esc(FIGURE_ALT)}" '
            'width="760" height="560">\n'
            f'  <figcaption><span class="label">Fig. 1:</span> '
            f"{m.group(1).strip()}</figcaption>\n"
            "</figure>"
        ),
        body,
        count=1,
    )

    # --- Table 1 --------------------------------------------------------
    table_pattern = re.compile(
        r'<div id="tb001" class="table-wrap">\s*'
        r'<div class="caption">\s*<p>(.*?)</p>\s*</div>\s*'
        r"(<table>.*?</table>)\s*</div>",
        re.S,
    )

    def table_replacement(match: re.Match) -> str:
        caption = match.group(1).strip()
        table = match.group(2)
        return (
            '<figure id="tb001" class="article-table">\n'
            f'<figcaption><span class="label">Table 1:</span> {caption}</figcaption>\n'
            '<div class="table-scroll" role="region" aria-label="Table 1" tabindex="0">\n'
            f"{table}\n"
            "</div>\n"
            "</figure>"
        )

    body = table_pattern.sub(table_replacement, body, count=1)

    # --- In-text citations ---------------------------------------------
    citation_pattern = re.compile(
        r'<span class="citation" data-cites="([^"]+)">(.*?)</span>', re.S
    )

    def citation_replacement(match: re.Match) -> str:
        rids = match.group(1).split()
        text = match.group(2)
        if len(rids) == 1:
            return f'<a class="citation" href="#ref-{rids[0]}">{text}</a>'
        return match.group(0)

    body = citation_pattern.sub(citation_replacement, body)

    # --- Back matter headings ------------------------------------------
    back_headings = {
        "Acknowledgments": "acknowledgments",
        "Data Statement": "data-statement",
        "Funding Sources": "funding-sources",
        "Declaration of Interest": "declaration-of-interest",
        "Use of AI Tools": "use-of-ai-tools",
    }
    for label, anchor in back_headings.items():
        body = re.sub(
            rf'<h[23](?: id="[^"]*")?>{re.escape(label)}</h[23]>',
            f'<h2 id="{anchor}" class="backmatter-title">{label}</h2>',
            body,
        )

    # --- Remove Pandoc's empty reference block --------------------------
    body = re.sub(
        r"<h2>References</h2>\s*<div id=\"refs\" role=\"list\">\s*</div>",
        "",
        body,
    )

    # --- Pull out the end-of-document footnotes -------------------------
    footnotes = ""
    footnotes_match = re.search(
        r'<section id="footnotes".*?</section>', body, re.S
    )
    if footnotes_match:
        footnotes = footnotes_match.group(0)
        body = body[: footnotes_match.start()] + body[footnotes_match.end() :]

    # --- External links -------------------------------------------------
    body = add_target_blank(body)

    # --- Section numbers ------------------------------------------------
    heading_pattern = re.compile(r"<h([234])([^>]*)>(.*?)</h\1>", re.S)

    def heading_replacement(match: re.Match) -> str:
        level, attrs, inner = match.group(1), match.group(2), match.group(3)
        if "backmatter-title" in attrs or 'class="secnum"' in inner:
            return match.group(0)
        plain = re.sub(r"<[^>]+>", "", inner).strip()
        number, label = split_number(plain)
        if not number:
            return match.group(0)
        return (
            f"<h{level}{attrs}><span class=\"secnum\">{number}</span>"
            f'<span class="sectitle">{label}</span></h{level}>'
        )

    body = heading_pattern.sub(heading_replacement, body)

    # --- Notes and references -------------------------------------------
    reference_items = "".join(
        render_reference(ref) for ref in root.findall("back/ref-list/ref")
    )
    notes_html = ""
    if footnotes:
        notes_html = (
            '<section class="backmatter" aria-labelledby="notes">'
            '<h2 id="notes" class="backmatter-title">Notes</h2>'
            f"{footnotes}</section>"
        )
    references_html = (
        '<section class="backmatter" aria-labelledby="references">'
        '<h2 id="references" class="backmatter-title">References</h2>'
        f'<ol class="references">{reference_items}</ol>'
        "</section>"
    )

    return body + notes_html + references_html


def build_citation_meta(article: dict) -> str:
    lines = [
        f'<meta name="citation_title" content="{esc(article["title"])}">',
    ]
    for author in article["authors"]:
        lines.append(
            f'<meta name="citation_author" '
            f'content="{esc(author["surname"])}, {esc(author["given"])}">'
        )
    lines.extend(
        [
            f'<meta name="citation_publication_date" content="2025/06/16">',
            f'<meta name="citation_journal_title" content="{esc(JOURNAL_TITLE)}">',
            f'<meta name="citation_volume" content="35">',
            f'<meta name="citation_issue" content="1">',
            f'<meta name="citation_firstpage" content="1">',
            f'<meta name="citation_lastpage" content="28">',
            f'<meta name="citation_doi" content="{DOI}">',
            f'<meta name="citation_pdf_url" content="{PDF_URL}">',
            f'<meta name="citation_issn" content="{ISSN}">',
            f'<meta name="citation_language" content="en">',
            f'<meta name="citation_abstract" content="{esc(article["abstract_text"])}">',
            f'<meta name="citation_keywords" content="{esc("; ".join(article["keywords"]))}">',
        ]
    )
    return "\n  ".join(lines)


def build_json_ld(article: dict, canonical_url: str, og_image_url: str) -> str:
    authors = []
    for author in article["authors"]:
        person = {
            "@type": "Person",
            "name": author["name"],
        }
        if author["orcid"]:
            person["identifier"] = author["orcid"]
            person["sameAs"] = author["orcid"]
        affiliations = [
            {"@type": "Organization", "name": article["affs"].get(rid, "")}
            for rid in author["affs"]
            if article["affs"].get(rid)
        ]
        if affiliations:
            person["affiliation"] = affiliations
        authors.append(person)

    data = {
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "headline": article["title"],
        "name": article["title"],
        "author": authors,
        "datePublished": PUBLISHED_ISO,
        "abstract": article["abstract_text"],
        "keywords": article["keywords"],
        "inLanguage": "en",
        "license": LICENSE_URL,
        "url": DOI_URL,
        "sameAs": [DOI_URL, ARTICLE_URL],
        "isBasedOn": ARTICLE_URL,
        "mainEntityOfPage": canonical_url,
        "image": og_image_url,
        "identifier": DOI_URL,
        "pageStart": "1",
        "pageEnd": "28",
        "volumeNumber": "35",
        "issueNumber": "1",
        "isPartOf": {
            "@type": "Periodical",
            "name": JOURNAL_TITLE,
            "issn": ISSN,
            "publisher": {
                "@type": "Organization",
                "name": "LIBER, the Association of European Research Libraries",
            },
        },
        "publisher": {
            "@type": "Organization",
            "name": "LIBER, the Association of European Research Libraries",
        },
        "copyrightHolder": [{"@type": "Person", "name": a["name"]} for a in article["authors"]],
        "copyrightYear": 2025,
    }

    return (
        '<script type="application/ld+json">\n'
        + json.dumps(data, ensure_ascii=False, indent=2)
        + "\n</script>"
    )


def build_apa_citation() -> str:
    return (
        "Nogueira, T. F., Eikebrokk, T., &amp; Aksetøy, L. Ø. (2025). "
        "Research Data: A Public Good or a Private Asset? "
        f"<em>{esc(JOURNAL_TITLE)}, 35</em>(1), 1–28. "
        f'<a href="{DOI_URL}" target="_blank" rel="noopener">{DOI_URL}</a>'
    )


def build_bibtex() -> str:
    return f"""@article{{nogueira2025research,
  author  = {{Nogueira, Tadeu Fernando and Eikebrokk, Trude and Akset{{\\o}}y, Laila {{\\O}}kdal}},
  title   = {{Research Data: A Public Good or a Private Asset?}},
  journal = {{{JOURNAL_TITLE}}},
  year    = {{2025}},
  volume  = {{35}},
  number  = {{1}},
  pages   = {{1--28}},
  doi     = {{{DOI}}},
  url     = {{{DOI_URL}}},
  license = {{CC BY 4.0}}
}}"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Public base URL of the site (default: {DEFAULT_BASE_URL})",
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    canonical_url = f"{base_url}/"
    og_image_url = f"{base_url}/assets/og-image.png"

    root, meta, article = load_article()
    body_html = process_body(run_pandoc(), root)

    sections = root.findall("body/sec")
    toc_html = (
        '<ul class="toc__list">'
        '<li><a class="toc__link" href="#abstract">'
        '<span class="toc__num">&nbsp;</span><span class="toc__title">Abstract</span></a></li>'
        + render_toc(sections)
        + '<li><a class="toc__link" href="#acknowledgments">'
        '<span class="toc__num">&nbsp;</span><span class="toc__title">Acknowledgments</span></a></li>'
        '<li><a class="toc__link" href="#data-statement">'
        '<span class="toc__num">&nbsp;</span><span class="toc__title">Data Statement</span></a></li>'
        '<li><a class="toc__link" href="#funding-sources">'
        '<span class="toc__num">&nbsp;</span><span class="toc__title">Funding Sources</span></a></li>'
        '<li><a class="toc__link" href="#declaration-of-interest">'
        '<span class="toc__num">&nbsp;</span><span class="toc__title">Declaration of Interest</span></a></li>'
        '<li><a class="toc__link" href="#use-of-ai-tools">'
        '<span class="toc__num">&nbsp;</span><span class="toc__title">Use of AI Tools</span></a></li>'
        '<li><a class="toc__link" href="#notes">'
        '<span class="toc__num">&nbsp;</span><span class="toc__title">Notes</span></a></li>'
        '<li><a class="toc__link" href="#references">'
        '<span class="toc__num">&nbsp;</span><span class="toc__title">References</span></a></li>'
        "</ul>"
    )

    replacements = {
        "{{PAGE_TITLE}}": f"{article['title']} — LIBER Quarterly",
        "{{TITLE}}": esc(article["title"]),
        "{{META_DESCRIPTION}}": esc(
            "This article examines how Research Performing Organizations can "
            "balance the market and non-market values of the research data they hold."
        ),
        "{{CANONICAL_URL}}": esc(canonical_url),
        "{{OG_IMAGE_URL}}": esc(og_image_url),
        "{{CITATION_META}}": build_citation_meta(article),
        "{{JSON_LD}}": build_json_ld(article, canonical_url, og_image_url),
        "{{AUTHORS_HTML}}": render_authors(article["authors"]),
        "{{AFFILIATIONS_HTML}}": render_affiliations(article["authors"], article["affs"]),
        "{{KEYWORDS_HTML}}": render_keywords(article["keywords"]),
        "{{META_CARD_HTML}}": render_meta_card(),
        "{{ABSTRACT_HTML}}": render_abstract(article["abstract_paras"]),
        "{{TOC_HTML}}": toc_html,
        "{{ARTICLE_BODY}}": body_html,
        "{{APA_CITATION}}": build_apa_citation(),
        "{{BIBTEX_CITATION}}": esc(build_bibtex()),
        "{{ARTICLE_URL}}": ARTICLE_URL,
        "{{PDF_URL}}": PDF_URL,
        "{{XML_URL}}": XML_URL,
        "{{DOI_URL}}": DOI_URL,
        "{{JOURNAL_URL}}": JOURNAL_URL,
        "{{REPO_URL}}": REPO_URL,
    }

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    for key, value in replacements.items():
        template = template.replace(key, value)

    leftover = re.findall(r"\{\{[A-Z_]+\}\}", template)
    if leftover:
        sys.exit(f"Unreplaced template placeholders: {', '.join(sorted(set(leftover)))}")

    OUTPUT_PATH.write_text(template, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)}")
    print(f"  {len(article['authors'])} authors, {len(article['keywords'])} keywords")
    print(f"  {len(root.findall('back/ref-list/ref'))} references")
    print(f"  canonical URL: {canonical_url}")


if __name__ == "__main__":
    main()
