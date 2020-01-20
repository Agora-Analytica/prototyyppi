"""
WikiData
~~~~~~~~

Fetch data from wikidata.

..usage::
    $ wikidata.py parties
    $ wikidata.py politicians

"""

from json import dumps as jsonify
from qwikidata.sparql import (
    return_sparql_query_results
)

# TODO: Removes dead politicians, but should query dead after (P570) or not dead
QUERY_POLITICIANS = """
    SELECT ?item ?itemLabel ?itemAltLabel ?image
           ?member_of_political_partyLabel ?date_of_birth
    WHERE {
        ?item wdt:P31 wd:Q5;        # instanceof human
              wdt:P106 wd:Q82955;   # occupation politician
              wdt:P27 wd:Q33.       # citizenship Finaland
        OPTIONAL { ?item wdt:P18 ?image. }
        FILTER(NOT EXISTS { ?item wdt:P570 _:b21. })
        OPTIONAL { ?item wdt:P102 ?member_of_political_party. }
        OPTIONAL { ?item wdt:P569 ?date_of_birth. }
        SERVICE wikibase:label { bd:serviceParam wikibase:language "fi,[AUTO_LANGUAGE]". }
    }
"""

QUERY_PARTIES = """
    SELECT ?item ?itemLabel ?itemAltLabel ?official_name
           ?logo_image ?sRGB_color_hex_triplet ?short_name ?official_website
    WHERE {
        ?item wdt:P31/wdt:P279* wd:Q7278;   # Instanceof or subclass of politician
              wdt:P17 wd:Q33.               # Country Finland
        OPTIONAL { ?item wdt:P1448 ?official_name. }
        OPTIONAL { ?item wdt:P154 ?logo_image. }
        OPTIONAL { ?item wdt:P465 ?sRGB_color_hex_triplet. }
        OPTIONAL { ?item wdt:P1813 ?short_name. }
        OPTIONAL { ?item wdt:P856 ?official_website. }
        SERVICE wikibase:label { bd:serviceParam wikibase:language "fi,[AUTO_LANGUAGE]". }
    }
"""


class WDList(list):
    def __init__(self, iterable):
        if type(iterable) == dict:
            iterable = list(iterable.values())

        super().__init__(iterable)

    def party(self, value, default=None):
        party = default
        try:
            party = next( x for x in self if value in x['itemLabel'] or value in x.get('itemAltLabel', []))
        except StopIteration:
            pass
        return party



def wikidata_query(query):
    """ Perform sparql query """
    data = {}

    res = return_sparql_query_results(query)

    for e in res['results']['bindings']:
        # Format results into a more json-ish format.
        id = e['item']['value']
        data.setdefault(id, {})
        for i in e:
            if i == "item":
                continue

            data[id].setdefault(i, list())
            v = [e[i]['value']]

            if i == "itemAltLabel":
                # comma separated list. Split it into a list.
                v = e[i]['value'].split(", ")

            [data[id][i].append(x) for x in v if x not in data[id][i]]

    return data


def finnish_parties() -> WDList:
    d = wikidata_query(QUERY_PARTIES)
    return WDList(d)


def finnish_politicians():
    d = wikidata_query(QUERY_POLITICIANS)
    return WDList(d)


if __name__ == "__main__":

    import sys
    command = sys.argv[1]
    data = []

    # Accepted commands
    if command == "parties":
        data = list(finnish_parties().values())
    elif command == "politicians":
        data = list(finnish_politicians().values())

    print(jsonify(data, indent=True, ensure_ascii=False))
