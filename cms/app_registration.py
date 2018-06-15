import inspect
from importlib import import_module

from django.apps import apps
from django.utils.module_loading import module_has_submodule


CMS_CONFIG_NAME = 'cms_apps'


def autodiscover_cms_files():
    """
    Find and import all cms_apps.py modules. Add a cms_app attribute
    to django's app config.
    """
    for app_config in apps.get_app_configs():
        try:
            cms_module = import_module(
                '%s.%s' % (app_config.name, CMS_CONFIG_NAME))
        except:
            # If something in cms_apps.py raises an exception let that
            # exception bubble up. Only catch the exception if
            # cms_apps.py doesn't exist
            if module_has_submodule(app_config.module, CMS_CONFIG_NAME):
                raise
        else:
            for name, obj in inspect.getmembers(cms_module):
                # TODO: Raise exception if a suitable class can't be
                # found in the module or if there's more than one?
                if inspect.isclass(obj) and CMSAppConfig in obj.__mro__:
                    # We are adding this attribute here rather than in
                    # django's app config definition because there are
                    # all kinds of limitations as to what can be
                    # imported in django's apps.py and this could cause
                    # issues
                    app_config.cms_app = obj()


def _register_cms_extension_if_exists(app_config):
    """
    Helper function.
    Call the register_extension method on cms app classes. Handle cases
    when the django app does not have a cms extension to register.
    """
    # The cms_app attr is added by the autodiscover_cms_files
    # function if a cms_apps.py file with a suitable class is found.
    is_cms_app = hasattr(app_config, 'cms_app')
    # The register_extension method is only present on the cms app class
    # if there is an extension to register. For classes that only have
    # config this method will not be present.
    if is_cms_app:
        has_cms_extension = hasattr(
            app_config.cms_app, 'register_extension')
    else:
        has_cms_extension = False

    if is_cms_app and has_cms_extension:
        app_config.cms_app.register_extension()


def register_cms_extensions():
    """
    Run register extension code for each cms app
    """
    for app_config in apps.get_app_configs():
        _register_cms_extension_if_exists(app_config)


class CMSAppConfig():
    pass
