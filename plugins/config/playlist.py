
# Default playlist format
m3uemptyheader = '#EXTM3U\n'
m3uheader = \
    '#EXTM3U url-tvg="http://1ttvapi.top/ttv.xmltv.xml.gz"\n'
m3uchanneltemplate = \
    '#EXTINF:-1 group-title="%(group)s" tvg-name="%(tvg)s" tvg-id="%(tvgid)s" tvg-logo="%(logo)s",%(name)s\n#EXTGRP:%(group)s\n%(url)s\n'
