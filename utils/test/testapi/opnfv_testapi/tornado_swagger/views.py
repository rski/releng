##############################################################################
# Copyright (c) 2016 ZTE Corporation
# feng.xiaowei@zte.com.cn
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Apache License, Version 2.0
# which accompanies this distribution, and is available at
# http://www.apache.org/licenses/LICENSE-2.0
##############################################################################
import inspect
import json

import tornado.template
import tornado.web

from settings import SWAGGER_VERSION, SWAGGER_API_LIST, SWAGGER_API_SPEC
from settings import models, basePath


def json_dumps(obj, pretty=False):
    return json.dumps(obj, sort_keys=True, indent=4, separators=(',', ': ')) \
        if pretty else json.dumps(obj)


class SwaggerUIHandler(tornado.web.RequestHandler):
    def initialize(self, static_path, **kwds):
        self.static_path = static_path

    def get_template_path(self):
        return self.static_path

    def get(self):
        discovery_url = basePath() + self.reverse_url(SWAGGER_API_LIST)
        self.render('index.html', discovery_url=discovery_url)


class SwaggerResourcesHandler(tornado.web.RequestHandler):
    def initialize(self, api_version, exclude_namespaces, **kwds):
        self.api_version = api_version
        self.exclude_namespaces = exclude_namespaces

    def get(self):
        self.set_header('content-type', 'application/json')
        resources = {
            'apiVersion': self.api_version,
            'swaggerVersion': SWAGGER_VERSION,
            'basePath': basePath(),
            'produces': ["application/json"],
            'description': 'Test Api Spec',
            'apis': [{
                'path': self.reverse_url(SWAGGER_API_SPEC),
                'description': 'Test Api Spec'
            }]
        }

        self.finish(json_dumps(resources, self.get_arguments('pretty')))


class SwaggerApiHandler(tornado.web.RequestHandler):
    def initialize(self, api_version, base_url, **kwds):
        self.api_version = api_version
        self.base_url = base_url

    def get(self):
        self.set_header('content-type', 'application/json')
        apis = self.find_api(self.application.handlers)
        if apis is None:
            raise tornado.web.HTTPError(404)

        specs = {
            'apiVersion': self.api_version,
            'swaggerVersion': SWAGGER_VERSION,
            'basePath': basePath(),
            'apis': [self.__get_api_spec__(path, spec, operations)
                     for path, spec, operations in apis],
            'models': self.__get_models_spec(models)
        }
        self.finish(json_dumps(specs, self.get_arguments('pretty')))

    def __get_models_spec(self, models):
        models_spec = {}
        for model in models:
            models_spec.setdefault(model.id, self.__get_model_spec(model))
        return models_spec

    @staticmethod
    def __get_model_spec(model):
        return {
            'description': model.summary,
            'id': model.id,
            'notes': model.notes,
            'properties': model.properties,
            'required': model.required
        }

    @staticmethod
    def __get_api_spec__(path, spec, operations):
        return {
            'path': path,
            'description': spec.handler_class.__doc__,
            'operations': [{
                'httpMethod': api.func.__name__.upper(),
                'nickname': api.nickname,
                'parameters': api.params.values(),
                'summary': api.summary,
                'notes': api.notes,
                'responseClass': api.responseClass,
                'responseMessages': api.responseMessages,
            } for api in operations]
        }

    @staticmethod
    def find_api(host_handlers):
        def get_path(url, args):
            return url % tuple(['{%s}' % arg for arg in args])

        def get_operations(cls):
            return [member.rest_api
                    for (_, member) in inspect.getmembers(cls)
                    if hasattr(member, 'rest_api')]

        for host, handlers in host_handlers:
            for spec in handlers:
                for (_, mbr) in inspect.getmembers(spec.handler_class):
                    if inspect.ismethod(mbr) and hasattr(mbr, 'rest_api'):
                        path = get_path(spec._path, mbr.rest_api.func_args)
                        operations = get_operations(spec.handler_class)
                        yield path, spec, operations
                        break
