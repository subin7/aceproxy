'''
Simple statistics plugin

To use it, go to http://127.0.0.1:8000/stat
'''
from modules.PluginInterface import AceProxyPlugin
import time
import locale

class Stat(AceProxyPlugin):
    handlers = ('stat', 'favicon.ico')
    locale.setlocale(locale.LC_ALL, locale.getdefaultlocale())
    
    def __init__(self, AceConfig, AceStuff):
        self.config = AceConfig
        self.stuff = AceStuff

    def handle(self, connection, headers_only=False):
        if connection.reqtype == 'favicon.ico':
            connection.send_response(404)
            return
        
        connection.send_response(200)
        connection.send_header('Content-type', 'text/html; charset=utf-8')
        connection.end_headers()
        
        if headers_only:
            return
        
        connection.wfile.write(
            '<html><body><h4>Connected clients: ' + str(self.stuff.clientcounter.total) + '</h4>')
        connection.wfile.write(
            '<h5>Concurrent connections limit: ' + str(self.config.maxconns) + '</h5><table  border="1" cellspacing="0" cellpadding="3">')
        for i in self.stuff.clientcounter.clients:
            for c in self.stuff.clientcounter.clients[i]:
                connection.wfile.write('<tr><td>')
                if c.channelIcon:
                    connection.wfile.write('<img src="' + c.channelIcon + '" width="40" height="16" />&nbsp;')
                if c.channelName:
                    connection.wfile.write(c.channelName.encode('UTF8'))
                else:
                    connection.wfile.write(i)
                connection.wfile.write('</td><td>' + c.handler.clientip + '</td>')
                connection.wfile.write('<td>' + time.strftime('%c', time.localtime(c.connectionTime)) + '</td></tr>')
        connection.wfile.write('</table></body></html>')
