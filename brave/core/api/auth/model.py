class AuthorizationMethod(object):
    """Generic class that declares the methods for the various authorization methods Core supports. To add a new
        authorization method, simply create a subclass of this class and override all of the methods. Authentication of
        the user in question is done prior to any of the methods in this class being called."""

    # The formal name of the authorization method, this is displayed in areas such as the application registration form
    name = ""

    # This is used when applications are requesting authorization; the authorization endpoint will be
    # /api/auth/{short}
    short = ""

    # Additional HTTPMethods that your authorization method implements. Should be a list of strings.
    # Will be callable at /api/auth/{short}/{method_name}
    additional_methods = []

    @classmethod
    def pre_authorize(cls, user, app, request, *args, **kw):
        """Called when an application is requesting access to a user, regardless of whether or not they've authorized
            the application. You MUST validate the request, ensuring that it meets the requirements of the authorization
            method. This is called prior to the user being displayed the authorization page. This function should return
            if the request is valid, and raise an exception otherwise.

            :param user: The :class:`User` attempting to authorize the application
            :param app: The :class:`Application` that is requesting authorization
            :param request: The :class:`Request` that was made to request authorization
            """

        raise NotImplementedError()

    @classmethod
    def authorize(cls, user, app, request, characters, all_chars, *args, **kw):
        """Called after the user has been displayed the authorization page, and has decided to authorize the
            application. You MUST validate the request, ensuring that it meets the requirements of the authorization
            method. This is where you should parse the response from the user to determine the approved scopes.

            :param user: The :class:`User` attempting to authorize the application
            :param app: The :class:`Application` that is requesting authorization
            :param request: The :class:`Request` that was made to request authorization
            :param characters: A list of the :class:`EVECharacter` that the user authorized the application to access
            :param all_chars: Indicates whether the user authorized the application to access all of their characters.
            :type all_chars: True or False
            :rtype: 'json:', dict(success=True, location=REDIRECT_URI_HERE)
            """

        raise NotImplementedError()

    @classmethod
    def deny_authorize(cls, user, app, request, *args, **kw):
        """Called after the user has been displayed the authorization page, and has decided NOT to authorize the
            application. You MUST validate the request, ensuring that it meets the requirements of the authorization
            method. Typically at this point you'll want to redirect to the requesting application with a notification
            that the user denied their request.

            :param user: The :class:`User` attempting to authorize the application
            :param app: The :class:`Application` that is requesting authorization
            :param request: The :class:`Request` that was made to request authorization
            :rtype: 'json:', dict(success=True, location=REDIRECT_URI_HERE)
            """

        raise NotImplementedError()

    @classmethod
    def authenticate(cls, user, app, request, *args, **kw):
        """Called when an application requests authorization to a user who has already authorized the application. You
            MUST validate the request, ensuring it meets the requirements of the authorization method. As the user has
            already approved the app to access the requested scope, you merely have to reply to the request as the
            authorization method dictates (such as supplying a new access token).

            :param user: The :class:`User` attempting to authorize the application
            :param app: The :class:`Application` that is requesting authorization
            :param request: The :class:`Request` that was made to request authorization
            :rtype: String representing the URL to redirect the user to."""

        raise NotImplementedError()

    @classmethod
    def get_application(cls, request, *args, **kw):
        """Returns the :class:`Application` corresponding to the application that made this authorization request.

            :param request: The :class:`Request` that was made to request authorization
            :rtype: :class:`Application`"""

        raise NotImplementedError()

    @classmethod
    def before_api(cls, *args, **kw):
        """Called before API calls from applications using this authorization method. Provides an opportunity for
            authorization methods that enforce additional requirements on API calls to check those. This method should
            return the :class:`Application` corresponding to the application that made the API call if the call is
            valid, and should raise an :class:`HTTPError` describing the error if the validation fails,

            :rtype: :class:`Application` that made the API call
        """

        raise NotImplementedError()

    @classmethod
    def after_api(cls, response, result, *args, **kw):
        """Called after API calls from applications using this authorization method. Provides an opportunity for
            authorization methods that enforce additional requirements on API calls to check those. This method should
            return response, modified as necessary.

            :param response: :class:`Response` prefilled with default information
            :param result: Dictionary with the results of the API call
            :rtype: :class:`Response`"""

        raise NotImplementedError()

    @classmethod
    def get_token(cls, token, service):
        """Returns the ApplicationGrant object corresponding to the provided token. AuthorizationMethods may extend the
            :class:`ApplicationGrant` and return a subclass instance, but MUST NOT override any default methods or
            fields of the default :class:`ApplicationGrant` class.

            :param token: A string representing the token being requested
            :param service: The :class:`Application` that we want the token for
            :rtype: :class:`ApplicationGrant` or a subclass of it."""

        raise NotImplementedError()

