# -*- coding: utf-8 -*-
import argparse
import logging
import sys
import os
import signal
from ss import utils

def to_bytes(s):
    if type(s) != bytes:
        return s.encode("utf8")
    return s


class Command(object):

    DESC = "A fast tunnel proxy that helps you bypass firewalls."
    USAGE="myss <subcommand> [options] [args]"

    def __init__(self, parser=None):
        
        self.parser = parser if parser else \
                argparse.ArgumentParser(description=self.DESC,
                usage=self.USAGE
                    )
        subcommand = self.parser.add_subparsers(title="subcommands", 
                        prog="run myss as", dest="subcmd")
        self.local_parser = subcommand.add_parser("local")
        self.server_parser = subcommand.add_parser("server")
        self.add_server_argument()
        self.add_local_argument()

    def add_general_argument(self, parser):
        parser = parser.add_argument_group("General options")
        parser.add_argument("-v", help="verbose mode")
        parser.add_argument("-d", help="command for daemon mode", dest="action",
                            choices=["start", "stop", "restart"])
        parser.add_argument("--pid-file", help="pid file for daemon mode", 
                            type=self._check_path, dest="pid_file")
        parser.add_argument("--log-file", help="log file for daemon mode", 
                            type=self._check_path, dest="log_file")
        parser.add_argument("--user", help="username to run as")
        parser.add_argument("--quiet", help="quiet mode, only show warnings and errors",
                             action='store_true')
        parser.add_argument("--version", help="show version information",
                             action='version', version='myss 0.0')

    def add_common_argument(self, parser):
        parser.add_argument("-c", metavar="CONFIG", type=self._check_config,
                            help="path to config file, if this parameter is specified," 
                            "all other parameters will be ignored!", 
                            dest="config")
        
        parser.add_argument("-p", metavar="PASSWORD", required=True,
                            help="password", dest="password")

        parser.add_argument("-m", metavar="METHOD", default=to_bytes("aes-256-cfb"),
                            help="encryption method, default: aes-256-cfb", 
                            type=self._check_method, dest="method")

        parser.add_argument("-t", metavar="TIMEOUT", default=300, 
                            type=self._check_timeout, dest="timeout",
                            help="timeout in seconds for idle connection, "
                            "default: 300")

        parser.add_argument("--fast-open", action='store_true', dest="fast_open",
                            help="use TCP_FASTOPEN, requires Linux 3.7+")
        
    def add_server_argument(self):
        
        parser = self.server_parser
        parser.add_argument("--workers", type=self._check_workers, metavar="WORKERS",
                            help="number of workers, available on Unix/Linux,"
                            " count of cpu cores is recommended.",
                            default=self._default_workers())

        parser.add_argument("-s", metavar="ADDR", dest="server", type=self._check_addr,
                            default=to_bytes("0.0.0.0"), required=True, 
                            help=" hostname or ipaddr, default is 0.0.0.0")

        parser.add_argument("-P", metavar="PORT", type=int, 
                            default=8388, required=True,
                            help="port, default: 8388", dest="server_port")
        self.add_common_argument(parser)
        parser.add_argument("--forbidden-ip", type=self._check_iplist, 
                            metavar="IPLIST", dest="forbidden_ip",
                            help="comma seperated IP list forbidden to connect")

        parser.add_argument("--manager-address", dest="manager_address",
                            help="optional server manager UDP address, see wiki")
        self.add_general_argument(self.server_parser)

    def add_local_argument(self):
        parser = self.local_parser
        parser.add_argument("-s", metavar="ADDR", dest="local_address", 
                            default="127.0.0.1", required=True,
                            help="interface for local server to listen on, "
                            "default is 127.0.0.1" , type=self._check_addr)

        parser.add_argument("-P", metavar="PORT", type=int, default=1080,
                            help="local listen port, default: 1080", 
                            dest="local_port", required=True)

        parser.add_argument("-H", metavar="REMOTE-HOST", dest="rhost",
                            help="remote ss server host, format is hostname:port"
                            "eg. ssbetter.org:8888", required=True,)

        self.add_common_argument(parser)

        parser.add_argument("--gfw-list", type=self._check_iplist, metavar="IPLIST",
                            help="a file which contains host forbidden by gfw",
                            dest="gfwlist")
        self.add_general_argument(self.local_parser)

    def _to_abspath(self, p):
        is_absolute = os.path.isabs(p)        
        if not is_absolute:
            basedir = os.getcwd()
            p = os.path.join(basedir, p)
        return p

    def _check_addr(self, addr):
        return to_bytes(addr)

    def _default_workers(self):
        from multiprocessing import cpu_count
        if os.name != "posix":
            return 1
        else:
            return cpu_count()

    def _check_workers(self, c):
        try:
            c = int(c)
            if os.name != "posix" and c > 1:
                logging.warn("fork mode is only support on `posix`, "
                             "other platform worker count is limit 1")
                c = 1
            return c
        except ValueError:
            raise argparse.ArgumentTypeError("invalid int value: '%s'" % c)

    def _check_timeout(self, t):
        try:
            t = int(t)
        except ValueError:
            raise argparse.ArgumentTypeError("invalid int value: '%s'" % t)
        if t < 300:
            logging.warn("your timeout `%d` seems too short" % t)
        elif t > 600:
            logging.warn("your timeout `%d` seems too long" % t)
        return t

    def _check_pswd(self, pswd):
        return to_bytes(pswd)

    def _check_method(self, m):
        m = m.lower()
        if m in ["table", "rc4"]:
            logging.warn("%s is not safe; please use a safer cipher" 
                         " like `AES-256-CFB` is recommended." % m)
        return to_bytes(m)

    def _check_path(self, p):
        p = self._to_abspath(p)
        parent = os.path.dirname(p)
        if not os.access(parent, os.W_OK):
            raise argparse.ArgumentTypeError("can't write to %s, Permission Denied" % p)
        return p
        
    def _check_config(self, f):
        f = self._to_abspath(f)
        if not os.path.exists(f):
            raise argparse.ArgumentTypeError("config file `%s` doen't exist!" % f)
        import json
        try:
            with open(f, "r") as f:
                cfg = json.load(f)
            if "password" not in cfg:
                raise argparse.ArgumentTypeError("`password` must be specified in config file")
            cfg["password"] = to_bytes(cfg["password"])
            cfg["method"] = to_bytes(cfg["method"])
            return cfg
        except ValueError:
            raise argparse.ArgumentTypeError("config file must be json format")

    def _check_iplist(self, f):
        pass

    def _cfg_param(self, args):
        cfg = None
        for i, arg in enumerate(args):
            if arg == "-c":
                if i + 1 >= len(args):
                    cfg = None
                else:
                    cfg = args[i+1]
                break
            elif arg.startswith("-c"):
                cfg = arg.strip("-c")
                break
        return cfg

    def parse(self, args=None):
        if not args:
            args = sys.argv[1:]
        cfg = self._cfg_param(args)

        if not args:
            return self.parser.parse_args(args).__dict__
        elif not cfg:
            return self.parser.parse_args(args).__dict__
        else:
            subc = args[0]
            try:
                if subc not in ["local", "server"]:
                    raise argparse.ArgumentTypeError
                config = self._check_config(cfg)
                config["subcmd"] = subc
                return config
            except argparse.ArgumentTypeError:
                self.parser.parse_args([subc, "-c%s"%cfg])
            


def get_cofing_from_cli():
    from ss import settings
    cmd = Command()
    cfg = cmd.parse()
    settings.settings.__dict__ = cfg
    config_logging(cfg)
    return cfg

def run(io_loop=None):
    config = get_cofing_from_cli()
    from ss.ioloop import IOLoop
    if not io_loop:
        io_loop = IOLoop()
    subcmd = config.get("subcmd")
    handlers = {"local": run_local, "server": run_server}
    return handlers[subcmd](io_loop, config)

def run_local(io_loop, config):
    from ss.core import tcphandler, udphandler
    from ss.core.asyncdns import DNSResolver
    try:
        sa = config['local_address'], config['local_port']
        logging.info("starting local at %s:%d" % sa)
        dns_resolver = DNSResolver(io_loop)
        tcp_server = tcphandler.ListenHandler(io_loop, sa, 
            tcphandler.LocalConnHandler, dns_resolver, **config)
        udp_server = udphandler.ListenHandler(io_loop, sa, 
            udphandler.ConnHandler, 1, dns_resolver, **config)  # 1 means local
        dns_resolver.register()
        udp_server.register()
        tcp_server.register()

        def on_quit(s, _):
            logging.warn('received SIGQUIT, doing graceful shutting down..')
            tcp_server.destroy()
            udp_server.destroy()

        def on_interrupt(s, _):
            sys.exit(1)
            
        signal.signal(signal.SIGINT, on_interrupt)    
        signal.signal(getattr(signal, 'SIGQUIT', signal.SIGTERM), on_quit)
        io_loop.run()
    except Exception as e:
        logging.error(e, exc_info=True)
        sys.exit(1)

def run_server(io_loop, config):
    from ss.core import tcphandler, udphandler
    from ss.core.asyncdns import DNSResolver
    sa = config['server'], config['server_port']
    logging.info("starting server at %s:%d" % sa)

    dns_resolver = DNSResolver(io_loop)
    tcp_server = tcphandler.ListenHandler(io_loop, sa, 
        tcphandler.RemoteConnHandler, dns_resolver, **config)
    upd_server = udphandler.ListenHandler(io_loop, sa, 
        udphandler.ConnHandler, 0, dns_resolver, **config)
    servers = [dns_resolver, tcp_server, upd_server]

    def on_quit(s, _):
        logging.warn('received SIGQUIT, doing graceful shutting down..')
        for server in servers:
            server.destroy()
        logging.warn('all servers have been shut down')

    def start():
        try:
            for server in servers:
                server.register()
            io_loop.run()
        except Exception as e:
            logging.error(e, exc_info=True)
            sys.exit(1)

    workers = config.get("workers", 1)
    if workers > 1:
        children = []
        def on_master_exit(s, _):
            for pid in children:
                try:
                    os.kill(pid, s)
                    os.waitpid(pid, 0)
                except OSError:  # child may already exited
                    pass
            sys.exit(0)

        is_child = False
        for i in range(workers):
            rpid = os.fork()
            if rpid == 0:
                logging.info('worker started')
                is_child = True
                start()
                break
            else:
                children.append(rpid)
        if not is_child:
            signal.signal(signal.SIGTERM, on_master_exit)
            signal.signal(signal.SIGQUIT, on_master_exit)
            signal.signal(signal.SIGINT, on_master_exit)

            for server in servers:
                server.destroy()
            for child in children:
                os.waitpid(child, 0)
    else:
        logging.info('worker started')
        start()

def config_logging(cfg):
    logging.getLogger('').handlers = []
    kwargs = dict(
        format='%(asctime)s %(levelname)-8s lineno[%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    kwargs["level"] = logging.WARN if cfg.get("quiet") \
        else logging.INFO
    if kwargs.get("log_file"):
        kwargs["filename"] = kwargs["log_file"]

    logging.basicConfig(**kwargs)

if __name__ == "__main__":
    c = Command()
    print c.parse()