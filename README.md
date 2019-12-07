# img-lurker

img-lurker is a gallery downloader.

img-lurker takes a URL of a (HTML) web page and downloads linked images on it.
If the page contains only thumbnails, linking to a the full size version of
the image, img-lurker will rather take the bigger one.
If there are links to other HTML pages (themselves containing a the full size
image), img-lurker will follow those links to find the bigger size.

img-lurker has a "minimum image size" for considering an image is worthy of being downloaded and
isn't UI stuff like buttons/separators. img-lurker will not follow links if the link tag doesn't
contain an image tag (assumed to be the thumbnail).

## Example

Consider a site with following HTML:

    <a href="fullimage1.jpg">
        <img src="thumbnail1.jpg" />
    </a>
    <a href="fullimage2.jpg">
        <img src="thumbnail2.jpg" />
    </a>

img-lurker would download "fullimage1.jpg" and "fullimage2.jpg".
If instead the links point to other HTML pages containing the full size version
of the images (for example "fullimage1.html" containing "fullimage1.jpg"),
img-lurker would still find fullimage1.jpg by following the page links.

## Options

    --cookie KEY=VALUE

Inject a specific cookie, which might be required to visit some restricted
access pages. For example, some subreddits require you to pass the cookie "over18=1".

The option can be passed several times to inject multiple cookies.

    --next-page-xpath HTML_XPATH

img-lurker can handle pagination for sites where a gallery contains so many
images that the site is split in numbered pages.
`HTML_XPATH` should be an XPath expression locating the HTML link to the "next
page".
If this argument is given, after downloading all images of a "page", img-lurker
will follow the link pointed to by `HTML_XPATH` and repeat on the next page.

Warning: this can issue a lot of traffic for huge galleries. Be cautious or you
might get blocked by the website.

    --history-file FILE

Mark all downloaded images URLs in this file and avoid redownloading URLs
present in this file.
Useful when running img-lurker multiple times on the same gallery, typically if
the gallery has received fresh images. Also useful if you use
`--next-page-xpath` option and kill img-lurker to avoid flooding the site, make
a pause (minutes? hours? days?) then restart img-lurker: the history file will
help it resume where it was interrupted.

This makes the assumption that each image has a URL that is unique (the image
URL always have the same URL, e.g. no varying tokens, etc.) and
conversely (the URLs will not point to another image at some point, e.g. the
images are NOT numbered in ascending order (else "1.jpg" would point to
different images over time)).

    --min-thumb-size WIDTHxHEIGHT
    --min-image-size WIDTHxHEIGHT

Minimum size for an image to be considered a thumbnail worth following or an
image worth downloading. Useful not to download navigation buttons, logos, etc.
Default values are `--min-thumb-size=128x128` and `--min-image-size=400x400`.

    --max-aspect-ratio WIDTH:HEIGHT

Maximum ratio between WIDTH and HEIGHT (or HEIGHT on WIDTH, img-lurker is smart
enough to figure out) to consider an image is worth downloading.

For example, pass "16:9" and img-lurker will accept images with dimensions
1920x1080 or 1080x1920 as they are respectively 16:9 and 9:16 but also 1600x1200
or 1200x1600 because they are 4:3 (and 3:4) which is lower (more looking like
a square) than the max "16:9". Ratios of portrait and landscape are considered
equivalent.
However, passing "16:9" would discard a banner with dimensions 1200x300 because
its ratio is 4:1 which is way more distorted (very thin rectangle) than 16:9.
It would also reject a banner with dimensions 300x1200 because it is 1:4,
equivalent to 4:1.

A photo is rarely square but is almost never thin like 4:1, except panoramas, so
configure this option if you intend to download panoramas for example.
The default value is `--max-aspect-ratio=4:1`.

    --debug

Debug log.

## Limits

img-lurker will not interpret javascript, though it has specific hints to detect
lazy-loaded images, so it might not work on sites like instagram.
img-lurker will not open iframes, so it will fail to download a few images from
reddit.
img-lurker does not crawl a site and does not support nested galleries, it only
takes one gallery and expects it to contain the images desired.
