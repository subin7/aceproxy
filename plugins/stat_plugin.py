'''                                                                                                                                                                                                                
Simple statistics plugin                                                                                                                                                                                           
                                                                                                                                                                                                                   
To use it, go to http://127.0.0.1:8000/stat                                                                                                                                                                        
'''                                                                                                                                                                                                                
from modules.PluginInterface import AceProxyPlugin                                                                                                                                                                 
from subprocess import Popen, PIPE                                                                                                                                                                                 
import re                                                                                                                                                                                                          
import time                                                                                                                                                                                                        
import logging                                                                                                                                                                                                     
import urllib2                                                                                                                                                                                                     
import plugins.modules.ipaddr as ipaddr                                                                                                                                                                            
import locale                                                                                                                                                                                                      
import json                                                                                                                                                                                                        
                                                                                                                                                                                                                   
localnetranges = (                                                                                                                                                                                                 
        '192.168.0.0/16',                                                                                                                                                                                          
        '10.0.0.0/8',                                                                                                                                                                                              
        '172.16.0.0/12',                                                                                                                                                                                           
        '224.0.0.0/4',                                                                                                                                                                                             
        '240.0.0.0/5',                                                                                                                                                                                             
        '127.0.0.0/8',                                                                                                                                                                                             
        )                                                                                                                                                                                                          
                                                                                                                                                                                                                   
class Stat(AceProxyPlugin):                                                                                                                                                                                        
    handlers = ('stat', 'favicon.icon')                                                                                                                                                  
    logger = logging.getLogger('STAT')                                                                                                                                                                             
                                                                                                                                                                                                                   
    def __init__(self, AceConfig, AceStuff):                                                                                                                                                                       
        self.config = AceConfig                                                                                                                                                                                    
        self.stuff = AceStuff                                                                                                                                                                                      
                                                                                                                                                                                                                   
    def geo_ip_lookup(self, ip_address):                                                                                                                                                                           
        lookup_url = 'http://freegeoip.net/json/' + ip_address                                                                                                                                                     
        Stat.logger.debug('Trying to obtain geoip info : ' + lookup_url)                                                                                                                                           
                                                                                                                                                                                                                   
        req = urllib2.Request(lookup_url, headers={'User-Agent' : "Magic Browser"})                                                                                                                                
        response = json.loads(urllib2.urlopen(req, timeout=10).read())                                                                                                                                             
                                                                                                                                                                                                                   
        return {'country_code' : '' if not response['country_code'] else response['country_code'] ,                                                                                                                
                'country'      : '' if not response['country_name'] else response['country_name'] ,                                                                                                                
                'city'         : '' if not response['city'] else response['city']}   

    def mac_lookup(self,ip_address):                                                                                                                                                                               
        Popen(["ping", "-c 1", ip_address], stdout = PIPE, shell=False)                                                                                                                                            
        pid = Popen(["arp", "-n", ip_address], stdout = PIPE, shell=False)                                                                                                                                         
        s = pid.communicate()[0]                                                                                                                                                                                   
        mac_address = re.search(r"(([a-f\d]{1,2}\:){5}[a-f\d]{1,2})", s)                                                                                                                                           
        if mac_address != None:                                                                                                                                                                                    
           mac_address = mac_address.groups()[0]                                                                                                                                                                   
           lookup_url = "http://api.macvendors.com/" + mac_address                                                                                                                                                 
           Stat.logger.debug('Trying to obtain MAC address : ' + lookup_url)                                                                                                                                       
           req = urllib2.Request(lookup_url, headers={'User-Agent' : "Magic Browser"})                                                                                                                             
           response = urllib2.urlopen(req, timeout=10).read()                                                                                                                                                      
        else:                                                                                                                                                                                                      
           Stat.logger.debug("Can't obtain MAC address for Local IP")                                                                                                                                              
           response = ''                                                                                                                                                                                           
        return "Local IP address " if not response else response                                                                                                                                                   
                                                                                                                                                                                                                   
    def handle(self, connection, headers_only=False):                                                                                                                                                              
        current_time = time.time()                                                                                                                                                                                 
                                                                                                                                                                                                                   
        if connection.reqtype == 'favicon.ico':                                                                                                                                                                    
            connection.send_response(404)                                                                                                                                                                          
            return
        connection.wfile.write('<html><head>')
        connection.wfile.write('<meta charset="UTF-8" http-equiv="Refresh" content="60"/>')
        connection.wfile.write('<title>AceProxy stat info</title>')
        connection.wfile.write('<link rel="stylesheet" type="text/css" href="http://cloud.github.com/downloads/lafeber/world-flags-sprite/flags16.css"/>')
        connection.wfile.write('<link rel="shortcut icon" href="http://i.piccy.info/i9/5777461ca749986f6fb4c4b06a70bfbe/1504856430/10417/1177931/SHesterenka_150x150.png" type="image/png">')
        connection.wfile.write('</head>')
        connection.wfile.write('<body><div class="f16"><h4>Connected clients: ' + str(self.stuff.clientcounter.total) + '</h4>')
        connection.wfile.write('<h5>Concurrent connections limit: ' + str(self.config.maxconns) + '</h5><table  border="2" cellspacing="0" cellpadding="3">')
        connection.wfile.write('<tr align=CENTER valign=BASELINE BGCOLOR="#eeeee5"><td>Channel name</td><td>Client IP</td><td>Client/Location</td><td>Start time</td><td>Duration</td></tr>')

        for i in self.stuff.clientcounter.clients:
            for c in self.stuff.clientcounter.clients[i]:
                connection.wfile.write('<tr><td>')
                if c.channelIcon:
                    connection.wfile.write('<img src="' + c.channelIcon + '" width="40" height="16"/>&nbsp;')
                if c.channelName:
                    connection.wfile.write(c.channelName.encode('UTF8'))
                else:
                    connection.wfile.write(i)

                connection.wfile.write('</td><td>' + c.handler.clientip + '</td>')
                clientinrange = any(map(lambda i: ipaddr.IPAddress(c.handler.clientip) in ipaddr.IPNetwork(i),localnetranges))

                if clientinrange:
                    connection.wfile.write('<td>' + self.mac_lookup(c.handler.clientip).encode('UTF8').strip() + '</td>')
                else:
                    geo_ip_info = self.geo_ip_lookup(c.handler.clientip)
                    connection.wfile.write('<td>' + geo_ip_info.get('country').encode('UTF8') + ', ' +                                                                                                             geo_ip_info.get('city').encode('UTF8') + '&nbsp;<i class="flag ' + geo_ip_info.get('country_code').encode('UTF8').lower() + '"></i>&nbsp;</td>')
                connection.wfile.write('<td>' + time.strftime('%c', time.localtime(c.connectionTime)) + '</td>')
                connection.wfile.write('<td align="center">' + time.strftime("%H:%M:%S",  time.gmtime(current_time-c.connectionTime)) + '</td></tr>')
        connection.wfile.write('</table></div></body></html>')        
