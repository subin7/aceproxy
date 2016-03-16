'''
Torrent-tv.ru Playlist Downloader Plugin
http://ip:port/ttvplaylist
'''
import re
import logging
import urllib2
import time
import gevent
import threading
import urlparse
import md5
import traceback
from modules.PluginInterface import AceProxyPlugin
from modules.PlaylistGenerator import PlaylistGenerator
import config.torrenttv as config


class Torrenttv(AceProxyPlugin):

    # ttvplaylist handler is obsolete
    handlers = ('torrenttv', 'ttvplaylist')

    def __init__(self, AceConfig, AceStuff):
        self.logger = logging.getLogger('plugin_torrenttv')
        self.lock = threading.Lock()
        self.channels = None
        self.playlist = None
        self.playlisttime = None
        self.etag = None
        
        if config.updateevery:
            gevent.spawn(self.playlistTimedDownloader)

    def playlistTimedDownloader(self):
        while True:
            with self.lock:
                self.downloadPlaylist()
            gevent.sleep(config.updateevery * 60)

    def downloadPlaylist(self):
        try:
            self.logger.debug('Trying to download playlist')
            req = urllib2.Request(config.url, headers={'User-Agent' : "Magic Browser"})
            origin = urllib2.urlopen(req, timeout=10).read()
            matches = re.finditer(r',(?P<name>\S.+) \((?P<group>.+)\)\n(?P<url>^.+$)', origin, re.MULTILINE)
            self.playlisttime = int(time.time())
            self.playlist = PlaylistGenerator()
            self.channels = dict()
            m = md5.new()
            counter = 0
            
            for match in matches:
                counter += 1
                itemdict = match.groupdict()
                name = itemdict.get('name').decode('UTF-8')
                logo = config.logomap.get(name)
                url = itemdict['url']
                self.playlist.addItem(itemdict)
                
                if logo:
                    itemdict['logo'] = logo
                
                if url.startswith('http://') and url.endswith('.acelive'):
                    num = str(counter)
                    self.channels[num] = [name, url]
                    itemdict['url'] = num
                    
                m.update(itemdict.get('name'))
                m.update(itemdict['url'])
            
            self.etag = '"' + m.hexdigest() + '"'
        except:
            self.logger.error("Can't download playlist!")
            self.logger.error(traceback.format_exc())
            return False

        return True

    def handle(self, connection, headers_only=False):
        play = False
        
        with self.lock:
            
            # 30 minutes cache
            if not self.playlist or (int(time.time()) - self.playlisttime > 30 * 60):
                if not self.downloadPlaylist():
                    connection.dieWithError()
                    return
            
            url = urlparse.urlparse(connection.path)
            
            if url.path.endswith('/play'):
                cid = urlparse.parse_qs(url.query)['id'][0]
                channel = self.channels[cid]
                connection.path = '/torrent/' + urllib2.quote(channel[1], '') + '/stream.mp4'
                connection.splittedpath = connection.path.split('/')
                connection.reqtype = 'torrent'
                play = True
            elif self.etag == connection.headers.get('If-None-Match'):
                self.logger.debug('ETag matches - returning 304')
                connection.send_response(304)
                connection.send_header('Connection', 'close')
                connection.end_headers()
                return
            else:
                if len(self.channels) == 0:
                    hostport = connection.headers['Host']
                else:
                    hostport = connection.headers['Host'] + '/torrenttv'

                add_ts = True if url.path.endswith('/ts')  else False
                header = '#EXTM3U url-tvg="%s" tvg-shift=%d\n' %(config.tvgurl, config.tvgshift)
                exported = self.playlist.exportm3u(hostport, add_ts=add_ts, header=header)
                
                connection.send_response(200)
                connection.send_header('Content-Type', 'application/x-mpegurl')
                connection.send_header('ETag', self.etag)
                connection.send_header('Content-Length', str(len(exported)))
                connection.send_header('Connection', 'close')
                connection.end_headers()
        
        if play:
            connection.handleRequest(headers_only, channel[0], config.logomap.get(channel[0]))
        elif not headers_only:
            connection.wfile.write(exported)
