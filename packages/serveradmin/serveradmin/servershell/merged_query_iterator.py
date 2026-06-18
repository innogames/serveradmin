class MergedQuery:
    """
    Holds an arbitrary amount of serveradmin queries that can be used as
    a single iteratable object.
    """
    queries = []

    def __init__(self, queries):
        self.queries = queries

    def __iter__(self):
        return MergedQueryIterator(self.queries)


class MergedQueryIterator:
    """
    Iterates over each query to retrieve the server's data.
    Avoids duplicate items by saving already iterated server-ids.
    """
    served_ids = []
    queries = []
    current_query = 0

    def __init__(self, queries):
        self.queries = [iter(i) for i in queries]
        self.served_ids = []

    def next(self):
        try:
            if len(self.queries) > self.current_query:
                return self.queries[self.current_query].__next__()
        except StopIteration:
            self.current_query += 1

            return self.next()

        raise StopIteration()

    def __next__(self):
        value = self.next()

        while value.object_id in self.served_ids:
            value = self.next()

        self.served_ids.append(value.object_id)

        return value
