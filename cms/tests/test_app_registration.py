import sys
from importlib import import_module
from mock import patch, Mock

from django.test import override_settings
from django.apps import apps, AppConfig
from django.core.exceptions import ImproperlyConfigured

from cms import app_registration
from cms.apps import CMSConfig
from cms.utils import setup
from cms.test_utils.testcases import CMSTestCase


class AutodiscoverTestCase(CMSTestCase):

    def _clear_autodiscover_imports(self):
        """Helper method to clear imports"""
        sys.path_importer_cache.clear()

        sys.modules.pop('cms.tests.test_app_registry.app_without_cms_file', None)
        sys.modules.pop('cms.tests.test_app_registry', None)
        sys.modules.pop('cms.tests.test_app_registry.app_with_cms_feature.models', None)
        sys.modules.pop('cms.tests.test_app_registry.app_without_cms_file.models', None)
        sys.modules.pop('cms.tests.test_app_registry.app_with_cms_feature', None)
        sys.modules.pop('cms.tests.test_app_registry.app_with_cms_feature.cms_apps', None)

    def setUp(self):
        self._clear_autodiscover_imports()

    def tearDown(self):
        self._clear_autodiscover_imports()

    @override_settings(INSTALLED_APPS=[
        'cms.tests.test_app_registry.app_with_cms_feature',
        'cms.tests.test_app_registry.app_without_cms_file'
    ])
    def test_imports_cms_apps_files(self):
        app_registration.autodiscover_cms_configs()

        # Make sure all the cms apps/files are imported during the cms
        # config autodiscover
        loaded = set([
            str(module) for module in sys.modules
            if 'cms.tests.test_app_registry' in module])
        expected = set([
            'cms.tests.test_app_registry.app_without_cms_file',
            'cms.tests.test_app_registry.app_without_cms_file.apps',
            'cms.tests.test_app_registry',
            'cms.tests.test_app_registry.app_with_cms_feature.models',
            'cms.tests.test_app_registry.app_without_cms_file.models',
            'cms.tests.test_app_registry.app_with_cms_feature',
            'cms.tests.test_app_registry.app_with_cms_feature.cms_apps',
            'cms.tests.test_app_registry.app_with_cms_feature.apps'
        ])
        self.assertSetEqual(loaded, expected)

    @override_settings(INSTALLED_APPS=[
        'cms.tests.test_app_registry.app_with_bad_cms_file',
    ])
    def test_raises_exception_raised_in_cms_file(self):
        # The cms file is badly written and raises a KeyError. We need
        # to make sure the exception definitely bubbles up and doesn't
        # get caught.
        with self.assertRaises(KeyError):
            app_registration.autodiscover_cms_configs()

    @override_settings(INSTALLED_APPS=[
        'cms.tests.test_app_registry.app_with_cms_feature',
        'cms.tests.test_app_registry.app_without_cms_file'
    ])
    def test_adds_cms_app_attribute_to_django_app_config(self):
        app_registration.autodiscover_cms_configs()

        # If a cms config is defined, add a cms_app attribute to the
        # django app config instance. Otherwise don't.
        app_list = [app for app in apps.get_app_configs()]
        self.assertTrue(hasattr(app_list[0], 'cms_app'))
        self.assertEqual(
            app_list[0].cms_app.__class__.__name__, 'CMSSomeFeatureConfig')
        self.assertFalse(hasattr(app_list[1], 'cms_app'))

    #~ @override_settings(INSTALLED_APPS=[
        #~ 'cms.tests.test_app_registry.app_without_cms_app_class',
    #~ ])
    #~ def test_raises_exception_when_no_cms_app_class_found_in_cms_file(self):
        #~ # No cms config defined in the cms file so raise exception
        #~ with self.assertRaises(ImproperlyConfigured):
            #~ app_registration.autodiscover_cms_configs()

    #~ @override_settings(INSTALLED_APPS=[
        #~ 'cms.tests.test_app_registry.app_with_two_cms_app_classes',
    #~ ])
    #~ def test_raises_exception_when_more_than_one_cms_app_class_found_in_cms_file(self):
        #~ # More than one cms config defined so raise exception
        #~ with self.assertRaises(ImproperlyConfigured):
            #~ app_registration.autodiscover_cms_configs()


class GetCmsAppsWithFeaturesTestCase(CMSTestCase):

    @patch.object(apps, 'get_app_configs')
    def test_returns_only_apps_with_features(self, mocked_apps):
        # apps with cms_app attr and a configure method
        app_with_cms_ext1 = Mock(cms_app=Mock(spec=['configure_app']))
        app_with_cms_ext2 = Mock(cms_app=Mock(spec=['configure_app']))
        # app with cms_app attr without a configure method
        # this throws an AttributeError if configure_app is accessed
        app_with_cms_config = Mock(cms_app=Mock(spec=[]))
        # app without cms_app attr
        # this throws an AttributeError if cms_app is accessed
        non_cms_app = Mock(spec=[])
        # mock what apps have been installed
        mocked_apps.return_value = [
            app_with_cms_ext1,
            app_with_cms_config,
            app_with_cms_ext2,
            non_cms_app,
        ]

        apps_with_features = app_registration.get_cms_apps_with_features()

        # Of the 4 installed apps only 2 have features (1 is a
        # non-cms app and 1 is a cms app without a feature)
        self.assertListEqual(
            apps_with_features,
            [app_with_cms_ext1, app_with_cms_ext2])


class ConfigureCmsAppsTestCase(CMSTestCase):

    @patch.object(apps, 'get_app_configs')
    def test_runs_configure_app_method_for_app_with_enabled_config(
        self, mocked_apps
    ):
        # Set up app with label djangocms_feature_x that has a cms feature
        feature_app = Mock(spec=AppConfig)
        feature_app.label = 'djangocms_feature_x'
        feature_app.cms_app = Mock(spec=['configure_app'])
        # Set up app that makes use of djangocms_feature_x
        config_app = Mock(spec=AppConfig)
        config_app.cms_app = Mock(
            spec=['djangocms_feature_x_enabled'])
        config_app.cms_app.djangocms_feature_x_enabled = True
        # Pretend these mocked apps are in INSTALLED_APPS
        mocked_apps.return_value = [
            feature_app, config_app]

        app_registration.configure_cms_apps([feature_app])

        # If an app has enabled a feature, the configure method
        # for that feature should have run with that app as the arg
        feature_app.cms_app.configure_app.assert_called_once_with(
            config_app)

    @patch.object(apps, 'get_app_configs')
    def test_doesnt_run_configure_app_method_for_disabled_app(
        self, mocked_apps
    ):
        # Set up app with label djangocms_feature_x that has a cms feature
        feature_app = Mock(spec=AppConfig)
        feature_app.label = 'djangocms_feature_x'
        feature_app.cms_app = Mock(spec=['configure_app'])
        # Set up two apps that do not make use of djangocms_feature_x.
        # One does not define the enabled attr at all (most common
        # use case) and one defines it as False
        config_app_disabled1 = Mock(spec=AppConfig)
        config_app_disabled1.cms_app = Mock(spec=[])
        config_app_disabled2 = Mock(spec=AppConfig)
        config_app_disabled2.cms_app = Mock(
            spec=['djangocms_feature_x_enabled'])
        config_app_disabled2.cms_app.djangocms_feature_x_enabled = False
        # Pretend all these mocked apps are in INSTALLED_APPS
        mocked_apps.return_value = [
            feature_app, config_app_disabled1, config_app_disabled2]

        app_registration.configure_cms_apps([feature_app])

        # If an app has not enabled a feature, the configure method
        # for that feature should not have been run for that app
        self.assertFalse(feature_app.cms_app.configure_app.called)

    @patch.object(apps, 'get_app_configs')
    def test_doesnt_raise_exception_if_not_cms_app(
        self, mocked_apps
    ):
        # Set up app with label djangocms_feature_x that has a cms feature
        feature_app = Mock(spec=AppConfig)
        feature_app.label = 'djangocms_feature_x'
        feature_app.cms_app = Mock(spec=['configure_app'])
        # Set up non cms app
        non_cms_app = Mock(spec=AppConfig)
        # Pretend these mocked apps are in INSTALLED_APPS
        mocked_apps.return_value = [feature_app, non_cms_app]

        # An app that does not define a cms config should just be
        # ignored and not cause any exceptions
        try:
            app_registration.configure_cms_apps([feature_app])
        except AttributeError:
            self.fail("Exception raised when cms app config not defined")

    @patch.object(apps, 'get_app_configs')
    def test_runs_configure_app_method_for_correct_apps_when_multiple_apps(
        self, mocked_apps
    ):
        # Set up app with label djangocms_feature_x that has a cms feature
        feature_app_x = Mock(spec=AppConfig)
        feature_app_x.label = 'djangocms_feature_x'
        feature_app_x.cms_app = Mock(spec=['configure_app'])
        # Set up app with label djangocms_feature_y that has a cms feature
        feature_app_y = Mock(spec=AppConfig)
        feature_app_y.label = 'djangocms_feature_y'
        feature_app_y.cms_app = Mock(spec=['configure_app'])
        # Set up apps that makes use of djangocms_feature_x
        config_app_x = Mock(spec=AppConfig)
        config_app_x.cms_app = Mock(
            spec=['djangocms_feature_x_enabled'])
        config_app_x.cms_app.djangocms_feature_x_enabled = True
        # Set up app that makes use of djangocms_feature_y
        config_app_y = Mock(spec=AppConfig)
        config_app_y.cms_app = Mock(
            spec=['djangocms_feature_y_enabled'])
        config_app_y.cms_app.djangocms_feature_y_enabled = True
        # Set up app that makes use of feature x & y
        config_app_xy = Mock(spec=AppConfig)
        config_app_xy.cms_app = Mock(
            spec=['djangocms_feature_x_enabled',
                  'djangocms_feature_y_enabled']
        )
        config_app_xy.cms_app.djangocms_feature_x_enabled = True
        config_app_xy.cms_app.djangocms_feature_y_enabled = True
        # Set up non cms app
        non_cms_app = Mock(spec=AppConfig)
        # Pretend these mocked apps are in INSTALLED_APPS
        mocked_apps.return_value = [
            feature_app_x, non_cms_app, config_app_xy, config_app_y,
            config_app_x, feature_app_y]

        app_registration.configure_cms_apps(
            [feature_app_x, feature_app_y])

        # Assert we configured the 2 apps we expected with feature x
        self.assertEqual(
            feature_app_x.cms_app.configure_app.call_count, 2)
        self.assertEqual(
            feature_app_x.cms_app.configure_app.call_args_list[0][0][0],
            config_app_xy)
        self.assertEqual(
            feature_app_x.cms_app.configure_app.call_args_list[1][0][0],
            config_app_x)
        # Assert we configured the 2 apps we expected with feature y
        self.assertEqual(
            feature_app_y.cms_app.configure_app.call_count, 2)
        self.assertEqual(
            feature_app_y.cms_app.configure_app.call_args_list[0][0][0],
            config_app_xy)
        self.assertEqual(
            feature_app_y.cms_app.configure_app.call_args_list[1][0][0],
            config_app_y)


class SetupCmsAppsTestCase(CMSTestCase):

    @patch.object(setup, 'setup_cms_apps')
    def test_setup_cms_apps_function_run_on_startup(self, mocked_setup):
        cms_module = import_module('cms')

        CMSConfig('app_name', cms_module).ready()

        mocked_setup.assert_called_once()

    @override_settings(INSTALLED_APPS=[
        'cms.tests.test_app_registry.app_with_cms_feature',
        'cms.tests.test_app_registry.app_without_cms_file',
        'cms.tests.test_app_registry.app_with_cms_config'
    ])
    def test_cms_apps_setup_after_setup_function_run(self):
        # This is the function that gets run on startup
        setup.setup_cms_apps()

        # Get the django app configs to do asserts on them later
        feature_app = apps.get_app_config('app_with_cms_feature')
        config_app = apps.get_app_config('app_with_cms_config')
        non_cms_app = apps.get_app_config('app_without_cms_file')

        # cms_app attribute has been added to all app configs
        # that correctly define a cms_apps.py file
        self.assertFalse(hasattr(non_cms_app, 'cms_app'))
        self.assertTrue(hasattr(feature_app, 'cms_app'))
        self.assertTrue(hasattr(config_app, 'cms_app'))

        # Code from the configure method did what we expected.
        # Relying on checking that the code in the app_with_cms_feature
        # test app ran. This is so as to avoid mocking and allow the
        # whole app registration code to run through.
        self.assertEqual(feature_app.cms_app.num_configured_apps, 1)
        self.assertTrue(config_app.cms_app.configured)
