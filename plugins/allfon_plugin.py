'''
Allfon.tv Playlist Downloader Plugin
http://ip:port/allfon
'''
import re
import logging
import urlparse
import requests
import time
from modules.PluginInterface import AceProxyPlugin
from modules.PlaylistGenerator import PlaylistGenerator
import config.allfon as config


class Allfon(AceProxyPlugin):

    # ttvplaylist handler is obsolete
    handlers = ('allfon',)

    logger = logging.getLogger('Plugin_Allfon')
    playlist = None
    playlisttime = None

    def __init__(self, AceConfig, AceStuff):
        pass

    def downloadPlaylist(self):
        try:
            Allfon.logger.debug('Trying to download AllFonTV playlist')
            self.headers = {'User-Agent' : "Magic Browser",
                            'Accept-Encoding': 'gzip'}
            if config.useproxy:
                   r = requests.get(config.url, headers=self.headers, proxies=config.proxies, timeout=30)
            else:
                   r = requests.get(config.url, headers=self.headers, timeout=10)
            Allfon.playlist = r.text.encode('UTF-8')
            Allfon.logger.debug('AllFon playlist ' + r.url + ' downloaded !')
            Allfon.playlisttime = int(time.time())
        except:
            Allfon.logger.error("Can't download AllFonTV playlist!")
            return False

        return True

    def handle(self, connection, headers_only=False):
        # 30 minutes cache
        if not Allfon.playlist or (int(time.time()) - Allfon.playlisttime > 30 * 60):
            if not self.downloadPlaylist():
                connection.dieWithError()
                return

        hostport = connection.headers['Host']

        connection.send_response(200)
        connection.send_header('Content-Type', 'application/x-mpegurl')
        connection.end_headers()

        if headers_only:
            return;

        matches = re.finditer(r'\#EXTINF\:0\,(?P<name>\S.+)\n.+\n.+\n(?P<url>^acestream.+$)',
                              Allfon.playlist, re.MULTILINE)
        add_ts = False
        try:
            if connection.splittedpath[2].lower() == 'ts':
                add_ts = True
        except:
            pass

        playlistgen = PlaylistGenerator(m3uchanneltemplate=config.m3uchanneltemplate)
        for match in matches:
            playlistgen.addItem(match.groupdict())

        url = urlparse.urlparse(connection.path)
        params = urlparse.parse_qs(url.query)
        fmt = params['fmt'][0] if params.has_key('fmt') else None
        header = '#EXTM3U url-tvg="%s" tvg-shift=%d deinterlace=1 m3uautoload=1 cache=1000\n' %(config.tvgurl, config.tvgshift)
        connection.wfile.write(playlistgen.exportm3u(hostport, header=header, add_ts=add_ts, fmt=fmt))
