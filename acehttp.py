#!/usr/bin/env python2
# -*- coding: utf-8 -*-
'''
AceProxy: Ace Stream to HTTP Proxy

Website: https://github.com/ValdikSS/AceProxy
'''
import traceback
import gevent
import gevent.monkey
from gevent.queue import Full
# Monkeypatching and all the stuff

gevent.monkey.patch_all()
import glob
import os
import signal
import sys
import logging
import psutil
from subprocess import PIPE
import BaseHTTPServer
import SocketServer
from socket import error as SocketException
from socket import SHUT_RDWR
from collections import deque
import base64
import json
import time
import threading
import urllib2
import urlparse
import Queue
import aceclient
import aceconfig
from aceconfig import AceConfig
import vlcclient
import plugins.modules.ipaddr as ipaddr
from aceclient.clientcounter import ClientCounter
from plugins.modules.PluginInterface import AceProxyPlugin
try:
    import pwd
    import grp
except ImportError:
    # Windows
    pass



class HTTPHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    requestlist = []
    
    def handle_one_request(self):
        '''
        Add request to requestlist, handle request and remove from the list
        '''
        HTTPHandler.requestlist.append(self)
        BaseHTTPServer.BaseHTTPRequestHandler.handle_one_request(self)
        HTTPHandler.requestlist.remove(self)

    def closeConnection(self):
        '''
        Disconnecting client
        '''
        if self.connected:
            self.connected = False
            try:
                self.wfile.close()
                self.rfile.close()
                self.connection.shutdown(SHUT_RDWR)
            except:
                pass

    def dieWithError(self, errorcode=500):
        '''
        Close connection with error
        '''
        logging.warning("Dying with error")
        if self.connected:
            self.send_error(errorcode)
            self.end_headers()
            self.closeConnection()

    def proxyReadWrite(self):
        '''
        Read video stream and send it to client
        '''
        logger = logging.getLogger('http_proxyReadWrite')
        logger.debug("Started")

        self.vlcstate = True
        self.streamstate = True

        try:
            while True:
                if AceConfig.videoobey and not AceConfig.vlcuse:
                    # Wait for PlayEvent if videoobey is enabled. Not for VLC
                    self.client.ace.getPlayEvent()

                if AceConfig.videoobey and AceConfig.vlcuse:
                    # For VLC
                    # Waiting 0.5 seconds. If timeout exceeded (and the Play event
                    # flag is not set), pause the stream if AceEngine says so and
                    # we should obey it.
                    # A bit ugly, huh?
                    self.streamstate = self.client.ace.getPlayEvent(0.5)
                    if self.streamstate and not self.vlcstate:
                        AceStuff.vlcclient.playBroadcast(self.vlcid)
                        self.vlcstate = True

                    if not self.streamstate and self.vlcstate:
                        if self.vlcstate:
                            AceStuff.vlcclient.pauseBroadcast(self.vlcid)
                            self.vlcstate = False

                if not self.connected:
                    logger.debug("Client is not connected, terminating")
                    break

                data = self.video.read(4096)
                if data and self.connected:
                    self.wfile.write(data)
                else:
                    logger.warning("Video connection closed")
                    break
        except SocketException:
            # Video connection dropped
            logger.warning("Video connection dropped")
        finally:
            self.video.close()
            self.client.destroy()

    def hangDetector(self):
        '''
        Detect client disconnection while in the middle of something
        or just normal connection close.
        '''
        logger = logging.getLogger('http_hangDetector')
        try:
            while True:
                if not self.rfile.read():
                    break
        except:
            pass
        finally:
            logger.debug("Client disconnected")
            client = self.client
            if client:
                self.client.destroy()
            
            try:
                self.requestgreenlet.kill()
            except:
                pass
            finally:
                gevent.sleep()
            return

    def do_HEAD(self):
        return self.do_GET(headers_only=True)

    def do_GET(self, headers_only=False):
        '''
        GET request handler
        '''
        logger = logging.getLogger('do_GET')
        self.reqtime = time.time()
        self.connected = True
        # Don't wait videodestroydelay if error happened
        self.errorhappened = True
        # Headers sent flag for fake headers UAs
        self.headerssent = False
        # Current greenlet
        self.requestgreenlet = gevent.getcurrent()
        # Connected client IP address
        self.clientip = self.request.getpeername()[0]

        if AceConfig.firewall:
            # If firewall enabled
            self.clientinrange = any(map(lambda i: ipaddr.IPAddress(self.clientip) \
                                in ipaddr.IPNetwork(i), AceConfig.firewallnetranges))

            if (AceConfig.firewallblacklistmode and self.clientinrange) or \
                (not AceConfig.firewallblacklistmode and not self.clientinrange):
                    logger.info('Dropping connection from ' + self.clientip + ' due to ' + \
                                'firewall rules')
                    self.dieWithError(403)  # 403 Forbidden
                    return

        logger.info("Accepted connection from " + self.clientip + " path " + self.path)

        try:
            self.splittedpath = self.path.split('/')
            self.reqtype = self.splittedpath[1].lower()
            # If first parameter is 'pid' or 'torrent' or it should be handled
            # by plugin
            if not (self.reqtype in ('pid', 'torrent') or self.reqtype in AceStuff.pluginshandlers):
                self.dieWithError(400)  # 400 Bad Request
                return
        except IndexError:
            self.dieWithError(400)  # 400 Bad Request
            return

        # Handle request with plugin handler
        if self.reqtype in AceStuff.pluginshandlers:
            try:
                AceStuff.pluginshandlers.get(self.reqtype).handle(self, headers_only)
            except Exception as e:
                logger.error('Plugin exception: ' + repr(e))
                logger.error(traceback.format_exc())
                self.dieWithError()
            finally:
                self.closeConnection()
                return
        self.handleRequest(headers_only)

    def handleRequest(self, headers_only, channelName=None, channelIcon=None, fmt=None):
        logger = logging.getLogger('handleRequest')
        self.requrl = urlparse.urlparse(self.path)
        self.reqparams = urlparse.parse_qs(self.requrl.query)
        self.path = self.requrl.path[:-1] if self.requrl.path.endswith('/') else self.requrl.path
        
        # Check if third parameter exists
        # …/pid/blablablablabla/video.mpg
        #                      |_________|
        # And if it ends with regular video extension
        try:
            if not self.path.endswith(('.3gp', '.avi', '.flv', '.mkv', '.mov', '.mp4', '.mpeg', '.mpg', '.ogv', '.ts')):
                logger.error("Request seems like valid but no valid video extension was provided")
                self.dieWithError(400)
                return
        except IndexError:
            self.dieWithError(400)  # 400 Bad Request
            return

        # Limit concurrent connections
        if 0 < AceConfig.maxconns <= AceStuff.clientcounter.total:
            logger.debug("Maximum connections reached, can't serve this")
            self.dieWithError(503)  # 503 Service Unavailable
            return

        # Pretend to work fine with Fake UAs or HEAD request.
        useragent = self.headers.get('User-Agent')
        fakeua = useragent and useragent in AceConfig.fakeuas
        if headers_only or fakeua:
            if fakeua:
                logger.debug("Got fake UA: " + self.headers.get('User-Agent'))
            # Return 200 and exit
            self.send_response(200)
            self.send_header("Content-Type", "video/mpeg")
            self.end_headers()
            self.closeConnection()
            return

        # Make list with parameters
        self.params = list()
        for i in xrange(3, 8):
            try:
                self.params.append(int(self.splittedpath[i]))
            except (IndexError, ValueError):
                self.params.append('0')
        
        self.url = None
        self.path_unquoted = urllib2.unquote(self.splittedpath[2])
        contentid = self.getCid(self.reqtype, self.path_unquoted)
        cid = contentid if contentid else self.path_unquoted
        logger.debug("CID: " + cid)
        self.client = Client(cid, self, channelName, channelIcon)
        self.vlcid = urllib2.quote(cid, '')
        shouldStart = AceStuff.clientcounter.add(cid, self.client) == 1

        # Send fake headers if this User-Agent is in fakeheaderuas tuple
        if fakeua:
            logger.debug(
                "Sending fake headers for " + useragent)
            self.send_response(200)
            self.send_header("Content-Type", "video/mpeg")
            self.end_headers()
            # Do not send real headers at all
            self.headerssent = True

        try:
            self.hanggreenlet = gevent.spawn(self.hangDetector)
            logger.debug("hangDetector spawned")
            gevent.sleep()

            # Initializing AceClient
            if shouldStart:
                if contentid:
                    self.client.ace.START('PID', {'content_id': contentid})
                elif self.reqtype == 'pid':
                    self.client.ace.START(
                        self.reqtype, {'content_id': self.path_unquoted, 'file_indexes': self.params[0]})
                elif self.reqtype == 'torrent':
                    paramsdict = dict(
                        zip(aceclient.acemessages.AceConst.START_TORRENT, self.params))
                    paramsdict['url'] = self.path_unquoted
                    self.client.ace.START(self.reqtype, paramsdict)
                logger.debug("START done")
                # Getting URL
                self.url = self.client.ace.getUrl(AceConfig.videotimeout)
                # Rewriting host for remote Ace Stream Engine
                self.url = self.url.replace('127.0.0.1', AceConfig.acehost)

            self.errorhappened = False

            if shouldStart:
                logger.debug("Got url " + self.url)
                # If using VLC, add this url to VLC
                if AceConfig.vlcuse:
                    # Force ffmpeg demuxing if set in config
                    if AceConfig.vlcforceffmpeg:
                        self.vlcprefix = 'http/ffmpeg://'
                    else:
                        self.vlcprefix = ''

                    self.client.ace.pause()
                    # Sleeping videodelay
                    gevent.sleep(AceConfig.videodelay)
                    self.client.ace.play()

                    AceStuff.vlcclient.startBroadcast(
                        self.vlcid, self.vlcprefix + self.url, AceConfig.vlcmux, AceConfig.vlcpreaccess)
                    # Sleep a bit, because sometimes VLC doesn't open port in
                    # time
                    gevent.sleep(0.5)

            # Building new VLC url
            if AceConfig.vlcuse:
                self.url = 'http://' + AceConfig.vlchost + \
                    ':' + str(AceConfig.vlcoutport) + '/' + self.vlcid
                logger.debug("VLC url " + self.url)
                
                # Sending client headers to videostream
                self.video = urllib2.Request(self.url)
                for key in self.headers.dict:
                    self.video.add_header(key, self.headers.dict[key])
    
                self.video = urllib2.urlopen(self.video)
    
                # Sending videostream headers to client
                if not self.headerssent:
                    self.send_response(self.video.getcode())
                    if self.video.info().dict.has_key('connection'):
                        del self.video.info().dict['connection']
                    if self.video.info().dict.has_key('server'):
                        del self.video.info().dict['server']
                    if self.video.info().dict.has_key('transfer-encoding'):
                        del self.video.info().dict['transfer-encoding']
                    if self.video.info().dict.has_key('keep-alive'):
                        del self.video.info().dict['keep-alive']
    
                    for key in self.video.info().dict:
                        self.send_header(key, self.video.info().dict[key])
                    # End headers. Next goes video data
                    self.end_headers()
                    logger.debug("Headers sent")
    
                # Run proxyReadWrite
                self.proxyReadWrite()
            else:
                if not fmt:
                    fmt = self.reqparams.get('fmt')[0] if self.reqparams.has_key('fmt') else None
                self.client.handle(shouldStart, self.url, fmt)

        except (aceclient.AceException, vlcclient.VlcException, urllib2.URLError) as e:
            logger.error("Exception: " + repr(e))
            self.errorhappened = True
            self.dieWithError()
        except gevent.GreenletExit:
            # hangDetector told us about client disconnection
            pass
        except Exception:
            # Unknown exception
            logger.error(traceback.format_exc())
            self.errorhappened = True
            self.dieWithError()
        finally:
            if AceConfig.videodestroydelay and not self.errorhappened and AceStuff.clientcounter.count(cid) == 1:
                # If no error happened and we are the only client
                try:
                    logger.debug("Sleeping for " + str(AceConfig.videodestroydelay) + " seconds")
                    gevent.sleep(AceConfig.videodestroydelay)
                except:
                    pass
                
            try:
                remaining = AceStuff.clientcounter.delete(cid, self.client)
                self.client.destroy()
                self.ace = None
                self.client = None
                if AceConfig.vlcuse and remaining == 0:
                    try:
                        AceStuff.vlcclient.stopBroadcast(self.vlcid)
                    except:
                        pass
                logger.debug("END REQUEST")
            except:
                logger.error(traceback.format_exc())
    
    def getCid(self, reqtype, url):
        cid = ''

        if reqtype == 'torrent':
            if url.startswith('http'):
                if url.endswith('.acelive') or  url.endswith('.acestream'):
                    try:
                        req = urllib2.Request(url, headers={'User-Agent' : "Magic Browser"})
                        f = base64.b64encode(urllib2.urlopen(req, timeout=5).read())
                        req = urllib2.Request('http://api.torrentstream.net/upload/raw', f)
                        req.add_header('Content-Type', 'application/octet-stream')
                        cid = json.loads(urllib2.urlopen(req, timeout=3).read())['content_id']                            
                    except:
                        pass
                        
                    if cid == '':
                        logging.debug("Failed to get CID from WEB API")
                        try:
                            with AceStuff.clientcounter.lock:
                                if not AceStuff.clientcounter.idleace:
                                    AceStuff.clientcounter.idleace = AceStuff.clientcounter.createAce()
                                cid = AceStuff.clientcounter.idleace.GETCID(reqtype, url)
                        except:
                            logging.debug("Failed to get CID from engine")
        
        return None if not cid or cid == '' else cid


class HTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    
    def process_request(self, request, client_address):
        checkVlc()
        checkAce()
        SocketServer.ThreadingMixIn.process_request(self, request, client_address)

    def handle_error(self, request, client_address):
        # logging.debug(traceback.format_exc())
        pass


class Client:
    
    def __init__(self, cid, handler, channelName, channelIcon):
        self.cid = cid
        self.handler = handler
        self.channelName = channelName
        self.channelIcon = channelIcon
        self.ace = None
        self.lock = threading.Condition(threading.Lock())
        self.queue = deque()
    
    def handle(self, shouldStart, url, fmt=None):
        logger = logging.getLogger("ClientHandler")
        
        if shouldStart:
            self.ace._streamReaderState = 1
            gevent.spawn(self.ace.startStreamReader, url, self.cid, AceStuff.clientcounter)
            gevent.sleep()
            
        with self.ace._lock:
            start = time.time()
            while self.handler.connected and self.ace._streamReaderState == 1:
                remaining = start + 5.0 - time.time()
                if remaining > 0:
                    self.ace._lock.wait(remaining)
                else:
                    logger.warning("Video stream not opened in 5 seconds - disconnecting")
                    self.handler.dieWithError()
                    return
                
            if self.handler.connected and self.ace._streamReaderState != 2:
                logger.warning("No video stream found")
                self.handler.dieWithError()
                return
            
        if self.handler.connected:
            self.handler.send_response(200)
            self.handler.send_header("Content-Type", "video/mpeg")
            self.handler.end_headers()
        
        if AceConfig.transcode:
            if not fmt or not AceConfig.transcodecmd.has_key(fmt):
                fmt = 'default'
            if AceConfig.transcodecmd.has_key(fmt):
                stderr = None if AceConfig.loglevel == logging.DEBUG else DEVNULL
                transcoder = psutil.Popen(AceConfig.transcodecmd[fmt], bufsize=AceConfig.readchunksize,
                                      stdin=PIPE, stdout=self.handler.wfile, stderr=stderr)
                out = transcoder.stdin
            else:
                transcoder = None
                out = self.handler.wfile
        else:
            transcoder = None
            out = self.handler.wfile
        
        try:
            while self.handler.connected and self.ace._streamReaderState == 2:
                try:
                    data = self.getChunk(60.0)
                    
                    if data and self.handler.connected:
                        try:
                            out.write(data)
                        except:
                            break
                    else:
                        break
                except Queue.Empty:
                    logger.debug("No data received in 60 seconds - disconnecting")
        finally:
            if transcoder:
                transcoder.kill()

    def addChunk(self, chunk, timeout):
        start = time.time()
        with self.lock:
            while(self.handler.connected and (len(self.queue) == AceConfig.readcachesize)):
                remaining = start + timeout + time.time()
                if remaining > 0:
                    self.lock.wait(remaining)
                else:
                    raise Queue.Full
            if self.handler.connected:
                self.queue.append(chunk)
                self.lock.notifyAll()
    
    def getChunk(self, timeout):
        start = time.time()
        with self.lock:
            while(self.handler.connected and (len(self.queue) == 0)):
                remaining = start + timeout - time.time()
                if remaining > 0:
                    self.lock.wait(remaining)
                else:
                    raise Queue.Empty
            if self.handler.connected:
                chunk = self.queue.popleft()
                self.lock.notifyAll()
                return chunk
            else:
                return None
            
    def destroy(self):
        with self.lock:
            self.handler.closeConnection()
            self.lock.notifyAll()
            self.queue.clear()
    
    def __eq__(self, other):
        return self is other

class AceStuff(object):
    '''
    Inter-class interaction class
    '''
# taken from http://stackoverflow.com/questions/2699907/dropping-root-permissions-in-python
def drop_privileges(uid_name, gid_name='nogroup'):

    # Get the uid/gid from the name
    running_uid = pwd.getpwnam(uid_name).pw_uid
    running_uid_home = pwd.getpwnam(uid_name).pw_dir
    running_gid = grp.getgrnam(gid_name).gr_gid

    # Remove group privileges
    os.setgroups([])

    # Try setting the new uid/gid
    os.setgid(running_gid)
    os.setuid(running_uid)

    # Ensure a very conservative umask
    old_umask = os.umask(077)

    if os.getuid() == running_uid and os.getgid() == running_gid:
        # could be useful
        os.environ['HOME'] = running_uid_home
        return True
    return False

logging.basicConfig(
    level=AceConfig.loglevel,
    filename=AceConfig.logfile,
    format=AceConfig.logfmt,
    datefmt=AceConfig.logdatefmt)
logger = logging.getLogger('INIT')

# Loading plugins
# Trying to change dir (would fail in freezed state)
try:
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
except:
    pass
# Creating dict of handlers
AceStuff.pluginshandlers = dict()
# And a list with plugin instances
AceStuff.pluginlist = list()
pluginsmatch = glob.glob('plugins/*_plugin.py')
sys.path.insert(0, 'plugins')
pluginslist = [os.path.splitext(os.path.basename(x))[0] for x in pluginsmatch]
for i in pluginslist:
    plugin = __import__(i)
    plugname = i.split('_')[0].capitalize()
    try:
        plugininstance = getattr(plugin, plugname)(AceConfig, AceStuff)
    except Exception as e:
        logger.error("Cannot load plugin " + plugname + ": " + repr(e))
        continue
    logger.debug('Plugin loaded: ' + plugname)
    for j in plugininstance.handlers:
        AceStuff.pluginshandlers[j] = plugininstance
    AceStuff.pluginlist.append(plugininstance)

# Check whether we can bind to the defined port safely
if AceConfig.osplatform != 'Windows' and os.getuid() != 0 and AceConfig.httpport <= 1024:
    logger.error("Cannot bind to port " + str(AceConfig.httpport) + " without root privileges")
    sys.exit(1)

server = HTTPServer((AceConfig.httphost, AceConfig.httpport), HTTPHandler)
logger = logging.getLogger('HTTP')

# Dropping root privileges if needed
if AceConfig.osplatform != 'Windows' and AceConfig.aceproxyuser and os.getuid() == 0:
    if drop_privileges(AceConfig.aceproxyuser):
        logger.info("Dropped privileges to user " + AceConfig.aceproxyuser)
    else:
        logger.error("Cannot drop privileges to user " + AceConfig.aceproxyuser)
        sys.exit(1)

# Creating ClientCounter
AceStuff.clientcounter = ClientCounter()

if AceConfig.vlcspawn or AceConfig.acespawn or AceConfig.transcode:
    DEVNULL = open(os.devnull, 'wb')

# Spawning procedures
def spawnVLC(cmd, delay=0):
    try:
        if AceConfig.osplatform == 'Windows' and AceConfig.vlcuseaceplayer:
            import _winreg
            import os.path
            reg = _winreg.ConnectRegistry(None, _winreg.HKEY_CURRENT_USER)
            try:
                key = _winreg.OpenKey(reg, 'Software\AceStream')
            except:
                print "Can't find AceStream!"
                sys.exit(1)
            dir = _winreg.QueryValueEx(key, 'InstallDir')
            playerdir = os.path.dirname(dir[0] + '\\player\\')
            cmd[0] = playerdir + '\\' + cmd[0]
        stdout = None if AceConfig.loglevel == logging.DEBUG else DEVNULL
        stderr = None if AceConfig.loglevel == logging.DEBUG else DEVNULL
        AceStuff.vlc = psutil.Popen(cmd, stdout=stdout, stderr=stderr)
        gevent.sleep(delay)
        return True
    except:
        return False

def connectVLC():
    try:
        AceStuff.vlcclient = vlcclient.VlcClient(
            host=AceConfig.vlchost, port=AceConfig.vlcport, password=AceConfig.vlcpass,
            out_port=AceConfig.vlcoutport)
        return True
    except vlcclient.VlcException as e:
        print repr(e)
        return False

def checkVlc():
    if AceConfig.vlcuse and AceConfig.vlcspawn and not isRunning(AceStuff.vlc):
        del AceStuff.vlc
        if spawnVLC(AceStuff.vlcProc, AceConfig.vlcspawntimeout) and connectVLC():
            logger.info("VLC died, respawned it with pid " + str(AceStuff.vlc.pid))
        else:
            logger.error("Cannot spawn VLC!")
            clean_proc()
            sys.exit(1)

def spawnAce(cmd, delay=0):
    if AceConfig.osplatform == 'Windows':
        reg = _winreg.ConnectRegistry(None, _winreg.HKEY_CURRENT_USER)
        try:
            key = _winreg.OpenKey(reg, 'Software\AceStream')
        except:
            print "Can't find acestream!"
            sys.exit(1)
        engine = _winreg.QueryValueEx(key, 'EnginePath')
        AceStuff.acedir = os.path.dirname(engine[0])
        cmd = engine[0].split()
    try:
        AceStuff.ace = psutil.Popen(cmd, stdout=DEVNULL, stderr=DEVNULL)
        gevent.sleep(delay)
        return True
    except:
        return False

def checkAce():
    if AceConfig.acespawn and not isRunning(AceStuff.ace):
        AceStuff.clientcounter.destroyIdle()
        if hasattr(AceStuff, 'ace'):
            del AceStuff.ace
        if spawnAce(AceStuff.aceProc, 1):
            logger.info("Ace Stream died, respawned it with pid " + str(AceStuff.ace.pid))
            if AceConfig.osplatform == 'Windows':
                # Wait some time because ace engine refreshes the acestream.port file only after full loading...
                gevent.sleep(AceConfig.acestartuptimeout)
                detectPort()
        else:
            logger.error("Cannot spawn Ace Stream!")
            clean_proc()
            sys.exit(1)
            
def detectPort():
    try:
        if not isRunning(AceStuff.ace):
            logger.error("Couldn't detect port! Ace Engine is not running?")
            clean_proc()
            sys.exit(1)
    except AttributeError:
        logger.error("Ace Engine is not running!")
        clean_proc()
        sys.exit(1)
    import _winreg
    import os.path
    reg = _winreg.ConnectRegistry(None, _winreg.HKEY_CURRENT_USER)
    try:
        key = _winreg.OpenKey(reg, 'Software\AceStream')
    except:
        print "Can't find AceStream!"
        sys.exit(1)
    engine = _winreg.QueryValueEx(key, 'EnginePath')
    AceStuff.acedir = os.path.dirname(engine[0])
    try:
        AceConfig.aceport = int(open(AceStuff.acedir + '\\acestream.port', 'r').read())
        logger.info("Detected ace port: " + str(AceConfig.aceport))
    except IOError:
        logger.error("Couldn't detect port! acestream.port file doesn't exist?")
        clean_proc()
        sys.exit(1)

def isRunning(process):
    if psutil.version_info[0] >= 2:
        if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
            return True
    else:  # for older versions of psutil
        if process.is_running() and process.status != psutil.STATUS_ZOMBIE:
            return True
    return False

def findProcess(name):
    for proc in psutil.process_iter():
        try:
            pinfo = proc.as_dict(attrs=['pid', 'name'])
            if pinfo['name'] == name:
                return pinfo['pid']
        except psutil.AccessDenied:
            # System process
            pass
        except psutil.NoSuchProcess:
            # Process terminated
            pass
    return None

def clean_proc():
    # Trying to close all spawned processes gracefully
    if AceConfig.vlcspawn and isRunning(AceStuff.vlc):
        AceStuff.vlcclient.destroy()
        gevent.sleep(1)
        if isRunning(AceStuff.vlc):
            # or not :)
            AceStuff.vlc.kill()
    if AceConfig.acespawn and isRunning(AceStuff.ace):
        AceStuff.ace.terminate()
        gevent.sleep(1)
        if isRunning(AceStuff.ace):
            AceStuff.ace.kill()
        # for windows, subprocess.terminate() is just an alias for kill(), so we have to delete the acestream port file manually
        if AceConfig.osplatform == 'Windows' and os.path.isfile(AceStuff.acedir + '\\acestream.port'):
            os.remove(AceStuff.acedir + '\\acestream.port')

# This is what we call to stop the server completely
def shutdown(signum=0, frame=0):
    logger.info("Stopping server...")
    # Closing all client connections
    for connection in server.RequestHandlerClass.requestlist:
        try:
            # Set errorhappened to prevent waiting for videodestroydelay
            connection.errorhappened = True
            connection.closeConnection()
        except:
            logger.warning("Cannot kill a connection!")
    clean_proc()
    server.server_close()
    sys.exit()

def _reloadconfig(signum=None, frame=None):
    '''
    Reload configuration file.
    SIGHUP handler.
    '''
    global AceConfig

    logger = logging.getLogger('reloadconfig')
    reload(aceconfig)
    from aceconfig import AceConfig
    logger.info('Config reloaded')

# setting signal handlers
try:
    gevent.signal(signal.SIGHUP, _reloadconfig)
    gevent.signal(signal.SIGTERM, shutdown)
except AttributeError:
    # not available on Windows
    pass

if AceConfig.vlcuse:
    if AceConfig.osplatform == 'Windows':
        if AceConfig.vlcuseaceplayer:
            name = 'ace_player.exe'
        else:
            name = 'vlc.exe'
    else:
        name = 'vlc'
    if AceConfig.vlcspawn:
        AceStuff.vlcProc = AceConfig.vlccmd.split()
        if spawnVLC(AceStuff.vlcProc, AceConfig.vlcspawntimeout) and connectVLC():
            logger.info("VLC spawned with pid " + str(AceStuff.vlc.pid))
        else:
            logger.error('Cannot spawn or connect to VLC!')
            clean_proc()
            sys.exit(1)
    else:
        if connectVLC():
            vlc_pid = findProcess(name)
            AceStuff.vlc = psutil.Process(vlc_pid)
        else:
            logger.error('Cannot connect to VLC!')
            clean_proc()
            sys.exit(1)

if AceConfig.osplatform == 'Windows':
    name = 'ace_engine.exe'
else:
    name = 'acestreamengine'
ace_pid = findProcess(name)
AceStuff.ace = None
if not ace_pid:
    if AceConfig.acespawn:
        if AceConfig.osplatform == 'Windows':
            import _winreg
            import os.path
            AceStuff.aceProc = ""
        else:
            AceStuff.aceProc = AceConfig.acecmd.split()
        if spawnAce(AceStuff.aceProc, 1):
            # could be redefined internally
            if AceConfig.acespawn:
                logger.info("Ace Stream spawned with pid " + str(AceStuff.ace.pid))
else:
    AceStuff.ace = psutil.Process(ace_pid)

if AceConfig.osplatform == 'Windows':
    # Wait some time because ace engine refreshes the acestream.port file only after full loading...
    gevent.sleep(AceConfig.acestartuptimeout)
    detectPort()
    
try:
    logger.info("Using gevent %s" % gevent.__version__)
    logger.info("Using psutil %s" % psutil.__version__)
    if AceConfig.vlcuse:
         logger.info("Using VLC %s" % AceStuff.vlcclient._vlcver)
    logger.info("Server started.")
    while True:
        server.handle_request()
except (KeyboardInterrupt, SystemExit):
    shutdown()
