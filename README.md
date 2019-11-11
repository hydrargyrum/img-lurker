# img-lurker

img-lurker takes a URL of an HTML web page and downloads linked images on it. If an image is
a link to a bigger version of the image, it will follow the link. If the link is a dedicated page
containing a bigger version of the previous thumbnail, it will rather download the bigger version.

img-lurker has a "minimum image size" for considering an image is worthy of being downloaded and
isn't UI stuff like buttons/separators. img-lurker will not follow links if the link tag doesn't
contain an image tag (assumed to be the thumbnail).
