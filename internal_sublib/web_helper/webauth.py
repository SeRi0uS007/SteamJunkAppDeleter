from time import time
from base64 import b64encode
from urllib.parse import urlparse
from binascii import hexlify
from os import urandom as random_bytes
import typing

import aiohttp
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey.RSA import construct as rsa_construct
from Crypto.Hash import SHA1
from steamid import SteamID


# Some code from https://github.com/ValvePython/steam/blob/master/steam/webauth.py
# Adapted for aiohttp
class Web:

    @staticmethod
    def pks1v15_encrypt(key, message):
        return PKCS1_v1_5.new(key).encrypt(message)

    @staticmethod
    def rsa_publickey(mod, exp):
        return rsa_construct((mod, exp))

    def __init__(self, login: str, password: str):
        self.__login = login
        self.__password = password
        self.__session = aiohttp.ClientSession()

        self.logged_on = False
        self.steamid: typing.Optional[SteamID] = None
        self.sessionid: typing.Optional[str] = None
        self.__rsa_key = None
        self.__rsa_timestamp = None
        self.__cookies = {}

    async def __load_key(self):
        if not self.__rsa_key:
            async with self.__session.post('https://steamcommunity.com/login/getrsakey/',
                                           timeout=15,
                                           data={
                                               'username': self.__login,
                                               'donotcache': int(time() * 1000)
                                           }) as response:
                resp = await response.json()
                self.__rsa_key = Web.rsa_publickey(int(resp['publickey_mod'], 16),
                                                   int(resp['publickey_exp'], 16))
                self.__rsa_timestamp = resp['timestamp']

    async def __send_login(self, two_factor: str = '', email_code: str = ''):
        data = {
            'username': self.__login,
            'password': b64encode(Web.pks1v15_encrypt(self.__rsa_key,
                                                      self.__password.encode('ascii'))).decode('ascii'),
            'emailauth': email_code,
            'emailsteamid': '',
            'twofactorcode': two_factor,
            'captchagid': '-1',
            'captcha_text': '',
            'loginfriendlyname': 'steamjunkappdeleter web',
            'rsatimestamp': self.__rsa_timestamp,
            'remember_login': 'false',
            'donotcache': str(int(time() * 100000))
        }

        try:
            async with self.__session.post('https://steamcommunity.com/login/dologin',
                                           data=data, timeout=15) as response:
                return await response.json()
        except aiohttp.ClientError as ex:
            raise HTTPError(str(ex))

    async def login(self, two_factor: str = '', email_code: str = '', language: str = 'english'):
        await self.__load_key()
        resp = await self.__send_login(two_factor, email_code)

        if resp['success'] and resp['login_complete']:
            self.logged_on = True

            for cookie in self.__session.cookie_jar:
                self.__cookies[cookie.key] = cookie.value

            self.__cookies['Steam_Language'] = language
            self.__cookies['birthtime'] = '-3333'
            self.__cookies['sessionid'] = self.sessionid = self.generate_session_id()

            self.steamid = SteamID(resp['transfer_parameters']['steamid'])
        else:
            if resp.get('captcha_needed', False):
                raise CaptchaRequired('please try later')
            elif resp.get('emailauth_needed', False):
                raise EmailCodeRequired('please input code from email')
            elif resp.get('requires_twofactor', False):
                raise TwoFactorCodeRequired('please input two factor code')
            else:
                raise LoginIncorrect(resp['message'])

    async def get(self, url: str) -> str:
        if not self.logged_on:
            raise NotLoggedOn('login required before using this method')

        if not self.is_allowed_domain(url):
            raise NotAllowedDomain('url is not from list of allowed domains')

        async with self.__session.get(url, timeout=15, cookies=self.__cookies) as response:
            return await response.text()

    async def post(self, url: str, data: dict) -> str:
        if not self.logged_on:
            raise NotLoggedOn('login required before using this method')

        if not self.is_allowed_domain(url):
            raise NotAllowedDomain('url is not from list of allowed domains')

        async with self.__session.post(url, data=data, timeout=15, cookies=self.__cookies) as response:
            return await response.text()

    @staticmethod
    def is_allowed_domain(url: str) -> bool:
        parse_result = urlparse(url)
        if parse_result.hostname not in ['help.steampowered.com', 'store.steampowered.com', 'steamcommunity.com']:
            return False
        return True

    @staticmethod
    def generate_session_id():
        return hexlify(Web.sha1_hash(random_bytes(32)))[:32].decode('ascii')

    @staticmethod
    def sha1_hash(data):
        return SHA1.new(data).digest()

    async def free(self):
        await self.__session.close()


class WebAuthException(Exception):
    pass


class HTTPError(WebAuthException):
    pass


class CaptchaRequired(WebAuthException):
    pass


class LoginIncorrect(WebAuthException):
    pass


class EmailCodeRequired(WebAuthException):
    pass


class TwoFactorCodeRequired(WebAuthException):
    pass


class NotLoggedOn(WebAuthException):
    pass


class NotAllowedDomain(WebAuthException):
    pass
