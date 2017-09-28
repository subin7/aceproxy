__author__ = 'miltador'
'''
Torrent-telik.com Playlist Downloader Plugin configuration file
'''
# Proxy settings.
# For example you can install tor browser and add in torrc SOCKSPort 9050
# if you use tor on the same machine with AceProxy -  proxies = { 'https' : 'socks5://127.0.0.1:9050' }
# If your http-proxy need authentification - proxies = {https' : 'https://user:password@ip:port'}
useproxy = False
proxies = {'http' : 'socks5://127.0.0.1:9050',
           'https' : 'socks5://127.0.0.1:9050'}
# Channels urls
url_ttv = 'http://torrent-telik.com/channels/torrent-tv.json'
url_mob_ttv = 'http://torrent-telik.com/channels/mob-torrent-tv.json'
url_allfon = 'http://torrent-telik.com/channels/allfon.json'

# EPG urls & EPG timeshift
tvgurl = 'http://simple-tv.torrent-telik.com/teleprograma'
tvgshift = 0
