# -*- coding: utf-8 -*-

"""
socks5 associate request premble

--------+-------+--------+--------+-----...---+----------------+ 
   VER  |  CMD  |  RSV   |  ATYP  | DST.ADDR  |    DST.PORT    |
--------+-------+--------+--------+-----...---+----------------+ 
   1B   |  1B   |   1B   |   1B   |    var    |       2B       |
--------+-------+--------+--------+-----...---+----------------+ 


socks5 associate response premble

--------+-------+--------+--------+-----...---+----------------+ 
   VER  |  REP  |  RSV   |  ATYP  | BND.ADDR  |    BND.PORT    |
--------+-------+--------+--------+-----...---+----------------+ 
   1B   |  1B   |   1B   |   1B   |    var    |       2B       |
--------+-------+--------+--------+-----...---+----------------+ 


udp forwarding request premble

+----+------+------+----------+----------+----------+
|RSV | FRAG | ATYP | DST.ADDR | DST.PORT |   DATA   |
+----+------+------+----------+----------+----------+
| 2  |  1   |  1   | Variable |    2     | Variable |
+----+------+------+----------+----------+----------+

udp forwarding response premble

+----+------+------+----------+----------+----------+
|RSV | FRAG | ATYP | DST.ADDR | DST.PORT |   DATA   |
+----+------+------+----------+----------+----------+
| 2  |  1   |  1   | Variable |    2     | Variable |
+----+------+------+----------+----------+----------+

"""

import socket
import struct
import logging
import os
from ss import utils

ATYP_IPV4 = 0x01
ATYP_HOST = 0x03
ATYP_IPV6 = 0x04

CMD_CONNECT = 0x01
CMD_BIND = 0x02
CMD_UDPFWD = 0x03


def parse_header(data):
    if not data:
        return None
    addrtype = ord(data[0])
    dest_addr = None
    dest_port = None
    header_length = 0
    if addrtype == ATYP_IPV4:
        if len(data) >= 7:
            dest_addr = socket.inet_ntoa(data[1:5])
            dest_port = struct.unpack('>H', data[5:7])[0]
            header_length = 7
        else:
            logging.warn('header is too short')
    elif addrtype == ATYP_HOST:
        if len(data) > 2:
            addrlen = ord(data[1])
            if len(data) >= 2 + addrlen:
                dest_addr = data[2:2 + addrlen]
                raw_port = data[2 + addrlen:4 + addrlen]
                dest_port = struct.unpack('>H', raw_port)[0]
                header_length = 4 + addrlen
            else:
                logging.warn('header is too short')
        else:
            logging.warn('header is too short')
    elif addrtype == ATYP_IPV6:
        if len(data) >= 19:
            dest_addr = socket.inet_ntop(socket.AF_INET6, data[1:17])
            dest_port = struct.unpack('>H', data[17:19])[0]
            header_length = 19
        else:
            logging.warn('header is too short')
    else:
        logging.warn('unsupported addrtype %d, maybe wrong password or '
                    'encryption method' % addrtype)
    if dest_addr is None:
        return None
    return addrtype, utils.to_bytes(dest_addr), dest_port, header_length


def gen_ack():
    r = b'\x05\x00\x00\x01\x00\x00\x00\x00\x10\x10'
    return r, len(r)

def gen_nego():
    r = b'\x05\00'
    return r, len(r)