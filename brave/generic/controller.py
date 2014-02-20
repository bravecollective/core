# encoding: utf-8

from __future__ import unicode_literals

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import csv

from math import ceil
from operator import __or__

from web.core import request, Controller, HTTPMethod
from web.core.http import HTTPFound, HTTPNotFound
from web.core.locale import _

from marrow.schema.declarative import BaseAttribute, Attribute
from marrow.schema.util import DeclarativeAttributes
from marrow.util.convert import array

from mongoengine import Q
from mongoengine.errors import ValidationError

from brave.generic.action import Action
from brave.generic.column import Column
from brave.generic.filter import Filter
from brave.generic.index import Index
from brave.generic.util import only, serialize, context


log = __import__('logging').getLogger(__name__)


def apply_input(obj, input):
    for k, v in input.iteritems():
        if '.' not in k:
            setattr(obj, k, v)
            continue
        
        parts = k.split('.')
        
        current = obj
        for part in parts[:-1]:
            current = getattr(obj, part)
        
        setattr(current, parts[-1], v)


def valid_field(ref):
    try:
        request.controller.__model__._lookup_field(ref)
    except:
        return False
    
    return True


class Generic(BaseAttribute, Controller):
    """A generalized structure for the presentation and implementation of record management.
    
    HTTP    GET /object/              Full page template for the list view.
    
     XHR    GET /object/index.html    The table body fragment for a given range of results.      XHR    GET /object/index.json    The equivalent of the table body in pure JSON.     So 
     XHR    GET /object/form.html     The form body fragment for record creation.
     XHR    GET /object/form.json     The schema of the record creation form, also available in yaml and bencode.
    
    HTTP   POST /object/              The action of creating a new record, HTTP redirect version.
     XHR   POST /object/              The action of creating a new record, JSON version.
    
    HTTP    GET /object/id            Full page template for record detail view.
     XHR    GET /object/id.json       JSON version of the record data.  (Also available: yaml, bencode.)
    
    HTTP   POST /object/id            Update the given record, HTTP redirect version.
     XHR   POST /object/id            Update the given record, JSON version.
                                      Partial updates are supported.
    
    HTTP DELETE /object/id            Delete the record, HTTP redirect version.
     XHR DELETE /object/id            Delete the record, JSON version.
    """
    
    __model__ = Attribute()
    __key__ = Attribute(default='id')
    __form__ = Attribute()
    __order__ = Attribute(default=None)  # default order
    
    __metadata__ = Attribute(default=dict())  # area, icon, etc
    __context__ = Attribute(default=None)  # dict or callable returning a dict of vars to pass to templates
    
    # Aggregates
    
    __actions__ = DeclarativeAttributes(Action)
    __filters__ = DeclarativeAttributes(Filter)
    __columns__ = DeclarativeAttributes(Column)
    __indexes__ = DeclarativeAttributes(Index)
    
    # Helpers.
    
    def __json__(self, record):
        """Translate a database record into valid JSON data."""
        if hasattr(record, '__json__'):
            return record.__json__()
        
        log.warning("%s instance is missing a __json__ method.", record.__class__.__name__)
        return record.to_json()
    
    @property
    def __query__(self):
        """Return a base query object.
        
        It is useful to override this if you have specific requirements, esp. security.
        """
        query = self.__model__.objects
        
        if self.__order__:
            query = query.order_by(self.__order__)
        
        return query
    
    # Default actions.
    
    @Action.method('{model.__name__} Records', False, template='brave.generic.template.list')
    def list(self, q=None, s=None, p=None, l=None, o=None, omit=None):
        """Return a listing, partial listing body, or serialized results."""
        
        controller = request.controller
        
        jsonify = controller.__json__
        results = controller.__query__
        
        page = int(p) if p else 1
        limit = min(int(l) if l else 10, 100)
        order = array(o) if o else controller.__order__
        omit = array(omit) if omit else []
        
        if q and q.strip():
            results = results.filter(reduce(__or__, [Q(**{i: q}) for index in controller.__indexes__.itervalues() for i in index.terms]))
        
        fields = [j for i in controller.__columns__.itervalues() for j in i.fields if valid_field(j)]
        results = results.only(*fields)
        
        count = results.count()
        pages = 1 if not limit else int(ceil(count / float(limit)))
        
        if limit:
            results = results.skip((page - 1) * limit).limit(limit)
        
        if request.is_xhr or ( request.format and request.format == 'html' ):
            log.debug("action.list.rows model=%s p=%d l=%d o=%s c=%d q=%r",
                    controller.__model__.__name__,
                    page, limit, order, count, q.encode('utf8') if q else None)
            return self.action.template, context(limit=limit, count=count, pages=pages, page=page, results=results, area=controller.__metadata__.get('area', None)), only('rows')
        
        if request.format:
            log.debug("action.list.serialize model=%s p=%d l=%d o=%s c=%d q=%r",
                    controller.__model__.__name__,
                    page, limit, order, count, q.encode('utf8') if q else None)
            
            data = dict(success=True)
            
            if 'count' not in omit:
                data['count'] = dict(
                        results = count,
                        pages = pages,
                        limit = limit
                    )
            
            if 'query' not in omit:
                 data['query'] = dict()
                
            if 'results' not in omit:
                data['results'] = []
                for record in results:
                    data['results'].append({name: col.serialize(record) for name, col in controller.__columns__.iteritems() if col.condition})
            
            if request.format in ('csv', 'tab'):
                tmp = StringIO()
                cw = csv.writer(tmp, dialect='excel' if request.format == 'csv' else 'excel-tab')
                
                for record in data['results']:
                    row = []
                    
                    for name, col in controller.__columns__.iteritems():
                        if not col.condition: continue
                        
                        if not isinstance(record[name], dict):
                            row.append(record[name])
                            continue
                        
                        for k, v in record[name].iteritems():
                            row.append(v)
                    
                    cw.writerow(row)
                
                return tmp.getvalue().strip('\r\n')
            
            return serialize(), data
        
        log.debug("action.list.html model=%s p=%d l=%d o=%s c=%d q=%r",
                controller.__model__.__name__,
                page, limit, order, count, q.encode('utf8') if q else None)
        return self.action.template, context(limit=limit, count=count, pages=pages, page=page, results=results, area=controller.__metadata__.get('area', None))
    
    @list.bind('post')
    def list(self, **data):
        log.debug("POST Listing")
        
        record = request.controller.__model__()
        record = apply_input(record, data)
        
        record.save()
        
        return serialize(), dict(
                success = True,
                status = 'created',
                identifier = record.id
            )
    
    @Action.method('New {model.__name__} Record', False, template='brave.generic.template.form')
    def create(self):
        if request.is_xhr:
            log.debug("action.create.get.xhr")
            return self.action.template, dict(
                area = self._area,
                form = self._form,
                data = None,
                controller = self
            ), dict(only='modal')

        log.debug("action.create.get.html")
        return self.action.template, dict(
                area = self._area,
                form = self._form,
                data = None,
                controller = self
            )
    
    @Action.method('{record}', False, template='brave.generic.template.view')
    def read(self):
        controller = request.controller
        record = request.record
        
        if request.format:
            log.debug("action.read.get.serialize")
            return serialize(), dict(
                    success = True,
                    query = {controller.__key__: getattr(record, controller.__key__)},
                    result = record.__json__() if hasattr(record, '__json__') else controller.__json__(record)
                )
        
        if request.is_xhr:
            log.debug("action.read.get.xhr")
            return self.action.template, context(), only()
        
        log.debug("action.read.get.html")
        return self.action.template, context()
    
    @Action.method('Delete {model.__name__} Record', template='brave.generic.template.delete', icon='trash-o')
    def delete(self):
        if request.is_xhr:
            log.debug("action.delete.get.xhr")
            return serialize(), dict(
                    success = True,
                    action = 'confirm',
                    title = _("Are you sure you wish to delete this record?"),
                    message = _("Associated data may also be removed.  This action can not be undone."),
                    label = _("Delete"),
                    verb = 'delete'
                )
        
        log.debug("action.delete.get.html")
        return self.action.template, context()
    
    @delete.bind('delete')
    def delete(self):
        try:
            request.record.delete()
        except:
            log.exception("Failure deleting record: %r", request.record)
            if request.is_xhr or request.format:
                return serialize(), dict(success=False, title=_("Error"), message=_("Encountered unexpected error while attempting to delete record."))
        
        if request.is_xhr or request.format:
            log.debug("action.delete.delete.serialize")
            return serialize(), dict(success=True, title=_("Success"), message=_("Record deleted."))
        
        log.debug("action.delete.delete.html")
        raise HTTPFound(location='../')
    
    @Action.method('Modify {model.__name__} Record', template='brave.generic.template.form', icon='pencil')
    def update(self):
        form = deepcopy(base._form)
        form.args['action'] = '/'.join(request.path.split('/')[:-1])
        
        data = request.record.to_mongo()
        
        if request.is_xhr:
            log.debug("action.update.get.serialize")
            return base._templates['update'], dict(
                area = base._area,
                form = form,
                data = data,
                controller = base
            ), dict(only='modal')
        
        log.debug("action.update.get.html")
        return base._templates['update'], dict(
                area = base._area,
                form = form,
                data = data,
                controller = base
            )
    
    @update.bind('post')
    def update(self, **data):
        log.debug("action.update.post")
        
        record = request.record
        record = apply_input(record, data)
        
        return serialize(), dict(
                success = True,
                status = 'updated'
            )
    
    # WebCore controller methods.
    
    def index(self, *args, **kw):
        request.controller = self
        return self.list.controller()(*args, **kw)
    
    def __lookup__(self, identifier, *args, **kw):
        request.path_info_pop()
        request.controller = self
        identifier, _, ext = identifier.rpartition('.')
        if not identifier: identifier = ext
        return InstanceMethods(identifier), args


class InstanceIndex(HTTPMethod):
    def __init__(self):
        controller = request.controller
        
        self.get = controller.read.controller()
        self.post = controller.update.controller()
        self.delete = controller.delete.controller()
        
        super(InstanceIndex, self).__init__()


class InstanceMethods(Controller):
    def __init__(self, identifier):
        super(InstanceMethods, self).__init__()
        
        controller = request.controller
        
        try:
            request.record = controller.__model__.objects.get(**{controller.__key__: identifier})
        except (controller.__model__.DoesNotExist, ValidationError):
            log.exception("instance.init model=%s %s=%s", controller.__model__.__name__, controller.__key__, identifier)
            raise HTTPNotFound(_("Record with identifier {0} can not be found.").format(identifier))

        self.index = InstanceIndex()
        
        # Attach additional actions.
        for action in (i for i in controller.__actions__.itervalues() if i.instance and i.__name__ not in ('read', )):
            setattr(self, action.__name__, action.controller())
        
        log.debug("instance.init model=%s %s=%s\n\t%r", controller.__model__.__name__, controller.__key__, identifier, request.record)
