import json
import six

from graphql.error import GraphQLError, format_error as format_graphql_error
from ..params import GraphQLParams
from .exceptions import InvalidVariablesJSONError, MissingQueryError


QUERY_OPERATION = {"query"}

MUTATION_OPERATION = {"mutation"}

SUBSCRIPTION_OPERATION = {"subscription"}

ALL_OPERATIONS = QUERY_OPERATION | MUTATION_OPERATION | SUBSCRIPTION_OPERATION


def params_from_http_request(query_params, data):
    variables = data.get("variables") or query_params.get("variables")
    if isinstance(variables, six.string_types):
        try:
            variables = json.loads(variables)
        except:
            raise InvalidVariablesJSONError()

    return GraphQLParams(
        query=data.get("query") or query_params.get("query"),
        document_id=data.get("documentId") or query_params.get("documentId"),
        operation_name=(data.get("operationName") or query_params.get("operationName")),
        variables=variables,
    )


def execution_result_to_dict(execution_result, format_error):
    data = {}
    if execution_result.errors:
        data["errors"] = [format_error(error) for error in execution_result.errors]
    if execution_result.data and not execution_result.invalid:
        data["data"] = execution_result.data
    return data


def format_error(error):
    if isinstance(error, GraphQLError):
        return format_graphql_error(error)

    return {"message": six.text_type(error)}