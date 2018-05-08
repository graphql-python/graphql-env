from __future__ import absolute_import

import json
import six
from graphql.execution import ExecutionResult
from flask import jsonify, request
from flask.views import View

from .graphiql import render_graphiql
from .exceptions import GraphQLHTTPError, InvalidJSONError, HTTPMethodNotAllowed
from .utils import (
    params_from_http_request,
    execution_result_to_dict,
    ALL_OPERATIONS,
    QUERY_OPERATION,
    format_error
)
from graphql_env import GraphQLEnvironment, GraphQLCoreBackend


class GraphQLView(View):
    schema = None
    executor = None
    root_value = None
    env = None
    graphiql = False
    graphiql_version = None
    format_error = staticmethod(format_error)
    graphiql_template = None
    graphiql_html_title = None
    middleware = None
    store = None
    execute_args = None
    batch = False

    methods = ['GET', 'POST', 'PUT', 'DELETE']

    def __init__(self, **kwargs):
        super(GraphQLView, self).__init__()
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        if self.batch:
            raise Exception("GraphQLView batch is no longer supported.")

        if self.env:
            assert not self.schema, (
                'Cant set env and schema at the same time. Please use GraphQLEnv(schema=...)'
            )
            assert not self.store, (
                'Cant set env and store at the same time. Please use GraphQLEnv(store=...)'
            )
            assert not self.store, (
                'Cant set env and backend at the same time. Please use GraphQLEnv(backend=...)'
            )
        else:
            self.backend = self.backend or GraphQLCoreBackend()
            assert isinstance(self.schema, GraphQLSchema), 'A Schema is required to be provided to GraphQLView.'
            self.env = GraphQLEnvironment(
                self.schema,
                backend=self.backend,
                store=self.store
            )

        self.execute_args = self.execute_args or {}

        if self.executor:
            self.execute_args['executor'] = self.executor
            
    def get_root_value(self):
        return self.root_value

    def get_context(self):
        return request

    def get_middleware(self):
        return self.middleware

    def get_executor(self):
        return self.executor

    def execute(self, *args, **kwargs):
        if self.execute_args:
            kwargs = dict(kwargs, **self.execute_args)
        return self.env(*args, **kwargs)

    def get_allowed_operations(self):
        if request.method == "GET":
            return QUERY_OPERATION
        return ALL_OPERATIONS

    def serialize(self, execution_result):
        data = execution_result_to_dict(execution_result, self.format_error)
        return jsonify(data)

    def can_display_graphiql(self):
        if request.method != 'GET':
            return False
        if 'raw' in request.args:
            return False

        best = request.accept_mimetypes \
            .best_match(['application/json', 'text/html'])

        return best == 'text/html' and \
            request.accept_mimetypes[best] > \
            request.accept_mimetypes['application/json']

    def get_graphql_params(self):
        data = {}
        content_type = request.mimetype
        if content_type == 'application/graphql':
            data = {'query': request.data.decode('utf8')}
        elif content_type == 'application/json':
            try:
                data = request.get_json()
            except:
                raise InvalidJSONError()
        elif content_type in ('application/x-www-form-urlencoded',
                            'multipart/form-data', ):
            data = request.form.to_dict()

        query_params = request.args.to_dict()
        return params_from_http_request(query_params, data)

    def dispatch_request(self):
        graphql_params = None
        status = 200
        try:
            if request.method not in ['GET', 'POST']:
                raise HTTPMethodNotAllowed()
            execution_result = self.execute(
                self.get_graphql_params(),
                root=self.get_root_value(),
                context=self.get_context(),
                middleware=self.get_middleware(),
                allowed_operations=self.get_allowed_operations()
            )
        except Exception as error:
            if isinstance(error, GraphQLHTTPError):
                status = error.status_code
            execution_result = ExecutionResult(errors=[error])

        if self.graphiql and self.can_display_graphiql():
            return self.render_graphiql(graphql_params, execution_result)

        if execution_result.data is None and execution_result.errors:
            status = 400

        return self.serialize(execution_result), status
