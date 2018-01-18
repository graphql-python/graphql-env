from graphql import print_schema

from .base import GraphQLBackend
from .compiled import GraphQLCompiledDocument

from .._compat import urlparse

GRAPHQL_QUERY = '''
mutation($schemaDsl: String!, $query: String!) {
  generateCode(
    schemaDsl: $schemaDsl
    query: $query,
    language: PYTHON,
    pythonOptions: {
      asyncFramework: PROMISE
    }
  ) {
    code
    compilationTime
    errors {
      type
    }
  }
}
'''


class GraphQLQuiverCloudBackend(GraphQLBackend):
    def __init__(self, dsn, python_options=None, **options):
        super(GraphQLQuiverCloudBackend, self).__init__(**options)
        try:
            url = urlparse(dsn.strip())
        except:
            raise Exception("Received wrong url {}".format(dsn))

        netloc = url.hostname
        if url.port:
            netloc += ':%s' % url.port

        path_bits = url.path.rsplit('/', 1)
        if len(path_bits) > 1:
            path = path_bits[0]
        else:
            path = ''

        self.api_url = '%s://%s%s' % (url.scheme.rsplit('+', 1)[-1], netloc,
                                      path)
        self.public_key = url.username
        self.secret_key = url.password
        self.python_options = python_options

    def make_post_request(self, url, auth, json_payload):
        '''This function executes the request with the provided
        json payload and return the json response'''
        import requests
        response = requests.post(url, auth=auth, json=json_payload)
        return response.json()

    def generate_source(self, schema, query):
        variables = {'schemaDsl': print_schema(schema), 'query': query}

        json_response = self.make_post_request(
            "{}/graphql".format(self.api_url),
            auth=(self.public_key, self.secret_key),
            json_payload={'query': GRAPHQL_QUERY,
                          'variables': variables})

        data = json_response.get('data', {})
        code_generation = data.get('generateCode', {})
        code = code_generation.get('code')
        if not code:
            raise Exception(
                "Cant get the code. Received json from Quiver Cloud")
        code = str(code)
        return code

    def document_from_string(self, environment, request_string):
        schema = environment.schema
        source = self.generate_source(schema, request_string)
        filename = '<document>'
        code = compile(source, filename, 'exec')
        uptodate = lambda: True
        document = GraphQLCompiledDocument.from_code(schema, code, uptodate)
        return document
