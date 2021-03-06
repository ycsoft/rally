# Copyright 2015: Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import sys

from rally.common.i18n import _
from rally.common.i18n import _LE
from rally.common.plugin import discover
from rally.common.plugin import info
from rally.common.plugin import meta
from rally import exceptions


def deprecated(reason, rally_version):
    """Mark plugin as deprecated.

    :param reason: Message that describes reason of plugin deprecation
    :param rally_version: Deprecated since this version of Rally
    """
    def decorator(plugin):
        plugin._set_deprecated(reason, rally_version)
        return plugin

    return decorator


def base():
    """Mark Plugin as a base.

    .. warning:: This decorator should be added the line before
        six.add_metaclass if it is used.
    """
    def wrapper(cls):
        if not issubclass(cls, Plugin):
            raise exceptions.RallyException(_(
                "Plugin's Base can be only a subclass of Plugin class."))

        parent = cls._get_base()
        if parent != Plugin:
            raise exceptions.RallyException(_(
                "'%(plugin_cls)s' can not be marked as plugin base, since it "
                "inherits from '%(parent)s' which is also plugin base.") % {
                "plugin_cls": cls.__name__,
                "parent": parent.__name__})

        cls.base_ref = cls
        return cls
    return wrapper


def configure(name, namespace="default", hidden=False):
    """Use this decorator to configure plugin's attributes.

    :param name: name of plugin that is used for searching purpose
    :param namespace: plugin namespace
    :param hidden: if True the plugin will be marked as hidden and can be
        loaded only explicitly
    """

    def decorator(plugin):
        if name is None:
            plugin_id = "%s.%s" % (plugin.__module__, plugin.__name__)
            raise ValueError("The name of the plugin %s cannot be None." %
                             plugin_id)
        plugin._configure(name, namespace)
        plugin._meta_set("hidden", hidden)
        return plugin

    return decorator


class Plugin(meta.MetaMixin, info.InfoMixin):
    """Base class for all Plugins in Rally."""

    @classmethod
    def _configure(cls, name, namespace="default"):
        """Init plugin and set common meta information.

        For now it sets only name of plugin, that is an actual identifier.
        Plugin name should be unique, otherwise exception is raised.

        :param name: Plugin name
        :param namespace: Plugins with the same name are allowed only if they
                          are in various namespaces.
        """
        cls._meta_init()
        cls._set_name_and_namespace(name, namespace)
        return cls

    @classmethod
    def unregister(cls):
        """Removes all plugin meta information and makes it undiscoverable."""
        cls._meta_clear()

    @classmethod
    def _get_base(cls):
        return getattr(cls, "base_ref", Plugin)

    @classmethod
    def _set_name_and_namespace(cls, name, namespace):
        try:
            existing_plugin = cls._get_base().get(name=name,
                                                  namespace=namespace,
                                                  allow_hidden=True,
                                                  fallback_to_default=False)

        except exceptions.PluginNotFound:
            cls._meta_set("name", name)
            cls._meta_set("namespace", namespace)
        else:
            cls.unregister()
            raise exceptions.PluginWithSuchNameExists(
                name=name, namespace=existing_plugin.get_namespace(),
                existing_path=(
                    sys.modules[existing_plugin.__module__].__file__),
                new_path=sys.modules[cls.__module__].__file__
            )

    @classmethod
    def _set_deprecated(cls, reason, rally_version):
        """Mark plugin as deprecated.

        :param reason: Message that describes reason of plugin deprecation
        :param rally_version: Deprecated since this version of Rally
        """

        cls._meta_set("deprecated", {
            "reason": reason,
            "rally_version": rally_version
        })
        return cls

    @classmethod
    def get(cls, name, namespace=None, allow_hidden=False,
            fallback_to_default=True):
        """Return plugin by its name from specified namespace.

        This method iterates over all subclasses of cls and returns plugin
        by name from specified namespace.

        If namespace is not specified, it will return first found plugin from
        any of namespaces.

        :param name: Plugin's name
        :param namespace: Namespace where to search for plugins
        :param allow_hidden: if False and found plugin is hidden then
            PluginNotFound will be raised
        :param fallback_to_default: if True, then it tries to find
            plugin within "default" namespace
        """
        potential_result = cls.get_all(name=name, namespace=namespace,
                                       allow_hidden=True)

        if fallback_to_default and len(potential_result) == 0:
            # try to find in default namespace
            potential_result = cls.get_all(name=name, namespace="default",
                                           allow_hidden=True)

        if len(potential_result) == 1:
            plugin = potential_result[0]
            if allow_hidden or not plugin.is_hidden():
                return plugin

        elif potential_result:
            hint = _LE("Try to choose the correct Plugin base or namespace to "
                       "search in.")
            if namespace:
                needle = "%s at %s namespace" % (name, namespace)
            else:
                needle = "%s at any of namespaces" % name
            raise exceptions.MultipleMatchesFound(
                needle=needle,
                haystack=", ".join(p.get_name() for p in potential_result),
                hint=hint)

        raise exceptions.PluginNotFound(
            name=name, namespace=namespace or "any of")

    @classmethod
    def get_all(cls, namespace=None, allow_hidden=False, name=None):
        """Return all subclass plugins of plugin.

        All plugins that are not configured will be ignored.

        :param namespace: return only plugins from specified namespace.
        :param name: return only plugins with specified name.
        :param allow_hidden: if False return only non hidden plugins
        """
        plugins = []

        for p in discover.itersubclasses(cls):
            if not issubclass(p, Plugin):
                continue
            if not p._meta_is_inited(raise_exc=False):
                continue
            if name and name != p.get_name():
                continue
            if namespace and namespace != p.get_namespace():
                continue
            if not allow_hidden and p.is_hidden():
                continue
            plugins.append(p)

        return plugins

    @classmethod
    def get_name(cls):
        """Return name of plugin."""
        return cls._meta_get("name")

    @classmethod
    def get_namespace(cls):
        """"Return namespace of plugin, e.g. default or openstack."""
        return cls._meta_get("namespace")

    @classmethod
    def is_hidden(cls):
        """Return True if plugin is hidden."""
        return cls._meta_get("hidden", False)

    @classmethod
    def is_deprecated(cls):
        """Return deprecation details for deprecated plugins."""
        return cls._meta_get("deprecated", False)
