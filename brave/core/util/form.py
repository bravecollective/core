# encoding: utf-8

from __future__ import unicode_literals

from copy import copy
from web.core.locale import L_
from marrow.widgets import Widget, NestedWidget, Input, BooleanInput
from marrow.widgets import transforms as t
from marrow.tags import html5 as H
from marrow.util.convert import boolean


log = __import__('logging').getLogger(__name__)


class BooleanTransform(t.Transform):
    def __call__(self, value):
        if value: return 'True'
        return None

    def native(self, value):
        if isinstance(value, list):
            return boolean(value[-1])
        return boolean(value)


class IntegerListTransform(t.BaseTransform):
    def __call__(self, value):
        if value is None: return ''
        
        return [unicode(i) for i in value]
        
    def native(self, value):
        try:
            return [int(i) for i in value]
        except ValueError:
            raise t.TransformException("Invalid number: {0}".format(i))


class CheckboxField(BooleanInput):
    transform = BooleanTransform()

    @property
    def template(self):
        return H.div(strip=True) [
                H.input(type_="hidden", name=self.name, id=self.name + '-hidden', value='false'),
                H.label(for_=self.name + '-field', class_='') [
                        H.input(type_="checkbox", name=self.name, id=self.name + '-field', checked=self.value, value='true', **self.args),
                        self.title
                    ]
            ]


class BlankSubmit(Widget):
    @property
    def template(self):
        return H.input(type_='submit')


class Paragraph(Widget):
    @property
    def template(self):
        return H.p(**self.args) [ self.title ]


class Tab(NestedWidget):
    @property
    def template(self):
        args = dict(self.args)
        args['class_'] = ('tab-pane ' + args.get('class_', '')).strip()
        labels = args.pop('labels', True)
        
        children = self.children
        data = self.data
        
        if isinstance(self, EmbeddedDocumentTab):
            data = {self.name + '.' + k: v for k, v in self.data[self.name].iteritems()} if self.name in self.data else {}
            
            children = [copy(child) for child in self.children]
            for child in children:
                child.name = self.name + '.' + child.name
        
        root = H.div(id=self.name + '-tab', **args)
        
        parts = [
                ((H.div(class_='control-group' + (' success' if child.args.get('required', False) else '')) [
                        (H.label(for_=child.name + '-field', class_='control-label')[ child.title ]) if not isinstance(child, CheckboxField) else '',
                        H.div(class_='controls') [ child(data) ]
                    ]) if labels else ( H.div [ child(data) ] ))
                for child in children
            ]
        
        return root[parts]


class EmbeddedDocumentTab(Tab):
    def native(self, data):
        from marrow.util.bunch import Bunch
        result = dict()
        
        data = data[self.name] if self.name in data else Bunch.partial(self.name, data)
        
        for child in self.children:
            if isinstance(child, NestedWidget):
                result.update(child.native(Bunch.partial(child.name, data))[0])
                continue
            
            result[child.name] = child.native(data)
        
        return {self.name: result}, dict()
