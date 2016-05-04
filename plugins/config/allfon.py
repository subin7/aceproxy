'''
Allfon.tv Playlist Downloader Plugin configuration file
'''

# Insert your allfon.tv playlist URL here
url = 'http://allfon.org/autogenplaylist/allfontv.m3u'

# EPG urls & EPG timeshift
tvgurl = 'http://www.teleguide.info/download/new3/jtv.zip'
tvgshift = 0

# Channel template
m3uchanneltemplate = '#EXTINF:-1 tvg-name="%(tvg)s",%(name)s\n%(url)s\n' 