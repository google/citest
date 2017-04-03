# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Support for bindings and configuration."""


import argparse
import copy
import inspect
import os

import ConfigParser

def _normalize_key(key):
  """Handle historic interpretation of binding keys being upper-cased.

  Converts the queries to lower case. This does not enforce that keys added
  through configuration files are lower cased, in which case they will not
  be findable. Eventually this should be the identity.
  """
  return key.lower()


class ConfigurationBindings(object):
  """Represents variable bindings for a configuration.

  ConfigurationBindings is essentially a dictionary of name/value pairs.
  However they are composed from a hierarchical search space and make use
  of python "ConfigParser" to specify them in a static file.

  The search space is (in order of precedence):
    Overrides - These are explicit values injected at runtime.
       They could be from flags or other explicit API calls.
    ConfigParser - These are values read from configuration files[*].
    LazyInitializers - These are values derived from injected functions.
       The functions compute the value only if/when it is first accessed.
    Defaults - These are static default values if not found in a configuration
       file.


  The ConfigParser has an additional hierarchy of sections. If the instance
  section attribute is set, then only that section in the ConfigParser will be
  considered. The Defaults are implemented as part of the ConfigParser

  The LazyInitializers are computed by an added function with the signature
      value function(bindings, key)
  where the <function> returns the desired <value> for the desired <key>
  while considering other related <bindings>. The function may indirectly
  add additional binding values as a side effect of attempting to access
  other values that have lazy initializers, thus the functions should not
  form a cycle.

  Bindings are typically collected and assembled by a
  ConfigurationBindingsBuilder.
  """

  @property
  def config_parser(self):
    """Returns the underlying ConfigParser."""
    return self.__config_parser

  @property
  def overrides(self):
    """Returns the underlying overrides dictionary."""
    return self.__overrides

  def __init__(self, config_parser, overrides,
               lazy_initializers=None, defaults=None, section=None):
    """Construct a bindings instance.

    Args:
      config_parser: [ConfigParser] Retrieves values from configuration files.
      overrides: [dict] Values that override anything found in config_parser.
      lazy_initializers: [dict] Values that are initialized on demand.
      defaults[dict]: Default values if not otherwise determined.
      section: [string] Section to constrain ConfigParser to.
    """
    self.__config_parser = config_parser
    self.__overrides = overrides or {}
    self.__lazy_initializers = lazy_initializers or {}
    self.__defaults = defaults or {}
    self.__section = section

  def __str__(self):
    return self.__to_string(False)

  def __repr__(self):
    return self.__to_string(True)

  def __to_string(self, lazy_eval):
    configs = {}
    for section in self.__config_parser.sections():
      values = {key: self.__config_parser.get(section, key)
                for key in self.__config_parser.options(section)}
      configs[section] = values

    parts = [
        'configs={!r}'.format(configs),
        'config_defaults={!r}'.format(self.__config_parser.defaults()),
        'overrides={!r}'.format(self.__overrides),
        'lazy={!r}'.format({key: self.__lazy_initializers[key](self, key)
                                 if lazy_eval
                                 else self.__lazy_initializers[key]
                            for key in self.__lazy_initializers.keys()}),
        'defaults={!r}'.format(self.__defaults)]
    return ' '.join(parts)

  def add_lazy_initializer(self, key, initializer):
    """Add to the existing lazy initializers.

    Args:
      key: [string] The key to add (or replace)
      initializer: [callable] The initializer.
    """
    normalized_key = _normalize_key(key)
    if (self.__overrides.get(normalized_key) is None
        and normalized_key in self.__overrides):
      del(self.__overrides[normalized_key])

    self.__lazy_initializers[normalized_key] = initializer

  def get_section_bindings(self, section):
    """Returns a new instance restrained to a particular section.

    Args:
      section: [string] The section in the configuration files to restrict to.
    """
    return ConfigurationBindings(
        self.__config_parser, overrides=self.__overrides,
        lazy_initializers=self.__lazy_initializers, section=section)

  def __setitem__(self, name, value):
    """Override a binding values."""
    self.__overrides[_normalize_key(name)] = value

  def __contains__(self, name):
    """Determine if a binding name is defined."""

    key = _normalize_key(name)
    if (key in self.__overrides
        or key in self.__lazy_initializers
        or key in self.__defaults
        or key in self.__config_parser.defaults()):
      return True

    all_sections = ([self.__section]
                    if self.__section
                    else self.__config_parser.sections())
    if not all_sections:
      all_sections = [ConfigParser.DEFAULTSECT]

    for section in all_sections:
      if self.__config_parser.has_option(section, key):
        return True
    return False

  def __getitem__(self, name):
    """Retrieve a binding value."""
    have = self._do_get(name, None)
    if have is None and not self.__contains__(name):
      raise KeyError(name)
    return have

  def get(self, name, default_value=None):
    """Retrieve a binding value or default."""
    return self._do_get(name, default_value)

  def _do_get(self, name, default_value):
    """Helper function for looking up binding values.

    Args:
      name: [string] The name of the binding will be normalized internally.
      default_value: [string] The value to return if not otherwise found.

    Returns:
      The binding value as either an override, config_value or default value.
      Config values will come from the first section it is found in (or the
      specific section this instance was configured for).
    """
    key = _normalize_key(name)
    if key in self.__overrides:
      return self.__overrides[key]

    all_sections = ([self.__section]
                    if self.__section
                    else self.__config_parser.sections())
    if not all_sections:
      all_sections = [ConfigParser.DEFAULTSECT]

    for section in all_sections:
      if self.__config_parser.has_option(section, key):
        return self.__config_parser.get(section, key) or default_value

    lazy_init = self.__lazy_initializers.get(key)
    if lazy_init is not None:
      lazy_value = lazy_init(self, key)
      if lazy_value is not None:
        self.__overrides[key] = lazy_value
        return lazy_value

    if key in self.__config_parser.defaults():
      return self.__config_parser.defaults()[key]

    return self.__defaults.get(key, default_value)


class ConfigurationBindingsBuilder(object):
  """Builds a ConfigurationBindings instance."""

  @property
  def defaults(self):
    """The default values to use if not explicitly found in a file."""
    return self.__defaults

  @property
  def overrides(self):
    """Explicit values to use regardless of being in a config file or not."""
    return self.__overrides

  @overrides.setter
  def overrides(self, overrides):
    """Replace all the overrides with the ones given."""
    self.__overrides = {}
    if overrides:
      self.update_overrides(overrides)

  @property
  def lazy_initializers(self):
    """Lazy initialization functions for specific keys. See class for more info.

    Returns:
      dictionary keyed by lazy key value whose value is the initialization
      function in the form
         value = func(bindings, key)
      See class for more info about func
    """
    return self.__lazy_initializers

  def __init__(self, **kwargs):
    self.__config_files = list(kwargs.pop('default_config_files', []))
    self.__defaults = dict(kwargs.pop('defaults', {}))
    self.__overrides = dict(kwargs.pop('overrides', {}))
    self.__kwargs = copy.deepcopy(kwargs)
    self.__visited_for_config = set([])
    self.__arguments = []
    self.__lazy_initializers = {}

    # These dummies are used for validation purposes at the point of API calls.
    # The final build() will recreate the parsers from scratch so they run
    # using the final configuration state at the time of the build() call.
    self.__dummy_arg_parser = argparse.ArgumentParser()
    self.__dummy_config_parser = ConfigParser.RawConfigParser()
    if self.__config_files:
      self.__dummy_config_parser.read(self.__config_files)

  def add_argument(self, name, **kwargs):
    """Add a command-line argument.

    The default value given for the command-line argument will be added
    to the ConfigParser defaults.

    Args:
      name: [string] The name of the flag as used by argparse.
      kwargs: [kwargs] Extra parameters to pass to argparse.
    """
    default_value = kwargs.get('default', None)
    if default_value:
      key = name
      if key.startswith('--'):
        key = key[2:]
      self.set_default(key, default_value)

    self.__dummy_arg_parser.add_argument(name, **kwargs) # check
    self.__arguments.append((name, copy.deepcopy(kwargs)))

  def set_default(self, name, value):
    """Sets a default binding."""
    self.__defaults[_normalize_key(name)] = value

  def update_defaults(self, default_values):
    """Add a collection of default values.

    Args:
      default_values: [dict]  All the default values to add.
    """
    self.__defaults.update({_normalize_key(name): value
                            for name, value in default_values.items()})

  def set_override(self, name, value):
    """Overrides a binding."""
    self.__overrides[_normalize_key(name)] = value

  def update_overrides(self, values):
    """Add a collection of overriden values.

    Args:
      values: [dict]  All the values to override.
    """
    self.__overrides.update({_normalize_key(name): value
                             for name, value in values.items()})

  def add_lazy_initializer(self, name, func):
    """Adds a lazy initialization function for a bindings.

    The lazy function will only be called if the binding is requested
    but value not yet known. It will not be needed if the value has
    been provided through some other means, such as a command-line argument
    or an override.

    Args:
      name: [string] The key for the initializer.
      func: [value (bindings, key)] function.
    """
    normalized_key = _normalize_key(name)
    if (self.__overrides.get(normalized_key) is None
        and normalized_key in self.__overrides):
      del self.__overrides[normalized_key]
    self.__lazy_initializers[normalized_key] = func

  def update_lazy_initializers(self, values):
    """Add a collection of lazy initializers.

    Args:
      values: [dict]  All the lazy initializers to add.
    """
    self.__lazy_initializers.update({_normalize_key(name): value
                                     for name, value in values.items()})

  def add_config_file(self, path):
    """Explicitly add a configuration file to the bindings.

    This is a lazy call. The bindings will be read on build().
    """
    self.__config_files.append(path)
    self.__dummy_config_parser.read([path]) # only to eagerly discover errors.

  def __is_config_name(self, config_parser, key):
    """Determine if a normalized key is a known configuration value.

    Args:
      config_parser: [ConfigParser] Knows about options.
      key: [string] Normalized key.
    """
    if key in self.__defaults or key in self.__overrides:
      return True
    for section in config_parser.sections():
      if key in config_parser.options(section):
        return True
    return False

  def __infer_options(self, config_parser, extra):
    """Add bindings inferred from unexpected command-line arguments.

    Args:
      config_parser: [ConfigParser] Knows about options.
      extra: [list of string] Extra arguments from parsing command line.
    """

    result = {}
    values = []
    name = None

    for param in extra:
      if not param.startswith('--'):
        values.append(param)
        continue

      # Write previous entry now that we've seen the value(s).
      #
      # Consider only when self.__is_config_name(config_parser, name).
      # For the time being, we will be conservative and accept anything
      # to reduce the chance that we break existing code as we try to
      # be backward compatible.
      if name:
        if not values:
          values = ['True']
        if len(values) == 1:
          result[name] = values[0]
        else:
          result[name] = values

      # Start next entry.
      param_parts = param[2:].split('=', 1)
      name = _normalize_key(param_parts[0])
      values = []
      if len(param_parts) == 2:
        values = param_parts[1:2]

    if True or self.__is_config_name(config_parser, name):
      if not values:
        values = ['True']
      if len(values) == 1:
        result[name] = values[0]
      else:
        result[name] = values

    return result

  def build(self, section=None, infer=True):
    """Builds a new ConfigurationBindings instance."""
    parser = argparse.ArgumentParser()
    for arg in self.__arguments:
      parser.add_argument(arg[0], **arg[1])
    options = parser.parse_known_args()

    config_parser = ConfigParser.RawConfigParser()
    config_parser.read(self.__config_files)
    flags = {}
    flags.update(vars(options[0]))
    extra = options[1]
    if infer and extra:
      flags.update(self.__infer_options(config_parser, extra))
    flags.update({key.lower(): value
                  for key, value in self.__overrides.items()})

    bindings = ConfigurationBindings(
        config_parser, overrides=flags,
        lazy_initializers=self.__lazy_initializers,
        defaults=self.__defaults,
        section=section)
    return bindings

  def _exists(self, path):
    """Helper function to determine if a path exists to facilitate testing."""
    return os.path.exists(path)

  def __add_configs_for_name(self, name, location, dirs, accumulator):
    """Find zero or more config files for the given entity name.

    Args:
      name: [string] The basename of the entity to locate config for.
      location: [string] The path where the entity is located.
      dirs: [string] Other standard paths to look in.
      accumulator: [list] The files found with highest precedence first.
    """
    config_name = name + '.config'
    all_dirs = []
    if location:
      all_dirs.append(os.path.join(location, config_name))
    all_dirs.extend([os.path.join(elem, config_name) for elem in dirs])
    for path in all_dirs:
      if self._exists(path):
        accumulator.append(path)

  def add_configs_for_class(self, klass):
    """Add all the config files that the given class may use.

    This is the closure of its subclasses and modules.
    """
    name = klass.__name__
    if name in self.__visited_for_config:
      return
    self.__visited_for_config.add(name)

    found_list = []
    location = os.path.dirname(inspect.getfile(klass))
    dirs = ['.', os.path.join(os.path.expanduser('~'), '.citest')]
    self.__add_configs_for_name(name, location, dirs, found_list)

    package_parts = klass.__module__.split('.')
    module = package_parts[-1]
    self.__add_configs_for_name(module, location, dirs, found_list)

    package_paths = []
    package = '.'.join(package_parts[:-1]) if len(package_parts) > 1 else None

    while package and not package in self.__visited_for_config:
      parts = package.split('.')
      package_path = os.path.join(location, '__package__.config')
      if not package_path in self.__visited_for_config:
        self.__visited_for_config.add(package_path)
        if os.path.exists(package_path):
          package_paths.append(package_path)

      self.__add_configs_for_name(parts[0], location, [], found_list)
      self.__add_configs_for_name(package, None, dirs, found_list)
      package = '.'.join(parts[:-1]) if len(parts) > 1 else None
      location = os.path.dirname(location)
    found_list.extend(package_paths)

    # Add in reverse order so highest precedence is last.
    self.__config_files.extend(found_list[::-1])
