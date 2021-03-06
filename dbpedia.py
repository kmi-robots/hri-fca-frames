from SPARQLWrapper import SPARQLWrapper, JSON

class DBPedia(object):

    def __init__(self):
        self.sparql_endpoint = "http://dbpedia.org/sparql"
        self.template = """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            SELECT ?type
            WHERE { <%s> rdf:type ?type }
        """
        self.template_superclass = """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            SELECT ?type
            WHERE { <%s> rdfs:subClassOf ?type }
        """
        self.template_ontology_check = """
            PREFIX dbo: <http://dbpedia.org/ontology/>
            ASK {
                VALUES (?r) { (dbo:%s) }
                    { ?r ?p ?o }
                    UNION
                    { ?s ?r ?o }
                    UNION
                    { ?s ?p ?r }
                }
        """
        self.template_redirect = """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            PREFIX db: <http://dbpedia.org/resource/>
            SELECT ?redirectsTo WHERE {
              ?x rdfs:label "%s"@en .
              ?x dbo:wikiPageRedirects ?redirectsTo
            }
        """
        self.template_hypernym = """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            SELECT ?hypernym
            WHERE { <%s> <http://purl.org/linguistics/gold/hypernym> ?hypernym }
        """

        self.template_disambiguate = """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            SELECT ?other
            WHERE { <%s> dbo:wikiPageDisambiguates ?other . }
        """

    def get_hypernym(self, name, verbose=False):
        """Gets the rdf:type list with the selected filter.
        The filter is a partial string that must be contained in the URI
        'dbpedia.org/ontology/'
        """
        sparql = SPARQLWrapper(self.sparql_endpoint)
        query = self.template_hypernym % name
        if verbose:
            print(query)
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        query_results = sparql.query().convert()
        types = []
        if verbose:
            print(query_results)
        for result in query_results["results"]["bindings"]:
            uri = result['hypernym']['value']
            types.append(uri)
        #print(name, types)
        return set(types)
    
    def get_types(self, name, verbose=False):
        """Gets the rdf:type or rdfs:subClassOf list with the selected filter.
        The filter is a partial string that must be contained in the URI
        'dbpedia.org/ontology/'
        """
        sparql = SPARQLWrapper(self.sparql_endpoint)
        if 'dbpedia.org/ontology/' in name:
            query = self.template_superclass % name
        else:
            query = self.template % name
        if verbose:
            print(query)
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        query_results = sparql.query().convert()
        types = []
        if verbose:
            print(query_results)
        for result in query_results["results"]["bindings"]:
            uri = result['type']['value']
            if 'dbpedia.org/ontology/' in uri or 'dbpedia.org/resource' in uri:
                # take the last part of URI
                #last_part = '/'.join(uri.split('/')[-2:])
                types.append(uri)
        #print(name, types)
        return set(types)

    def get_disambiguate(self, name, verbose=False):
        sparql = SPARQLWrapper(self.sparql_endpoint)
        query = self.template_disambiguate % name
        if verbose:
            print(query)
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        query_results = sparql.query().convert()
        others = []
        if verbose:
            print(query_results)
        for result in query_results["results"]["bindings"]:
            other = result['other']['value']
            others.append(other)

        return set(others)

    def get_all_types(self, name, verbose=False, disambiguate=False):
        """Returns all the Hypernims and types
        if disambiguate is True, also picks the first disambiguation if the search is stopping without types and hypernims"""
        #results = defaultdict(lambda: False)
        edges = set()
        all_results = {}
        # 1 get first level hp
        types = self.get_types(name, verbose)
        hypernyms = self.get_hypernym(name, verbose)
        first = types.union(hypernyms)
        for t in types:
            edge_type = 'rdfs:subClassOf' if ('dbpedia.org/ontology/' in name) else 'rdf:type'
            edges.add((name, t, edge_type))
        for h in hypernyms:
            edges.add((name, h, 'hypernym'))
        if not first and disambiguate:
            first = self.get_disambiguate(name, verbose)
            for d in first:
                edges.add((name, d, 'disambiguated_by'))
        for h in first:
            all_results[h] = False
        #print('%%')
        # 2 while exist results not explored, find their hyperonims and add to the results (marked as not explored)
        while any(not v for k,v in all_results.items()):
            not_explored = [k for k,v in all_results.items() if not v]
            #print('not explored ',len(not_explored), '/', len(results.keys()), '\r', end='')
            # explore one and update flags
            selected = not_explored[0]
            # TODO find a way to reduce candidates, maybe use 'source' param to restrict the field?
            if verbose:
                print('selected', selected)
            types = self.get_types(selected, verbose)
            hypernyms = self.get_hypernym(selected, verbose)
            discovered = types.union(hypernyms)
            for t in types:
                edge_type = 'rdfs:subClassOf' if ('dbpedia.org/ontology/' in selected) else 'rdf:type'
                edges.add((selected, t, edge_type))
            for h in hypernyms:
                edges.add((selected, h, 'hypernym'))
            if not discovered and disambiguate:
                discovered = self.get_disambiguate(selected, verbose)
                for d in discovered:
                    edges.add((selected, d, 'disambiguated_by'))
            for h in discovered:
                if not h in all_results.keys():
                    all_results[h] = False
            all_results[selected] = True
        
        return set(all_results.keys()), set(edges)

    def get_id(self, name):
        #return name.replace(' ', '_').capitalize()
        truecased_name = name.capitalize()
        sparql = SPARQLWrapper(self.sparql_endpoint)
        query = self.template_redirect % truecased_name
        #print(query)
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()
        #print(results)

        bindings = results['results']['bindings']
        if bindings:
            uri = bindings[0]['redirectsTo']['value']
            #new_name = '/'.join(uri.split('/')[-2:-1])
            return uri
            #return new_name
        else:
            # check if exists in ontology
            sparql = SPARQLWrapper(self.sparql_endpoint)
            query = self.template_ontology_check % truecased_name
            sparql.setQuery(query)
            sparql.setReturnFormat(JSON)
            results = sparql.query().convert()
            if results['boolean']:
                area = 'ontology'
            else:
                # otherwise go to resource
                area = 'resource'
            return 'http://dbpedia.org/{}/{}'.format(area, truecased_name)

    def get_name(self, uri):
        return uri.split('/')[-1]

        

def main():
    dbpedia = DBPedia()
    dbpedia.get_types('Book')
    dbpedia.get_types('Mug')
    dbpedia.get_types('Coffee')
    dbpedia.get_types('Kitchen')
    dbpedia.get_types('Building')

if __name__ == '__main__':
    main()
