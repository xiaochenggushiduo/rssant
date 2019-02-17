import codecs
import cchardet


def resolve_response_encoding(response):
    encoding = response.encoding
    if not encoding:
        # response.apparent_encoding使用chardet检测编码，有些情况会非常慢
        # 换成cchardet实现，性能可以提升100倍
        encoding = cchardet.detect(response.content)['encoding']
        if encoding:
            encoding = encoding.lower()
            # 解决常见的乱码问题，chardet没检测出来基本就是windows-1254编码
            if encoding == 'windows-1254' or encoding == 'ascii':
                encoding = 'utf-8'
        else:
            encoding = 'utf-8'
    encoding = codecs.lookup(encoding).name
    response.encoding = encoding


def coerce_url(url):
    url = url.strip()
    if url.startswith("feed://"):
        return "http://{}".format(url[7:])
    if "://" not in url:
        return "http://{}".format(url)
    return url
