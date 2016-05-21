# -*- coding: utf-8 -*- 
class PlaylistConfig():
    
    # Default playlist format
    m3uemptyheader = '#EXTM3U\n'
    m3uheader = '#EXTM3U url-tvg="http://1ttvapi.top/ttv.xmltv.xml.gz"\n'
    # If you need the #EXTGRP field put this #EXTGRP:%(group)s\n after %(name)s\n.
    m3uchanneltemplate = \
        '#EXTINF:-1 group-title="%(group)s" tvg-name="%(tvg)s" tvg-id="%(tvgid)s" tvg-logo="%(logo)s",%(name)s\n%(url)s\n'
    
    # Channel names mapping. You may use this to rename channels. 
    # Examples: 
    # m3uchannelnames['Canal+ HD (France)'] = 'Canal+ HD'
    # m3uchannelnames['Sky Sport 1 HD (Italy)'] = 'Sky Sport 1 HD'
    m3uchannelnames = dict()
    
    # This method can be used to change a channel info such as name, group etc.
    # The following fields can be changed:
    #
    #    name - channel name
    #    url - channel URL
    #    tvg - channel tvg name
    #    tvgid - channel tvg id
    #    group - channel group
    #    logo - channel logo  
    @staticmethod
    def changeItem(item):
        if len(PlaylistConfig.m3uchannelnames) > 0:
            name = item['name']
            
            if isinstance(name, str):
                name = PlaylistConfig.m3uchannelnames.get(name)
                if name:
                    item['name'] = name
            elif isinstance(name, unicode):
                name = PlaylistConfig.m3uchannelnames.get(name.encode('utf8'))
                if name:
                    item['name'] = name.decode('utf8')
