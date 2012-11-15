#!/usr/bin/python

"""
Small web application to retrieve genes from the tomato genome
annotation involved to a specified pathways.

"""

import flask
from flaskext.wtf import Form, TextField

import ConfigParser
import datetime
import json
import os
import rdflib
import urllib


CONFIG = ConfigParser.ConfigParser()
CONFIG.readfp(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
    'path2gene.cfg')))
# Address of the sparql server to query.
SERVER = CONFIG.get('path2gene', 'sparql_server')

# Create the application.
APP = flask.Flask(__name__)
APP.secret_key = CONFIG.get('path2gene', 'secret_key')


# Stores in which graphs are the different source of information.
GRAPHS = {option: CONFIG.get('graph', option) for option in CONFIG.options('graph')}


class PathwayForm(Form):
    """ Simple text field form to input the pathway of interest.
    """
    pathway_name = TextField('Pathway name (or part of it)')


def search_pathway_in_db(name):
    """ Search the uniprot database for pathways having the given string
    in their name. It returns a list of these pathways.

    @param name, a string, name or part of the name of the pathway to
        search in uniprot.
    @return, a list of the pathway names found for having the given
        string.
    """
    query = '''
    PREFIX gene:<http://pbr.wur.nl/GENE#> 
    PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#> 
    PREFIX uniprot:<http://purl.uniprot.org/core/> 
    SELECT DISTINCT ?pathdesc 
    FROM <%(uniprot)s> 
    WHERE{  
        ?prot uniprot:annotation ?annot . 
        ?annot rdfs:seeAlso ?url . 
        ?annot rdfs:comment ?pathdesc . 
        FILTER (
            regex(?pathdesc, "%(search)s", "i")
        )
    } ORDER BY ASC(?pathdesc)
    ''' % {'search': name, 'uniprot': GRAPHS['uniprot']}
    data_js = sparql_query(query, SERVER)
    if not data_js:
        return
    pathways = []
    for entry in data_js['results']['bindings']:
        pathways.append(entry['pathdesc']['value'])
    return pathways


def get_gene_of_pathway(pathway):
    """ Retrieve all the gene associated with pathways containing the
    given string.

    @param name, a string, name of the pathway for which to retrieve the
        genes in the tomato genome annotation.
    @return, a hash of the genes name and description found to be
        associated with the specified pathway.
    """
    query = '''
    PREFIX gene:<http://pbr.wur.nl/GENE#> 
    PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#> 
    PREFIX uniprot:<http://purl.uniprot.org/core/> 
    SELECT DISTINCT ?gene ?desc ?pathdesc
    FROM <%(itag)s> 
    FROM <%(uniprot)s> 
    WHERE{  
        ?geneobj gene:Protein ?prot . 
        ?geneobj gene:Description ?desc . 
        ?geneobj gene:FeatureName ?gene . 
        ?prot uniprot:annotation ?annot . 
        ?annot rdfs:seeAlso ?url . 
        ?annot rdfs:comment ?pathdesc . 
        FILTER (
          regex(?pathdesc, "%(search)s", "i")
        )
    } ORDER BY ASC(?gene)
    ''' % {'search': pathway, 'uniprot': GRAPHS['uniprot'],
        'itag': GRAPHS['itag']}
    data_js = sparql_query(query, SERVER)
    if not data_js:
        return
    genes = {}
    for entry in data_js['results']['bindings']:
        genes[entry['gene']['value']] = [entry['desc']['value'],
            entry['pathdesc']['value']]
    return genes


def get_gene_of_pathway_strict(pathway):
    """ Retrieve all the gene associated with the given pathway.

    @param name, a string, name of the pathway for which to retrieve the
        genes in the tomato genome annotation.
    @return, a hash of the genes name and description found to be
        associated with the specified pathway.
    """
    query = '''
    PREFIX gene:<http://pbr.wur.nl/GENE#> 
    PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#> 
    PREFIX uniprot:<http://purl.uniprot.org/core/> 
    SELECT DISTINCT ?gene ?desc
    FROM <%(itag)s> 
    FROM <%(uniprot)s> 
    WHERE{  
        ?geneobj gene:Protein ?prot . 
        ?geneobj gene:Description ?desc . 
        ?geneobj gene:FeatureName ?gene . 
        ?prot uniprot:annotation ?annot . 
        ?annot rdfs:seeAlso ?url . 
        ?annot rdfs:comment "%(search)s" . 
    } ORDER BY ASC(?gene)
    ''' % {'search': pathway, 'uniprot': GRAPHS['uniprot'],
        'itag': GRAPHS['itag']}
    data_js = sparql_query(query, SERVER)
    if not data_js:
        return
    genes = {}
    for entry in data_js['results']['bindings']:
        genes[entry['gene']['value']] = [entry['desc']['value'],
            pathway]
    return genes


def sparql_query(query, server, output_format='application/json'):
    """ Runs the given SPARQL query against the desired sparql endpoint
    and return the output in the format asked (default being rdf/xml).

    @param query, the string of the sparql query that should be ran.
    @param server, a string, the url of the sparql endpoint that we want
    to run query against.
    @param format, specifies in which format we want to have the output.
    Defaults to `application/json` but can also be `application/rdf+xml`.
    @return, a JSON object, representing the output of the provided
    sparql query.
    """
    params = {
        'default-graph': '',
        'should-sponge': 'soft',
        'query': query,
        'debug': 'off',
        'timeout': '',
        'format': output_format,
        'save': 'display',
        'fname': ''
    }
    querypart = urllib.urlencode(params)
    response = urllib.urlopen(server, querypart).read()
    try:
        output = json.loads(response)
    except ValueError:
        output = {}
    return output


##  Web-app


@APP.route('/', methods=['GET', 'POST'])
def index():
    """ Shows the front page.
    All the content of this page is in the index.html file under the
    templates directory. The file is full html and has no templating
    logic within.
    """
    print 'path2gene %s -- %s -- %s' % (datetime.datetime.now(),
        flask.request.remote_addr, flask.request.url)
    form = PathwayForm(csrf_enabled=False)
    if form.validate_on_submit():
        return flask.redirect(flask.url_for('search_pathway',
                name=form.pathway_name.data))
    return flask.render_template('index.html', form=form)


@APP.route('/search/<name>')
def search_pathway(name):
    """ Search the database for pathways containing the given string.
    """
    print 'path2gene %s -- %s -- %s' % (datetime.datetime.now(),
        flask.request.remote_addr, flask.request.url)
    pathways = search_pathway_in_db(name)
    core = []
    for path in pathways:
        core.append('%s*' % path.split(';')[0].strip())
    core = list(set(core))
    return flask.render_template('search.html', data=pathways,
        search=name, core=core)


@APP.route('/path/<path:pathway>')
def pathway(pathway):
    """ Show for the given pathways all the genes found to be related.
    """
    print 'path2gene %s -- %s -- %s' % (datetime.datetime.now(),
        flask.request.remote_addr, flask.request.url)
    if pathway.endswith('*'):
        genes = get_gene_of_pathway(pathway[:-1])
    else:
        genes = get_gene_of_pathway_strict(pathway)
    geneids = genes.keys()
    geneids.sort()
    return flask.render_template('output.html', pathway=pathway,
        genes=genes, geneids=geneids)


@APP.route('/csv/<path:pathway>')
def generate_csv(pathway):
    """ Generate a comma separated value file containing all the
    information.
    """
    print 'path2gene %s -- %s -- %s' % (datetime.datetime.now(),
        flask.request.remote_addr, flask.request.url)
    # Regenerate the informations
    if pathway.endswith('*'):
        genes = get_gene_of_pathway(pathway[:-1])
    else:
        genes = get_gene_of_pathway_strict(pathway)

    string = 'Gene ID, Gene description, Pathway\n'
    for gene in genes:
        string = string + "%s, %s, %s\n" % (gene, genes[gene][0],
            genes[gene][1])
    return flask.Response(string, mimetype='application/excel')


if __name__ == '__main__':
    APP.debug = True
    APP.run()
