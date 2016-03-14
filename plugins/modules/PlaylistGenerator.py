'''
Playlist Generator
This module can generate .m3u playlists with tv guide
and groups
'''
import re
import urllib2
import plugins.config.playlist as config

class PlaylistGenerator(object):

    def __init__(self):
        self.itemlist = list()

    def addItem(self, itemdict):
        '''
        Adds item to the list
        itemdict is a dictionary with the following fields:
            name - item name
            url - item URL
            tvg - item tvg name (optional)
            tvgid - item tvg id (optional)
            group - item playlist group (optional)
            logo - item logo file name (optional)
        '''
        self.itemlist.append(itemdict)

    @staticmethod
    def _generatem3uline(item):
        '''
        Generates EXTINF line with url
        '''
        if not item.has_key('tvg'):
            item['tvg'] = ''
        if not item.has_key('tvgid'):
            item['tvgid'] = ''
        if not item.has_key('group'):
            item['group'] = ''
        if not item.has_key('logo'):
            item['logo'] = ''
        
        return config.m3uchanneltemplate % item

    def exportm3u(self, hostport, add_ts=False, empty_header=False, archive=False, header=None):
        '''
        Exports m3u playlist
        '''
        
        if add_ts:
            # Adding ts:// after http:// for some players
            hostport = 'ts://' + hostport
            
        if header is None:
            if not empty_header:
                itemlist = config.m3uheader
            else:
                itemlist = config.m3uemptyheader
        else:
            itemlist = header
        
        for i in self.itemlist:
            item = i.copy()
            item['tvg'] = item.get('tvg', '') if item.get('tvg') else \
                item.get('name').replace(' ', '_')
            # For .acelive and .torrent
            item['url'] = re.sub('^(http.+)$', lambda match: 'http://' + hostport + '/torrent/' + \
                             urllib2.quote(match.group(0), '') + '/stream.mp4', item['url'],
                                   flags=re.MULTILINE)
            # For PIDs
            item['url'] = re.sub('^(acestream://)?(?P<pid>[0-9a-f]{40})$', 'http://' + hostport + '/pid/\\g<pid>/stream.mp4',
                                    item['url'], flags=re.MULTILINE)

            # For channel id's
            if archive:
                item['url'] = re.sub('^([0-9]+)$', lambda match: 'http://' + hostport + '/archive/play?id=' + match.group(0),
                                    item['url'], flags=re.MULTILINE)
            else:
                item['url'] = re.sub('^([0-9]+)$', lambda match: 'http://' + hostport + '/channels/play?id=' + match.group(0),
                                        item['url'], flags=re.MULTILINE)

            itemlist += PlaylistGenerator._generatem3uline(item)

        return itemlist
