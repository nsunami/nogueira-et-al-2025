# Research Data: A Public Good or a Private Asset?

A static, open-access HTML edition of the article by **Tadeu Fernando Nogueira**, **Trude Eikebrokk**, and **Laila Økdal Aksetøy**, originally published in *LIBER Quarterly: The Journal of the Association of European Research Libraries*, Vol. 35, No. 1 (2025), pp. 1–28.

**Live site:** <https://nsunami.github.io/nogueira-et-al-2025/>

## Source

- Original article: <https://liberquarterly.eu/article/view/22604>
- DOI: <https://doi.org/10.53377/lq.22604>
- Publisher PDF: <https://liberquarterly.eu/article/view/22604/25770>
- JATS XML: <https://liberquarterly.eu/article/view/22604/25771>

The page is generated from the publisher's JATS XML, archived in [`source/article.xml`](source/article.xml).

## License

Copyright (c) 2025 Tadeu Fernando Nogueira, Trude Eikebrokk, Laila Økdal Aksetøy.

This work is licensed under a [Creative Commons Attribution 4.0 International License](https://creativecommons.org/licenses/by/4.0/).

**Changes from the original:** this HTML edition reproduces the article text from the publisher's JATS XML. Figure 1 has been redrawn as an SVG; navigation, formatting, hyperlinks, and citation metadata have been added. The article text itself is unchanged.

The site code (`scripts/build.py`, `scripts/template.html`, and `assets/styles.css`) is released under the MIT License; see [`LICENSE-CODE`](LICENSE-CODE). The article text, figure, and journal logo remain subject to the CC BY 4.0 terms above.

## Files

```
index.html                     generated article page
assets/
  styles.css                   editorial layout, light/dark, print
  figure-1.svg                 redrawn Figure 1
  liber-quarterly-logo.png     journal logo (light theme)
  liber-quarterly-logo-light.png
  og-image.png                 social preview card
  favicon.svg
source/
  article.xml                  publisher JATS XML
scripts/
  build.py                     JATS XML -> index.html
  template.html                page shell
```

## Rebuild

Requires Python 3.9+ and [Pandoc 3.x](https://pandoc.org/) with the JATS reader.

```sh
python3 scripts/build.py
```

To use a different public URL for the canonical link and social preview:

```sh
python3 scripts/build.py --base-url https://example.github.io/repository-name
```

The generated `index.html` is committed, so GitHub Pages does not need a build step.

## Publish with GitHub Pages

1. Create a public repository and push this directory to `main`.
2. In **Settings → Pages**, choose **Deploy from a branch**, then `main` and `/ (root)`.
3. The site will be available at `https://<user>.github.io/<repository>/`.

Or, with the GitHub CLI:

```sh
git init
git add .
git commit -m "Add HTML edition of Nogueira et al. (2025)"
gh repo create <user>/<repository> --public --source=. --remote=origin --push
gh api --method POST "repos/<user>/<repository>/pages" \
  -f 'source[branch]=main' -f 'source[path]=/'
```

## Notes

- The article text was compared word-for-word against the JATS XML (9,688 words in both).
- In-text citations link to the reference list; footnotes link to the notes.
- Author names follow the JATS metadata: surname **Aksetøy**, given names **Laila Økdal**. The publisher's suggested citation uses the variant "Økdal Aksetøy, L."; this edition uses "Aksetøy, L. Ø."
- The journal logo is used solely to identify the original publication.
