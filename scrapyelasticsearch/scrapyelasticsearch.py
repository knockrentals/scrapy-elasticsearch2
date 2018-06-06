# Copyright 2014 Michael Malocha <michael@knockrentals.com>
#
# Expanded from the work by Julien Duponchelle <julien@duponchelle.info>.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Elastic Search Pipeline for scrapy expanded with support for multiple items"""

from datetime import datetime
from elasticsearch import Elasticsearch, helpers
from six import string_types

import logging
import hashlib
import types
import re


class InvalidSettingsException(Exception):
    pass


class ElasticSearchPipeline(object):
    settings = None
    es = None
    items_buffer = []

    @classmethod
    def validate_settings(cls, settings):
        def validate_setting(setting_key):
            if settings[setting_key] is None:
                raise InvalidSettingsException('%s is not defined in settings.py' % setting_key)

        required_settings = {'ELASTICSEARCH_INDEX', 'ELASTICSEARCH_TYPE'}

        for required_setting in required_settings:
            validate_setting(required_setting)

    @classmethod
    def init_es_client(cls, crawler_settings):
        auth_type = crawler_settings.get('ELASTICSEARCH_AUTH')
        es_timeout = crawler_settings.get('ELASTICSEARCH_TIMEOUT',60)

        es_servers = crawler_settings.get('ELASTICSEARCH_SERVERS', 'localhost:9200')
        es_servers = es_servers if isinstance(es_servers, list) else [es_servers]

        if auth_type == 'NTLM':
            from .transportNTLM import TransportNTLM
            es = Elasticsearch(hosts=es_servers,
                               transport_class=TransportNTLM,
                               ntlm_user= crawler_settings['ELASTICSEARCH_USERNAME'],
                               ntlm_pass= crawler_settings['ELASTICSEARCH_PASSWORD'],
                               timeout=es_timeout)

            return es

        es_settings = dict()
        es_settings['hosts'] = es_servers
        es_settings['timeout'] = es_timeout

        if 'ELASTICSEARCH_USERNAME' in crawler_settings and 'ELASTICSEARCH_PASSWORD' in crawler_settings:
            es_settings['http_auth'] = (crawler_settings['ELASTICSEARCH_USERNAME'], crawler_settings['ELASTICSEARCH_PASSWORD'])

        if 'ELASTICSEARCH_CA' in crawler_settings:
            import certifi
            es_settings['port'] = 443
            es_settings['use_ssl'] = True
            ca = crawler_settings['ELASTICSEARCH_CA']
            if 'CA_CERT' in ca:
                es_settings['ca_certs'] = ca['CA_CERT']
            if 'CLIENT_KEY' in ca:
                es_settings['client_key'] = ca['CLIENT_KEY']
            if 'CLIENT_CERT' in ca:
                es_settings['client_cert'] = ca['CLIENT_CERT']

        es = Elasticsearch(**es_settings)
        return es

    @classmethod
    def from_crawler(cls, crawler):
        ext = cls()
        ext.settings = crawler.settings

        cls.validate_settings(ext.settings)
        ext.es = cls.init_es_client(crawler.settings)
        return ext

    def process_unique_key(self, unique_key):
        if isinstance(unique_key, list):
            unique_key = unique_key[0].encode('utf-8')
        elif isinstance(unique_key, string_types):
            unique_key = unique_key.encode('utf-8')
        else:
            raise Exception('unique key must be str or unicode')

        return unique_key

    def get_id(self, item):
        unique_key = ''.encode('utf-8')
        for key in self.settings['ELASTICSEARCH_UNIQ_KEY'].split():
            item_unique_key = item[key]
            unique_key += self.process_unique_key(item_unique_key)
        item_id = hashlib.sha1(unique_key).hexdigest()
        return item_id

    def get_type(self, item):
        type_name = self.settings['ELASTICSEARCH_TYPE']
        mregex = re.search(r"^%([^\s%]+?)%$", type_name.strip())
        if(mregex):
            type_name = item[mregex.group(1)]
        if type(type_name) is list:
            type_name = '-'.join(type_name)
        return type_name

    def extract_item(self, item):
        dcitems = dict(item)

        for crec in self.settings.get('ELASTICSEARCH_RECORDS', []):
            records = []
            name, fields = crec.split(':')
            for field in fields.split(','):
                if field in dcitems:
                    for idx in range(len(dcitems[field])):
                        record = get_initialized(records, idx, {})
                        record[field] = dcitems[field][idx]
                    del dcitems[field]
            dcitems[name] = records

        return dcitems

    def index_item(self, item):
        index_name = self.settings['ELASTICSEARCH_INDEX']
        index_suffix_format = self.settings.get('ELASTICSEARCH_INDEX_DATE_FORMAT', None)
        index_suffix_key = self.settings.get('ELASTICSEARCH_INDEX_DATE_KEY', None)
        index_suffix_key_format = self.settings.get('ELASTICSEARCH_INDEX_DATE_KEY_FORMAT', None)

        if index_suffix_format:
            if index_suffix_key and index_suffix_key_format:
                dt = datetime.strptime(item[index_suffix_key], index_suffix_key_format)
            else:
                dt = datetime.now()
            index_name += "-" + datetime.strftime(dt,index_suffix_format)
        elif index_suffix_key:
            index_name += "-" + index_suffix_key

        index_action = {
            '_index': index_name,
            '_type': self.get_type(item),
            '_source': self.extract_item(item)
        }

        if self.settings['ELASTICSEARCH_UNIQ_KEY'] is not None:
            item_id = self.get_id(item)
            index_action['_id'] = item_id
            logging.debug('Generated unique key %s' % item_id)

        self.items_buffer.append(index_action)

        if len(self.items_buffer) >= self.settings.get('ELASTICSEARCH_BUFFER_LENGTH', 500):
            self.flush_items()

    def send_items(self):
        helpers.bulk(self.es, self.items_buffer)
    
    def flush_items(self):
        self.send_items()
        del self.items_buffer[:]

    def process_item(self, item, spider):
        if isinstance(item, types.GeneratorType) or isinstance(item, list):
            for each in item:
                self.process_item(each, spider)
        else:
            self.index_item(item)
            logging.debug('Item sent to Elastic Search %s' % self.settings['ELASTICSEARCH_INDEX'])
            return item

    def close_spider(self, spider):
        if len(self.items_buffer):
            self.flush_items()

def get_initialized(l, i, d = None):
    try:
        return l[i]
    except IndexError:
        for _ in range(i-len(l)+1):
            l.append(d)
    return l[i]
