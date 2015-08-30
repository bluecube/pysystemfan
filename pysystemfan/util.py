import itertools

class ConcatenatedLists:
    def __init__(self, *lists):
        self._lists = lists

    def __len__(self):
        return sum(len(l) for l in self._lists)

    def __iter__(self):
        return itertools.chain.from_iterable(self._lists)
