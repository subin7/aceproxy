# coding=utf-8
"""
Torrent-TV API communication class
Forms requests to API, checks result for errors and returns in desired form (lists or raw data)
"""
from unittest.signals import _results
__author__ = 'miltador'

import urllib2
import socket
import random
import xml.dom.minidom as dom
import logging
import time

class TorrentTvApiException(Exception):
    """
    Exception from Torrent-TV API
    """
    pass


class TorrentTvApi(object):
    CATEGORIES = {
        1: 'Детские',
        2: 'Музыка',
        3: 'Фильмы',
        4: 'Спорт',
        5: 'Общие',
        6: 'Познавательные',
        7: 'Новостные',
        8: 'Развлекательные',
        9: 'Для взрослых',
        10: 'Мужские',
        11: 'Региональные',
        12: 'Религиозные'
    }
    
    session = None
    sessionMaxIdle = 600
    sessionLastActive = 0.0
    sessionEmail = None
    sessionPassword = None

    @staticmethod
    def auth(email, password, raw=False):
        """
        User authentication
        Returns user session that can be used for API requests

        :param email: user email string
        :param password: user password string
        :param raw: if True returns unprocessed data
        :return: unique session string
        """
        session = TorrentTvApi.session
        sessionLastActive = TorrentTvApi.sessionLastActive
        if session and (time.time() - sessionLastActive) < TorrentTvApi.sessionMaxIdle:
            TorrentTvApi.sessionLastActive = time.time()
            logging.debug("Reusing previous session: " + session)
            return session
        
        logging.debug("Creating new session")
        TorrentTvApi.session = None
        xmlresult = TorrentTvApi._result(
             'v3/auth.php?username=' + email + '&password=' + password + '&application=tsproxy&guid=' + str(random.randint(100000000,199999999)))
        if raw:
            return xmlresult
        res = TorrentTvApi._check(xmlresult)
        session = res.getElementsByTagName('session')[0].firstChild.data
        TorrentTvApi.session = session
        TorrentTvApi.sessionEmail = email
        TorrentTvApi.sessionPassword - password
        TorrentTvApi.sessionLastActive = time.time()
        logging.debug("New session created: " + session)
        return session

    @staticmethod
    def translations(session, translation_type, raw=False):
        """
        Gets list of translations
        Translations are basically TV channels

        :param session: valid user session required
        :param translation_type: playlist type, valid values: all|channel|moderation|translation|favourite
        :param raw: if True returns unprocessed data
        :return: translations list
        """
        
        if raw:
            try:
                xmlresult = TorrentTvApi._result(
                                'v3/translation_list.php?session=' + session + '&type=' + translation_type)
                TorrentTvApi._check(xmlresult)
                return xmlresult
            except TorrentTvApiException:
                TorrentTvApi._resetSession()
                xmlresult = TorrentTvApi._result(
                                'v3/translation_list.php?session=' + session + '&type=' + translation_type)
                TorrentTvApi._check(xmlresult)
                return xmlresult
            
        res = TorrentTvApi._checkedresult(
            'v3/translation_list.php?session=' + session + '&type=' + translation_type)
        translationslist = res.getElementsByTagName('channel')
        return translationslist

    @staticmethod
    def records(session, channel_id, date, raw=False):
        """
        Gets list of available record for given channel and date

        :param session: valid user session required
        :param channel_id: id of channel in channel list
        :param date: format %d-%m-%Y
        :param raw: if True returns unprocessed data
        :return: records list
        """
        
        if raw:
            try:
                xmlresult = TorrentTvApi._result(
                                'v3/arc_records.php?session=' + session + '&channel_id=' + channel_id + '&date=' + date)
                TorrentTvApi._check(xmlresult)
                return xmlresult
            except TorrentTvApiException:
                TorrentTvApi._resetSession()
                xmlresult = TorrentTvApi._result(
                                'v3/arc_records.php?session=' + session + '&channel_id=' + channel_id + '&date=' + date)
                TorrentTvApi._check(xmlresult)
                return xmlresult
            
        res = TorrentTvApi._checkedresult(
            'v3/arc_records.php?session=' + session + '&channel_id=' + channel_id + '&date=' + date)
        recordslist = res.getElementsByTagName('channel')
        return recordslist

    @staticmethod
    def archive_channels(session, raw=False):
        """
        Gets the channels list for archive

        :param session: valid user session required
        :param raw: if True returns unprocessed data
        :return: archive channels list
        """
        if raw:
            try:
                xmlresult = TorrentTvApi._result('v3/arc_list.php?session=' + session)
                TorrentTvApi._check(xmlresult)
                return xmlresult
            except TorrentTvApiException:
                TorrentTvApi._resetSession()
                xmlresult = TorrentTvApi._result('v3/arc_list.php?session=' + session)
                TorrentTvApi._check(xmlresult)
                return xmlresult

        res = TorrentTvApi._checkedresult('v3/arc_list.php?session=' + session)
        archive_channelslist = res.getElementsByTagName('channel')
        return archive_channelslist

    @staticmethod
    def stream_source(session, channel_id):
        """
        Gets the source for Ace Stream by channel id

        :param session: valid user session required
        :param channel_id: id of channel in translations list (see translations() method)
        :return: type of stream and source
        """
        res = TorrentTvApi._checkedresult(
            'v3/translation_stream.php?session=' + session + '&channel_id=' + channel_id)
        stream_type = res.getElementsByTagName('type')[0].firstChild.data
        source = res.getElementsByTagName('source')[0].firstChild.data
        return stream_type.encode('utf-8'), source.encode('utf-8')

    @staticmethod
    def archive_stream_source(session, record_id):
        """
        Gets stream source for archive record

        :param session: valid user session required
        :param record_id: id of record in records list (see records() method)
        :return: type of stream and source
        """
        res = TorrentTvApi._checkedresult(
            'v3/arc_stream.php?session=' + session + '&record_id=' + record_id)
        stream_type = res.getElementsByTagName('type')[0].firstChild.data
        source = res.getElementsByTagName('source')[0].firstChild.data
        return stream_type.encode('utf-8'), source.encode('utf-8')

    @staticmethod
    def _check(xmlresult):
        """
        Validates received API answer
        Raises an exception if error detected

        :param xmlresult: API answer to check
        :return: minidom-parsed xmlresult
        :raise: TorrentTvApiException
        """
        res = dom.parseString(xmlresult).documentElement
        success = res.getElementsByTagName('success')[0].firstChild.data
        if success == '0' or not success:
            error = res.getElementsByTagName('error')[0].firstChild.data
            raise TorrentTvApiException('API returned error: ' + error)
        return res

    @staticmethod
    def _checkedresult(request):
        try:
            return TorrentTvApi._check(TorrentTvApi._result(request))
        except TorrentTvApiException:
            TorrentTvApi._resetSession()
            return TorrentTvApi._check(TorrentTvApi._result(request))

    @staticmethod
    def _result(request):
        """
        Sends request to API and returns the result in form of string

        :param request: API command string
        :return: result of request to API
        :raise: TorrentTvApiException
        """
        try:
            result = urllib2.urlopen('http://1ttvapi.top/' + request + '&typeresult=xml', timeout=10).read()
            return result
        except (urllib2.URLError, socket.timeout) as e:
            raise TorrentTvApiException('Error happened while trying to access API: ' + repr(e))

    @staticmethod
    def _resetSession():
        TorrentTvApi.session = None
        TorrentTvApi.auth(TorrentTvApi.sessionEmail, TorrentTvApi.sessionPassword)
