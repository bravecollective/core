# encoding: utf-8

from __future__ import unicode_literals

from web.core import request
from web.auth import always

from brave.core.util.predicate import is_administrator
from brave.generic.controller import Generic, Action
from brave.generic.column import Column, PrimaryColumn, LinkColumn, DateColumn, ReferenceCountColumn
from brave.generic.index import Index

from brave.core.account.model import User


log = __import__('logging').getLogger(__name__)


class UsersController(Generic):
    __model__ = User
    __order__ = 'username'
    __form__ = None
    
    __metadata__ = dict(
            area = 'user',
            icon = 'user',
            singular = "User",
            plural = "Users",
            subtitle = "User account management."
        )
    
    # Column Definitions
    
    username = PrimaryColumn('username', "Name", 2)
    email = LinkColumn('email', "E-Mail", 3)
    
    credentials = ReferenceCountColumn('credentials', "Creds.", 1)
    characters = ReferenceCountColumn('characters', "Chars.", 1)
    grants = ReferenceCountColumn('grants', "Grants", 1)
    
    character = Column('primary', "Default", 3)  # TODO: EVE Character Column (+ Portrait)
    
    joined = DateColumn('created', "Joined", 2)
    
    # Security Configuraiton of Existing Views
    # TODO: Allow 'core moderators' too.
    
    #list = Generic.list.clone(condition=is_administrator)
    #create = Generic.create.clone(condition=is_administrator)
    #read = Generic.read.clone(condition=is_administrator, template='brave.core.account.template.view')
    #update = Generic.update.clone(condition=is_administrator)
    #delete = Generic.delete.clone(condition=is_administrator)
    
    # Quick Search Indexes
    
    username_ = Index('username')
    email_ = Index('email')
    
    # Custom Actions
    
    @Action.method("Change Password",
            icon = 'key',
            condition = always)  # TODO: allow core moderators
    def passwd(self):
        user = request.record
        
        if request.is_xhr:
            return 'brave.core.account.template.passwd', dict(area='user', user=user), dict(only='modal')
        
        return 'brave.core.account.template.passwd', dict(area='user', user=user)
    
    @passwd.bind('post')
    def passwd(self, password1, password2):
        user = request.record
        
        if password1 != password2:
            return dict(success=False, message="Passwords do not match.")
        
        user.password = password1
        user.save()
        
        return 'json:', dict(success=True, message="Password updated.")
