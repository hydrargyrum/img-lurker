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
    def search_thumbs(self):
        for link_el in self.doc.xpath('//a[.//img]'):
            link = urljoin(self.url, link_el.attrib['href'])

            imgs = link_el.xpath('.//img')
            if len(imgs) != 1:
                continue
            img = urljoin(self.url, imgs[0].attrib['src'])

            yield link, img

    def search_big_images(self):
        for img_el in self.doc.xpath('//img'):
            img = urljoin(self.url, img_el.attrib['src'])

            imgpage = self.browser.open(img).page
            if not (isinstance(imgpage, IPage) and bigger_than(imgpage.size, args.min_image_size)):
                continue

            yield img

    def search_big_image_old(self):
        for img_el in self.doc.xpath('//img'):
            img = urljoin(self.url, img_el.attrib['src'])

            imgpage = self.browser.open(img).page
            if not (isinstance(imgpage, IPage) and bigger_than(imgpage.size, args.min_image_size)):
                continue

            # found, now look if we're on a link to hi-res
            links = img_el.xpath('./ancestor::a[@href]')
            if len(links) != 1:
                return img

            link_el = links[0]
            link = urljoin(self.url, link_el.attrib['href'])
            logging.debug(f'[-] found higher res? {link} for {img}')
            return img

    def search_big_image(self):
        for img_el in self.doc.xpath('//img'):
            img = self._url_of(img_el, 'src')

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

    def search_2(self):
        for img_el in self.doc.xpath('//img'):
            img = self._url_of(img_el, 'src')

            if not self.browser.test_min_thumb(img):
                # doesn't even qualify as probable thumbnail
                continue

            link_el = self._container_link_el(img_el)
            if link_el is not None:
                link = self._url_of(link_el, 'href')
                if self.browser.test_image_link(link):
                    # img is link to bigger image
                    yield link
                    continue

                sub = self.browser.get_page_image(link)
                if sub:
                    # img is link to page with bigger image
                    yield sub
                    continue

            if self.browser.test_image_link(img):
                # img is already the big image
                yield img
                continue


class IPage(RawPage):
    def build_doc(self, content):
        return Image.open(BytesIO(content))

    @property
    def size(self):
        return self.doc.size


class MyBrowser(CacheMixin, PagesBrowser):
    BASEURL = 'http://example.com'

    hmatch = MimeURL('https?://.*', HPage, types=['text/html'])
    imatch = MimeURL('https?://.*', IPage, types=[re.compile('image/(?!svg).*')])

    def __init__(self, *args, **kwargs):
        super(MyBrowser, self).__init__(*args, **kwargs)
        self.is_updatable = False  # cache requests without caring about ETags

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

    def crawl_old(self, url):
        self.location(url)

        for link, thumb in self.page.search_thumbs():
            logging.debug(f'[-] testing {thumb}')

            thumbpage = self.open(thumb).page
            if isinstance(thumbpage, IPage) and bigger_than(thumbpage.size, args.min_thumb_size):
                logging.debug(f'[-] {link}')

                imgpage = self.open(link).page
                if isinstance(imgpage, IPage) and bigger_than(imgpage.size, args.min_image_size):
                    logging.debug(f'[+] found direct {link}')
                    self.download(link)
                    continue
                elif not isinstance(imgpage, HPage):
                    logging.debug(f'[-] too bad, {link} was not html or image')
                    continue

                bigimg = imgpage.search_big_image()
                if bigimg:
                    logging.debug(f'[+] found {bigimg}')
                    self.download(bigimg)

        for img in self.page.search_big_images():
            logging.debug(f'[+] found embedded {img}')
            self.download(img)

    def crawl(self, url):
        self.location(url)

        for img in self.page.search_2():
            self.download(img)

    def download(self, url):
        name_re = re.compile(r'/([^/?]+)(\?.*)?$')
        with open(name_re.search(url)[1], 'wb') as fd:
            logging.info(f'writing to {fd.name}')
            fd.write(self.open(url).content)


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


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(filename)s:%(lineno)s %(message)s',
)

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
    "(and height/width for portrait format)",
    metavar='NUM:DENOM',
)
parser.add_argument('--cookie', type=parse_cookie)

args = parser.parse_args()
args.max_aspect_ratio = Fraction(*args.max_aspect_ratio)
if args.max_aspect_ratio < 1:
    args.max_aspect_ratio = 1 / args.max_aspect_ratio

b = MyBrowser()
if args.cookie:
    b.session.cookies[args.cookie[0]] = args.cookie[1]

b.crawl(args.url)
