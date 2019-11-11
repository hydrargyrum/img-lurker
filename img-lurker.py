#!/usr/bin/env python3
# license: Do What the Fuck You Want to Public License version 2
# [http://wtfpl.net]

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from fractions import Fraction
from io import BytesIO
import logging
import re
from urllib.parse import urljoin

from PIL import Image
from weboob.browser import PagesBrowser, URL
from weboob.browser.cache import CacheMixin
from weboob.browser.pages import HTMLPage, RawPage


class MimeURL(URL):
    def __init__(self, *args, types, **kwargs):
        super(MimeURL, self).__init__(*args, **kwargs)
        self.types = types

    def handle(self, response):
        response_type = response.headers.get('Content-Type')
        if not response_type:
            return
        response_type = re.match('[^;]+', response_type)[0]  # ignore mime params

        for accepted_type in self.types:
            if isinstance(accepted_type, str) and accepted_type == response_type:
                break
            elif isinstance(accepted_type, re.Pattern) and accepted_type.fullmatch(response_type):
                break
        else:
            # not found any match
            return

        return super(MimeURL, self).handle(response)


class HPage(HTMLPage):
    def search_big_image(self):
        for img_el in self.doc.xpath('//img'):
            if 'src' not in img_el.attrib:
                logging.debug(f'skipping img tag without a src attribute')
                continue

            img = self._url_of(img_el, 'src')

            link_el = self._container_link_el(img_el)
            if link_el is not None:
                link = self._url_of(link_el, 'href')
                if self.browser.test_image_link(link):
                    return link

            if self.browser.test_image_link(img):
                return img

    def _container_link_el(self, img_el):
        links = img_el.xpath('./ancestor::a[@href]')

        try:
            link_el, = links
        except ValueError:
            return

        return link_el

    def _url_of(self, el, attr):
        return urljoin(self.url, el.attrib[attr])

    def search_images(self):
        for img_el in self.doc.xpath('//img'):
            img = self._url_of(img_el, 'src')

            if not self.browser.test_min_thumb(img):
                logging.debug(f'{img} does not even qualify as probable thumbnail')
                continue

            link_el = self._container_link_el(img_el)
            if link_el is not None:
                link = self._url_of(link_el, 'href')
                if self.browser.test_image_link(link):
                    logging.debug(f'thumb {img} links directly to bigger image')
                    yield link
                    continue

                sub = self.browser.get_page_image(link)
                if sub:
                    logging.debug(f'thumb {img} links to page with bigger image')
                    yield sub
                    continue

            if self.browser.test_image_link(img):
                logging.debug(f'{img} has no link and is an embedded big image')
                yield img
                continue

    def go_xpath(self, xpath):
        links = self.doc.xpath(xpath)
        if links:
            logging.info(f'visiting next page {links[0]}')
            return self.browser.location(links[0])


class IPage(RawPage):
    def build_doc(self, content):
        return Image.open(BytesIO(content))

    @property
    def size(self):
        return self.doc.size

    def download(self):
        name_re = re.compile(r'/([^/?]+)(\?.*)?$')
        with open(name_re.search(self.url)[1], 'wb') as fd:
            logging.info(f'writing to {fd.name}')
            fd.write(self.content)


class LurkBrowser(CacheMixin, PagesBrowser):
    BASEURL = 'http://example.com'

    hmatch = MimeURL('https?://.*', HPage, types=['text/html'])
    imatch = MimeURL('https?://.*', IPage, types=[re.compile('image/(?!svg).*')])

    def __init__(self, *args, **kwargs):
        super(LurkBrowser, self).__init__(*args, **kwargs)
        self.is_updatable = False  # cache requests without caring about ETags

    open = CacheMixin.open_with_cache

    def test_min_thumb(self, url):
        if url.startswith('data:'):
            return

        imgpage = self.open(url).page
        return isinstance(imgpage, IPage) and bigger_than(imgpage.size, args.min_thumb_size)

    def test_image_link(self, url):
        if url.startswith('data:'):
            return

        imgpage = self.open(url).page
        return isinstance(imgpage, IPage) and bigger_than(imgpage.size, args.min_image_size)

    def get_page_image(self, url):
        hpage = self.open(url).page
        if isinstance(hpage, HPage):
            return hpage.search_big_image()

    def lurk(self, url):
        if url:
            logging.info(f'visiting page {url}')
            self.location(url)

        for img in self.page.search_images():
            self.download(img)

    def go_xpath(self, xpath):
        return self.page.go_xpath(xpath)

    def download(self, url):
        self.open(url).page.download()


def bigger_than(test, expected):
    if test[0] < expected[0] or test[1] < expected[1]:
        return False

    ratio_test = Fraction(test[0], test[1])
    if ratio_test < 1:
        ratio_test = 1 / ratio_test

    return ratio_test <= args.max_aspect_ratio


def build_tuple_maker(sep):
    def arg2size(s):
        m = re.fullmatch(fr'(\d+){sep}(\d+)', s)
        if m:
            return (int(m[1]), int(m[2]))


def parse_cookie(cstr):
    v = cstr.partition('=')
    return v[0], v[2]


parser = ArgumentParser(
    formatter_class=ArgumentDefaultsHelpFormatter,
    description='Extract images from a page',
)
parser.add_argument('url')
parser.add_argument(
    '--min-thumb-size', type=build_tuple_maker('x'), default=(128, 128),
    metavar='WIDTHxHEIGHT',
)
parser.add_argument(
    '--min-image-size', type=build_tuple_maker('x'), default=(400, 400),
    metavar='WIDTHxHEIGHT',
)
parser.add_argument(
    '--max-aspect-ratio', type=build_tuple_maker('[:/]'), default=(4, 1),
    help="Max ratio between width/height to skip banners, ads etc. "
    "(or height/width if portrait format)",
    metavar='NUM:DENOM',
)
parser.add_argument(
    '--cookie', dest='cookies', type=parse_cookie, action='append',
    default=[],
)
parser.add_argument('--next-page-xpath')
parser.add_argument('--debug', action='store_const', const=True)

args = parser.parse_args()
args.max_aspect_ratio = Fraction(*args.max_aspect_ratio)
if args.max_aspect_ratio < 1:
    args.max_aspect_ratio = 1 / args.max_aspect_ratio

logging.basicConfig(
    level=logging.DEBUG if args.debug else logging.INFO,
    format='%(asctime)s %(levelname)s %(filename)s:%(lineno)s %(message)s',
)

browser = LurkBrowser()
for cookie in args.cookies:
    browser.session.cookies[cookie[0]] = cookie[1]

browser.lurk(args.url)
if args.next_page_xpath:
    while browser.go_xpath(args.next_page_xpath):
        browser.lurk(None)
