# -*- coding: utf-8 -*-
import re
import time
import logging
from ss.wrapper import onstart
from ss.settings import settings

class ProxyAutoConfig(object):

    content = ""
    URI = "/pac?t="

    def __str__(self):
        s = "HTTP/1.1 200 OK\r\n"\
        "Server: myss\r\n"\
        "Connection: Close\r\n"\
        "Content-Type: application/x-ns-proxy-autoconfig\r\n"\
        "Content-Length: %d\r\n"\
        "\r\n"\
        "%s\r\n" % (len(self.content), self.content)
        return s

    @classmethod
    def load(cls):
        path = settings["pac"]
        with open(path, "r") as f:
            data = f.read()
        host = settings["local_address"]
        socks5_port = settings.get("local_port", 1080)
        http_port = settings.get("local_http_port", 1081)
        proxy = ' proxy = "PROXY %s:%d; SOCKS %s:%d; ";\n' %\
            (host, http_port, host, socks5_port)
        data = re.sub("proxy *= *[\s\S]+?\n", proxy, data, 1)
        cls.content = data
        cls.URI = "/pac?t=%d" % int(time.time())
        logging.info("reload pac file : %s" % path)

@onstart
def load_pac():
    ProxyAutoConfig.load()

if __name__ == "__main__":

    print(str(ProxyAutoConfig()))