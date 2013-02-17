from tornado import web, ioloop
from sockjs.tornado import SockJSRouter
from gpsstrike import *
import signal


def exit_handler(signal_no, frame):
    print "Interrupt by user"
    loop.close()
    exit()

if __name__ == '__main__':


    GPSStrikeConfig.parse('server.cfg')
    GPSStrikeConnection.fill_cmd_list()
    cfg = GPSStrikeConfig.cfg

    GPSStrikeRouter = SockJSRouter(GPSStrikeConnection, '/server')
    app = web.Application(GPSStrikeRouter.urls)

    print("Listen on {0:>s}:{1:>s} ...".format(cfg.get('server', 'ip'), cfg.get('server', 'port')))
    app.listen(cfg.get('server','port'),cfg.get('server','ip'))

    loop = ioloop.IOLoop.instance()

    signal.signal( signal.SIGINT, exit_handler )
    signal.signal( signal.SIGTERM, exit_handler )

    loop.start()