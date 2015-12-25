import os
import uuid
import cPickle as pickle
from threading import local

from django.core.cache import cache
from django.db import connection
from django.conf import settings

from serveradmin.serverdb.models import ServerObjectCache

CACHE_MIN_QS_COUNT = 5
NUM_OBJECTS_FOR_FILECACHE = 50
INVALIDATE_ALL_BARRIER = 100

_cache_info = local()

class QuerysetCacher(object):
    def __init__(
            self, queryset,
            key='qs',
            encoder=pickle,
            pre_store=None,
            post_load=None,
            post_fetch=None,
        ):

        self.queryset = queryset
        self._key = key
        self._encoder = encoder

        identity = lambda x: x
        self._pre_store = pre_store or identity
        self._post_load = post_load or identity
        self._post_fetch = post_fetch or identity
        self._do_cache = False

    def get_results(self):
        was_found, server_data = self._from_cache()
        if not was_found:
            server_data = self.queryset.get_raw_results()
            num_servers = len(server_data)
            server_data = self._post_fetch(server_data)
            self._to_cache(server_data, num_servers)
        return server_data

    def _get_cache_file(self, qs_repr_hash):
        return os.path.join(
                settings.DATASET_CACHE_DIR,
                'cache_{0}.{1}'.format(qs_repr_hash, self._key),
            )

    def _from_cache(self):
        qs_repr = self.queryset.get_representation()
        qs_repr_hash = hash(qs_repr)
        cache_version = _get_cache_version()
        hash_postfix = ':{0}:{1}:{2}'.format(
                self._key,
                qs_repr_hash,
                cache_version,
            )
        cached_qs_repr = cache.get('qs_repr' + hash_postfix)
        if cached_qs_repr and qs_repr == cached_qs_repr:
            cache_storage = cache.get('qs_storage' + hash_postfix)
            if cache_storage == 'cache':
                result = cache.get('qs_result' + hash_postfix)
                if result:
                    result = self._post_load(result)
                    return True, result
            elif cache_storage == 'file':
                try:
                    with open(self._get_cache_file(qs_repr_hash)) as f:
                        result = self._post_load(self._encoder.load(f))
                        return True, result
                except IOError:
                    cache.delete_many([
                            'qs_repr' + hash_postfix,
                            'qs_storage' + hash_postfix,
                        ])
        count_key =  'qs_count' + hash_postfix
        try:
            qs_count = cache.incr(count_key)
        except ValueError:
            # Reset counter after 1 day
            cache.set(count_key, 1, 24 * 3600)
            qs_count = 1

        has_limit = qs_repr.limit or qs_repr.offset
        if qs_count >= CACHE_MIN_QS_COUNT and not has_limit:
            self._do_cache = True
        return False, None

    def _to_cache(self, server_data, num_servers):
        # Only cache it, if it was a query that was requested often
        if not self._do_cache:
            return
        qs_repr = self.queryset.get_representation()
        qs_repr_hash = hash(qs_repr)
        cache_version = _get_cache_version()
        hash_postfix = ':{0}:{1}:{2}'.format(
                self._key,
                qs_repr_hash,
                cache_version,
            )
        cache.set('qs_result' + hash_postfix, server_data)
        if num_servers > NUM_OBJECTS_FOR_FILECACHE:
            storage = 'file'
            with open(self._get_cache_file(qs_repr_hash), 'w') as f:
                self._encoder.dump(server_data, f)
        else:
            storage = 'cache'
        cache.set('qs_repr' + hash_postfix, qs_repr)
        cache.set('qs_storage' + hash_postfix, storage)
        table_name = ServerObjectCache._meta.db_table
        cache_insert_sql = (
                'REPLACE INTO {0} (server_id, repr_hash) VALUES (%s, %s)'
            ).format(table_name)

        # Large querysets are always pruned from cache when data is
        # comitted
        c = connection.cursor()
        if len(server_data) >= NUM_OBJECTS_FOR_FILECACHE:
            c.execute(cache_insert_sql, (None, qs_repr_hash))
        else:
            for server_id in server_data:
                c.execute(cache_insert_sql, (server_id, qs_repr_hash))

def invalidate_cache(server_ids=None):
    c = connection.cursor()
    cache_table = ServerObjectCache._meta.db_table
    if server_ids:
        server_ids = ','.join([str(x) for x in server_ids])

        # Invalidate all cache values if there are too many
        query_count = (
                'SELECT COUNT(*) FROM {0} WHERE server_id IN ({1}) '
                'OR server_id IS NULL'
            )
        c.execute(query_count.format(cache_table, server_ids))
        if c.fetchone()[0] > INVALIDATE_ALL_BARRIER:
            c.execute('TRUNCATE TABLE {0}'.format(cache_table))
            _new_cache_version()
            return

        query_get = (
                'SELECT repr_hash FROM {0} '
                'WHERE server_id IN ({1}) OR server_id IS NULL'
            )
        c.execute(query_get.format(cache_table, server_ids))
        cache_hashes = [x[0] for x in c.fetchall()]
        cache_version = _get_cache_version()
        for prefix in ('qs_repr', 'qs_storage', 'qs_result'):
            for key in ('qs', 'api'):
                cache.delete_many(['{0}:{1}:{2}:{3}'.format(
                        prefix,
                        key,
                        qs_hash,
                        cache_version,
                    ) for qs_hash in cache_hashes])
    else:
        c.execute('TRUNCATE TABLE {0}'.format(cache_table))
        _new_cache_version()
        return

def _get_cache_version():
    version = cache.get(u'dataset_cache_version')
    if not version:
        version = uuid.uuid1().hex
        cache.add(u'dataset_lookups_version', version)
    return version

def _new_cache_version():
    cache.delete(u'dataset_cache_version')
    return _get_cache_version()
