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
import gzip
from StringIO import StringIO
from modules.PluginInterface import AceProxyPlugin
from modules.PlaylistGenerator import PlaylistGenerator
import config.torrenttv as config
import config.p2pproxy as p2pconfig
from torrenttv_api import TorrentTvApi


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
        self.logomap = config.logomap
        self.updatelogos = p2pconfig.email != 're.place@me' and p2pconfig.password != 'ReplaceMe'

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
            req.add_header('Accept-encoding' , 'gzip')
            response = urllib2.urlopen(req, timeout=15)

            origin = ''

            if response.info().get('Content-Encoding') == 'gzip':
               # read the encoded response into a buffer
               buffer = StringIO(response.read())
               # gzip decode the response
               f = gzip.GzipFile(fileobj=buffer)
               # store the result
               origin = f.read()
               # close the buffer
               buffer.close()
               # else if the response isn't gzip-encoded
               self.logger.debug('Playlist downloaded using gzip compression')
            else:
              # store the result
               origin = response.read()
               self.logger.debug('Playlist downloaded')
            
            matches = re.finditer(r',(?P<name>\S.+) \((?P<group>.+)\)[\r\n]+(?P<url>[^\r\n]+)?', origin, re.MULTILINE)
            self.playlisttime = int(time.time())
            self.playlist = PlaylistGenerator()
            self.channels = dict()
            m = md5.new()

            for match in matches:
                itemdict = match.groupdict()
                encname = itemdict.get('name')
                name = encname.decode('UTF-8')
                logo = config.logomap.get(name)
                url = itemdict['url']
                if logo:
                    itemdict['logo'] = logo

                if (url.startswith('acestream://')) or (url.startswith('http://') and url.endswith('.acelive')):
                    self.channels[name] = url
                    itemdict['url'] = urllib2.quote(encname, '') + '.mp4'
                self.playlist.addItem(itemdict)
                m.update(encname)
            
            self.etag = '"' + m.hexdigest() + '"'
        except:
            self.logger.error("Can't download playlist!")
            self.logger.error(traceback.format_exc())
            return False
        
        if self.updatelogos:
            try:
                api = TorrentTvApi(p2pconfig.email, p2pconfig.password, p2pconfig.sessiontimeout, p2pconfig.zoneid)
                translations = api.translations('all')
                logos = dict()

                for channel in translations:
                    name = channel.getAttribute('name').encode('utf-8')
                    logo = channel.getAttribute('logo').encode('utf-8')
                    logos[name] = config.logobase + logo

                self.logomap = logos
                self.logger.debug("Logos updated")
            except:
                # p2pproxy plugin seems not configured
                self.updatelogos = False

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
            path = url.path[0:-1] if url.path.endswith('/') else url.path
            params = urlparse.parse_qs(url.query)
            fmt = params['fmt'][0] if params.has_key('fmt') else None
            
            if path.startswith('/torrenttv/channel/'):
                if not path.endswith('.mp4'):
                    connection.dieWithError(404, 'Invalid path: ' + path, logging.DEBUG)
                    return
                
                name = urllib2.unquote(path[19:-4]).decode('UTF8')
                url = self.channels.get(name)
                if not url:
                    connection.dieWithError(404, 'Unknown channel: ' + name, logging.DEBUG)
                    return
                elif url.startswith('acestream://'):
                    connection.path = '/pid/' + url[12:] + '/stream.mp4'
                    connection.splittedpath = connection.path.split('/')
                    connection.reqtype = 'pid'
                else:
                    connection.path = '/torrent/' + urllib2.quote(url, '') + '/stream.mp4'
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
                hostport = connection.headers['Host']
                path = '' if len(self.channels) == 0 else '/torrenttv/channel'
                add_ts = True if path.endswith('/ts')  else False
                header = '#EXTM3U url-tvg="%s" tvg-shift=%d deinterlace=auto\n' % (config.tvgurl, config.tvgshift)
                exported = self.playlist.exportm3u(hostport, path, add_ts=add_ts, header=header, fmt=fmt)
                
                connection.send_response(200)
                connection.send_header('Content-Type', 'application/x-mpegurl')
                connection.send_header('ETag', self.etag)
                connection.send_header('Content-Length', str(len(exported)))
                connection.send_header('Connection', 'close')
                connection.end_headers()
        
        if play:
            connection.handleRequest(headers_only, name, config.logomap.get(name), fmt=fmt)
        elif not headers_only:
            connection.wfile.write(exported)
