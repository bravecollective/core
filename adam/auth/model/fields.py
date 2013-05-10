# encoding: utf-8

from __future__ import unicode_literals

import re

from random import choice
from string import printable
from mongoengine import BinaryField
from mongoengine.base import BaseField
from scrypt import error as scrypt_error, encrypt as scrypt, decrypt as validate_scrypt


class PasswordField(BinaryField):
    def __init__(self, difficulty=1, **kwargs):
        self.difficulty = difficulty
        
        super(PasswordField, self).__init__(**kwargs)
    
    def to_python(self, value):
        return value
    
    def __set__(self, instance, value):
        if instance._initialised:
            if isinstance(value, unicode):
                value = value.encode('utf-8')
            
            salt = b''.join([choice(printable) for i in range(32)])
            value = str(scrypt(salt, value, maxtime=self.difficulty))
        
        return super(PasswordField, self).__set__(instance, value)
    
    def to_mongo(self, value):
        if value is None:
            return value
        
        return super(PasswordField, self).to_mongo(value)
    
    def check(self, source, value):
        try:
            # It may be a tiny bit more difficult for us to validate than it was to generate.
            # Even a few ms too long will give us bad results.
            validate_scrypt(source, value, self.difficulty * 2)
        
        except scrypt_error:
            return False
        
        return True



class IPAddressField(BaseField):
    IPV6_REGEXP = re.compile(r"""
            ^
            \s*                         # Leading whitespace
            (?!.*::.*::)                # Only a single whildcard allowed
            (?:(?!:)|:(?=:))            # Colon iff it would be part of a wildcard
            (?:                         # Repeat 6 times:
                [0-9a-f]{0,4}           #   A group of at most four hexadecimal digits
                (?:(?<=::)|(?<!::):)    #   Colon unless preceeded by wildcard
            ){6}                        #
            (?:                         # Either
                [0-9a-f]{0,4}           #   Another group
                (?:(?<=::)|(?<!::):)    #   Colon unless preceeded by wildcard
                [0-9a-f]{0,4}           #   Last group
                (?: (?<=::)             #   Colon iff preceeded by exacly one colon
                 |  (?<!:)              #
                 |  (?<=:) (?<!::) :    #
                 )                      # OR
             |                          #   A v4 address with NO leading zeros
                (?:25[0-4]|2[0-4]\d|1\d\d|[1-9]?\d)
                (?: \.
                    (?:25[0-4]|2[0-4]\d|1\d\d|[1-9]?\d)
                ){3}
            )
            \s*                         # Trailing whitespace
            $
        """, re.VERBOSE | re.IGNORECASE | re.DOTALL)

    def validate_ipv4_address(self, address):
        addr_parts = address.split(".")
        if len(addr_parts) != 4:
            return False
        for part in addr_parts:
            try:
                if not 0 <= int(part) <= 255:
                    return False
            except ValueError:
                return False
        return True

    def validate_ipv6_address(self,address):
        return IPAddressField.IPV6_REGEXP.match(address) is not None

    def validate(self,value):
        addr_is_valid = self.validate_ipv4_address(value) or self.validate_ipv6_address(value)
        if not addr_is_valid:
            self.error('Invalid IP Address: %s' % value)
