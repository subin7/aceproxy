# -*- coding: utf-8 -*-
'''
Torrent Films Playlist Plugin
http://ip:port/films
(C) Dorik1972
'''
import os
import logging
import urllib2
import base64
import json
from modules.PluginInterface import AceProxyPlugin
import config.torrentfilms as config
from aceconfig import AceConfig

class Torrentfilms(AceProxyPlugin):

    handlers = ('torrentfilms', 'films',)

    def __init__(self, AceConfig, AceStuff):
        self.logger = logging.getLogger('plugin_TorrentFilms')
        self.filelist = None
        pass

    def createFilelist(self):
        try:
            self.logger.debug("Trying to load torrent files from "+config.directory)
            if os.path.exists(config.directory):
              self.filelist = filter(lambda x: x.endswith(('.torrent','.torrent.added')), os.listdir(config.directory))
        except:
            self.logger.error("Can't load torrent files from "+config.directory)
            return False
        return True

    def getCid(self, filename):
        cid = ''
        try:
            self.logger.debug('Get file name : '+filename)
            with open(filename, "rb") as torrent_file:
                 f = base64.b64encode(torrent_file.read())
            req = urllib2.Request('http://api.torrentstream.net/upload/raw', f)
            req.add_header('User-Agent', 'Python-urllib/2.7')
            req.add_header('Content-Type', 'application/octet-stream')
            cid = json.loads(urllib2.urlopen(req, timeout=10).read())['content_id']
            self.logger.debug("CID: " + cid)
        except:
               pass

        if cid == '':
             logging.debug("Failed to get ContentID from WEB API")

        return None if not cid or cid == '' else cid


    def handle(self, connection, headers_only=False):

        if not self.filelist:
            if not self.createFilelist():
               connection.dieWithError()
               return

        hostport = connection.headers['Host']
        connection.send_response(200)
        connection.send_header('Content-Type', 'application/x-mpegurl')
        connection.end_headers()

        if headers_only:
            return;

        connection.wfile.write('#EXTM3U deinterlace=1 m3uautoload=1 cache=1000\n')

        for i in range(len(self.filelist)):
             self.filenames = config.directory+'/'+self.filelist[i]
             content_id = self.getCid(self.filenames)

             if content_id!='':
                req = urllib2.Request('http://'+AceConfig.acehost+':6878/server/api?method=get_media_files&content_id='+content_id)
                try:
                   result = json.loads(urllib2.urlopen(req, timeout=10).read())['result']
                   for key in result:
                      connection.wfile.write('#EXTINF:-1 group-title="TorrentFilms",'+ result[key].encode('UTF-8').translate(None, b"%~}{][^$@*,!?&`|><") +'\n') 
                      connection.wfile.write('http://'+hostport.partition(':')[0]+':6878/ace/getstream?id='+content_id+'&_idx='+key+'\n') 
                except:
                   self.logger.debug("Can't load info form "+self.filelist[i]+" file !!")
                   pass

        self.filelist = None
        self.logger.debug('Playlist created!')
