
class PlaylistConfig():
    
    # Default playlist format
    m3uemptyheader = '#EXTM3U\n'
    m3uheader = '#EXTM3U url-tvg="http://1ttvapi.top/ttv.xmltv.xml.gz"\n'
    # If you need the #EXTGRP field put this #EXTGRP:%(group)s\n after %(name)s\n.
    m3uchanneltemplate = \
        '#EXTINF:-1 group-title="%(group)s" tvg-name="%(tvg)s" tvg-id="%(tvgid)s" tvg-logo="%(logo)s",%(name)s\n%(url)s\n'
    
    # Channel names mapping. You may use this to rename channels. 
    # Examples: 
    # m3uchannelnames[u'Canal+ HD (France)'] = u'Canal+ HD'
    # m3uchannelnames[u'Sky Sport 1 HD (Italy)'] = u'Sky Sport 1 HD'
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
        name = PlaylistConfig.m3uchannelnames.get(item['name'])
        
        if name:
            item['name'] = name
