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

    def exportm3u(self, hostport, path='', add_ts=False, empty_header=False, archive=False, header=None, fmt=None):
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
            item['name'] = item['name'].replace('"', "'").replace(',', '.')
            item['tvg'] = item.get('tvg', '') if item.has_key('tvg') else item.get('name').replace(' ', '_')
            url = item['url'];

            # For .acelive and .torrent
            item['url'] = re.sub('^(http.+)$', lambda match: 'http://' + hostport + path + '/torrent/' + \
                             urllib2.quote(match.group(0), '') + '/stream.mp4', url,
                                   flags=re.MULTILINE)
            if url == item['url']: # For PIDs
                item['url'] = re.sub('^(acestream://)?(?P<pid>[0-9a-f]{40})$', 'http://' + hostport + path + '/pid/\\g<pid>/stream.mp4',
                                    url, flags=re.MULTILINE)
            if archive and url == item['url']: # For archive channel id's
                item['url'] = re.sub('^([0-9]+)$', lambda match: 'http://' + hostport + path + '/archive/play?id=' + match.group(0),
                                    url, flags=re.MULTILINE)
            if not archive and url == item['url']: # For channel id's
                item['url'] = re.sub('^([0-9]+)$', lambda match: 'http://' + hostport + path + '/channels/play?id=' + match.group(0),
                                        url, flags=re.MULTILINE)
            if url == item['url']: # For channel names
                item['url'] = re.sub('^([^/]+)$', lambda match: 'http://' + hostport + path + '/' + match.group(0),
                                        url, flags=re.MULTILINE)
            
            if fmt:
                if '?' in item['url']:
                    item['url'] = item['url'] + '&fmt=' + fmt
                else:
                    item['url'] = item['url'] + '/?fmt=' + fmt

            itemlist += PlaylistGenerator._generatem3uline(item)

        return itemlist
