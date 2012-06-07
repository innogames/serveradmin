import os
import cPickle as pickle

from django.core.cache import cache
from django.db import connection
from django.conf import settings

from serveradmin.dataset.models import ServerObjectCache

CACHE_MIN_QS_COUNT = 5
NUM_OBJECTS_FOR_FILECACHE = 50

class QuerysetCacher(object):
    def __init__(self, queryset, key='qs', encoder=pickle, pre_store=None,
                 post_load=None, post_fetch=None):
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
            server_data = self._post_fetch(server_data)
            self._to_cache(server_data)
        return server_data
    
    def _get_cache_file(self, qs_repr_hash):
        return os.path.join(settings.DATASET_CACHE_DIR, 'cache_{0}.{1}'.format(
                qs_repr_hash, self._key))
    
    def _from_cache(self):
        qs_repr = self.queryset.get_representation()
        qs_repr_hash = hash(qs_repr)
        hash_postfix = ':{0}:{1}'.format(self._key, qs_repr_hash)
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
                    cache.delete_many(['qs_repr' + hash_postfix,
                                       'qs_storage' + hash_postfix])
        count_key =  'qs_count' + hash_postfix
        try:
            qs_count = cache.incr(count_key)
        except ValueError:
            # Reset counter after 1 day
            cache.set(count_key, 1, 24 * 3600)
            qs_count = 1
        if qs_count >= CACHE_MIN_QS_COUNT:
            self._do_cache = True
        return False, None
    
    def _to_cache(self, server_data):
        # Only cache it, if it was a query that was requested often
        if not self._do_cache:
            return
        qs_repr = self.queryset.get_representation()
        qs_repr_hash = hash(qs_repr)
        hash_postfix = ':{0}:{1}'.format(self._key, qs_repr_hash)
        cache.set('qs_result' + hash_postfix, server_data)
        if len(server_data) > NUM_OBJECTS_FOR_FILECACHE:
            storage = 'file'
            with open(self._get_cache_file(qs_repr_hash), 'w') as f:
                self._encoder.dump(server_data, f)
        else:
            storage = 'cache'
        cache.set('qs_repr' + hash_postfix, qs_repr)
        cache.set('qs_storage' + hash_postfix, storage)
        table_name = ServerObjectCache._meta.db_table
        cache_insert_sql = ('REPLACE INTO {0} (server_id, repr_hash) '
                'VALUES (%s, %s)').format(table_name)
        
        # Large querysets are always pruned from cache when data is
        # comitted
        c = connection.cursor()
        if len(server_data) >= NUM_OBJECTS_FOR_FILECACHE:
            c.execute(cache_insert_sql, (None, qs_repr_hash))
        else:
            for server_id in server_data:
                c.execute(cache_insert_sql, (server_id, qs_repr_hash))
