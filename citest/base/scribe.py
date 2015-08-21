# Copyright 2015 Google Inc. All Rights Reserved.
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

import collections
import inspect
import json
import re


"""Implements a registry and scribe to custom render class instances."""


class ScribeRendererPart(
      collections.namedtuple(
          'ScribeRendererPart',
          ['name', 'value', 'explicit_renderer', 'relation'])):
  """Holds a name/value pair for conveying structured information.

  This is intended to be used by registered renderers that return a
  structure of what to render without the actual syntax, thus giving them
  more reusability across different formats.

  Attributes:
    name: A string containing the part's display name.
    value: An object denoting the part's value.
    explicit_renderer: An explicit scribe renderer, or None to lookup the
       renderer from the Scribe when it is scribed.
    relation: The ScribePartBuilder relationship type of this part to the
       thing it is a part of. None indicates an unspecified relation.
  """
  pass


class ScribeRendererSection(object):
  """Acts as a part container to group parts together as nested structures.

  A different renderer for this class can be added to a registry to change
  how these groups are displayed.

  Attributes:
    parts: The list of ScribeRendererPart comprising the section content.
    title: The string name of the section.
  """

  @property
  def parts(self):
    return self._parts

  @property
  def title(self):
    return self._title

  def __init__(self, title=None):
    # Starting the section with an empty part will force a break,
    # especially if we render a title, so the section starts on a new line.
    # Later we strip these so that adjacent section boundries collapse
    # down to one eoln.
    self._parts = [ScribeRendererPart(None, '', Scribe.render_nothing, None)]
    self._title = title or ''

  @staticmethod
  def render(out, section):
    """Custom renderer for rendering parts in a section.

    Args:
      out: The Doodle to render to.
      section: The ScribeRendererSection to render.
    """
    out.push_level()
    try:
      return out.scribe.render_parts(out, section._parts)
    finally:
      out.pop_level()


class ScribeClassRegistryEntry(object):
  """Holds the registration info for a slot in the ScribeClassRegisry.

  Attributes:
    renderer: The callable function used to render instances.
       It takes the scribe Doodle to write to and the object to render
       and will render the object into the doodle.

    part_builder: A callable that takes the object and renderer and returns
       a list of ScribeRendererPart that can be later fed back into the scribe
       to render the values. This can be None if it is not supported.

       For registrations using part_builder, the registry can provide the
       renderer, thus allowing the registerer to write a single method that
       decomposes the structure of the data object independent of the
       formatting. This still means each format will have similar structure,
       but is still less work that providing custom renderers for each
       supported format.
  """

  @property
  def renderer(self):
    return self._renderer

  @property
  def part_builder(self):
    return self._part_builder

  def __init__(self, renderer=None, part_builder=None):
    if not renderer and not part_builder:
      raise ValueError()
    self._part_builder = part_builder
    self._renderer = renderer or self._do_render_parts

  def _do_render_parts(self, out, obj):
    scribe = out.scribe
    parts = self._part_builder(obj, scribe)
    return scribe.render_parts(out, parts)

  def __call__(self, out, obj):
    return self._renderer(out, obj)


class _BaseScribeClassRegistry(object):
  """Implements a registry of callable objects for rendering classes.

  The registry can be hierarichal to specialize renderings of some classes.
  The default registry can contain basic renderings, which can then be
  overriden for special purposes or different formats.

  When asked for a renderer, the registry will lookup the inheritence
  hierarchy of the object to be rendered and find the closest specialized
  renderer.

  This base class is intended just to implement the DEFAULT_SCRIBE_REGISTRY.
  Other custom registries derive from the ScribeRegistry specialization
  which inherits from the DEFAULT_SCRIBE_REGISTRY by default.

  Attributes:
    default_renderer: The default catch-all to use when classes are not known.
    name: The name of the registry for reporting purposes only.
  """

  @property
  def default_renderer(self):
    return self._default_renderer

  @default_renderer.setter
  def default_renderer(self, func):
    self._default_renderer = func

  @property
  def name(self):
    return self._name

  def __init__(self, name, overrides_registry=None):
    """Constructor.

    Args:
      name: The name of the registry.
      overrides_registry: Specifies the _BaseScribeClassRegistry to override,
          or None.
    """
    self._name = name
    self._registry = {}
    self._overrides_registry = overrides_registry
    self._default_renderer = (lambda out, value: out.write(repr(value)))

  def add_part_builder(self, klass, function):
    if klass in self._registry:
      raise ValueError('Class {0} already registered.'.format(
          klass.__class__.__name__))
    self._registry[klass] = ScribeClassRegistryEntry(part_builder=function)

  def add(self, klass, renderer):
    """Adds a class renderer to the registry.

    Args:
      klass: The type being registered.
      renderer: A callable returning a string, taking object to render and
          the scribe to render with. This is the renderer for the given type.
    """
    if klass in self._registry:
      raise ValueError('Class {0} already registered.'.format(
          klass.__class__.__name__))
    self._registry[klass] = ScribeClassRegistryEntry(renderer=renderer)

  def find_or_none(self, obj, search=True):
    """Returns the closest registered renderer for the given object.

    Args:
      obj: The object or type to lookup. If it is not a type, lookup its type.
      search: If no renderer is found, and search is True, fail over to the
          overriden registry chain.
    Returns:
      The registered renderer on the closest type that is found first while
          searching the registry hierarchy. For example, if this registry
          contains a base class but not the derived, and a parent registry
          contains a derived, then the base class renderer from this registry
          will be returned.

          Returns None if no renderer is found.
    """
    obj_class = obj if inspect.isclass(obj) else obj.__class__
    for klass in inspect.getmro(obj_class):
      if klass in self._registry:
        return self._registry[klass]
    if search and self._overrides_registry:
      return self._overrides_registry.find_or_none(obj, search)
    return None

  def find_with_default(self, obj, default_renderer=None, search=True):
    """Similiar to find_or_none but returns the default if not found.

    Args:
      obj: The object or type to lookup.
      default_renderer: The default to return if not found, or None to use
         the registries bound default.
      search: Whether to search the registry chain before returning the
         default. Only the default from this registry will be considered.
    """
    found = self.find_or_none(obj, search=search)
    if found:
      return found

    func = default_renderer or self._default_renderer
    if not func:
      return None
    return ScribeClassRegistryEntry(renderer=func)


class Doodle(object):
  """Object for accumulating text output.

  The doodle holds state information and and output produced by renderers.
  Ultimately it produces a chunk of text containing all the renderer output
  appended together. Doodles are used to make scribes stateless so that
  they are essentially threadsafe (the registry is not threadsafe, but is
  presumed to be read-only once the program is initialized).
  Expectation is that each thread journal its own information without being
  interleved by other threads -- especially to not have the scoping /
  indentation influenced by other threads. The thread decides when it wants
  to flush the doodle, which may require external coordination with
  other threads depending on expectations of the underlying medium produced.

  Typical usage is to pass the doodle into scribe.render as a caller,
  or receive the doodle as an argument and write text directly into it.

  Attributes:
    scribe: The scribe used to write to the doodle. It is kept here for
      convinence so only the doodle needs to be passed around.
    line_indent: Current indentation string.
    level: Numeric 'depth' of indentation levels.
    indent_factor: Number of spaces to indent per level.
  """

  @property
  def scribe(self):
    return self._scribe

  @property
  def segments(self):
    return self._segments

  @property
  def line_indent(self):
    return self._make_level_indent(self._level)

  @property
  def level(self):
    return self._level

  @property
  def indent_factor(self):
    return self._indent_factor

  @indent_factor.setter
  def indent_factor(self):
    self._indent_factor = factor

  def __init__(self, scribe):
    self._scribe = scribe
    self._level = 0
    self._indent_factor = 2
    self._segments = []

  def __str__(self):
    return ''.join(self._segments)

  def reset(self):
    """Reset the doodle back to its initial empty state.

    Presumably this is after flushing it.
    """
    self._level = 0
    self._segments = []

  def new_at_level(self):
    """Create a new empty doodle that is at the current level."""
    out = self.__class__(self._scribe)
    out._level = self._level
    out._indent_factor = self._indent_factor
    return out

  def render_to_string(self, obj, renderer=None):
    """Convienence method to render an object as a string at the current level.

    This will not write into the doodle. The instance is not affected at
    all. Rather this is a convienence method for converting an object
    to a string at the current indentation level of this doodle.
    """
    tmp = self.new_at_level()
    renderer(tmp, obj) if renderer else self.scribe.render(tmp, obj)
    return str(tmp)

  def write(self, text):
    if text:
      self._segments.append(text)

  def push_level(self, count=1):
    """Increment indentation level.

    Args:
      count: If specified, the number of levels to increment by.
    """
    if count < 0:
      raise ValueError('count={0} cannot be negative'.format(count))
    self._level += count

  def pop_level(self, count=1):
    """Decrement indentation level.

    Args:
      count: If specified, the number of levels to decrement by.
    """
    if count < 0:
      raise ValueError('count={0} cannot be negative'.format(count))
    if self._level < count:
      raise ValueError('Popped too far.')
    self._level -= count

  def _make_level_indent(self, level):
    """Helper function providing the indentation string for the given level."""
    return ' ' * level * self._indent_factor


class ScribePartBuilder(object):
  """Builds parts to be rendered by a scribe.

  This is a helper class for building parts with a scribe to prevent
  the scribe class from being overwhelmed by helper methods facilitating its
  use. Especially where these methods are typically not going to be specialized
  by particular Scribe implementations.

  The builder facilitates modeling parts having different relationships.
  The core relationships are INPUT, OUTPUT, CONTROL, MECHANISM using an
  IDEF-0 style (https://en.wikipedia.org/wiki/IDEF0) model to capture the
  general purpose of the entities.

  In practice, this isnt an ideal modeling style. For one, when we build
  a full tracability graph, the outputs of some components are the inputs of
  others, but we'll be using the same rendering methods. To compensate for
  this, we're adding a generic DATA relationship which is intended as being
  INPUT or OUTPUT but isnt that important which (the reader can infer). Also,
  the analysis components determining validation are a significant part of
  our reporting so would like to distinguish those. Since analysis is performed
  for verification purposes, we've added VALID/INVALID relationships denoting
  parts that are analysis data along with the validity conclusion of it.
  """

  ERROR='ERROR'      # Used to report errors
  VALID='VALID'      # A valid analysis (data or derived object).
  INVALID='INVALID'  # An invalid analysis (data or derived object).
  DATA='DATA'        # Typically input or output depending on perspective.
  INPUT='INPUT'      # An input parameter (data or object containing data).
  OUTPUT='OUTPUT'    # An output parameter (data or object containing data ).
  CONTROL='CONTROL'  # A configuration/control parameter (data).
  MECHANISM='MECHANISM'  # A mechanism that was used (component).

  def __init__(self, scribe):
    """Construct a part builder helper.

    Args:
      scribe: The Scribe this is helping serves as the actual part factory.
    """
    self._scribe = scribe

  def determine_verified_relation(self, obj):
    return self.VALID if obj else self.INVALID

  def build_data_part(self, name, value, renderer=None, summary=None):
    return self.build_nested_part(
        name, value,
        renderer=renderer, summary=summary, relation=self.DATA)

  def build_input_part(self, name, value, renderer=None, summary=None):
    return self.build_nested_part(
        name, value,
        renderer=renderer, summary=summary, relation=self.INPUT)

  def build_output_part(self, name, value, renderer=None, summary=None):
    return self.build_nested_part(
        name, value,
        renderer=renderer, summary=summary, relation=self.OUTPUT)

  def build_control_part(self, name, value, renderer=None, summary=None):
    return self.build_nested_part(
        name, value,
        renderer=renderer, summary=summary, relation=self.CONTROL)

  def build_mechanism_part(self, name, value, renderer=None, summary=None):
    return self.build_nested_part(
        name, value,
        renderer=renderer, summary=summary, relation=self.MECHANISM)

  def build_nested_part(self, name, value, renderer=None,
                        summary=None, relation=None):
    scribe = self._scribe
    if inspect.isclass(summary):
      summary = summary.__name__
    section = scribe.make_section(title=summary)
    if isinstance(value, list):
      if not value:
        section.parts.append(scribe.build_part(None, scribe.empty_list))
      else:
        for elem in value:
          section.parts.append(
              scribe.build_part(None, elem, renderer=renderer))
    else:
      section.parts.append(scribe.build_part(None, value, renderer=renderer))

    return scribe.build_part(name, section, relation=relation)


class Scribe(object):
  """Renders custom strings using a ScribeClassRegistry.

  Attributes:
    registry: Bound ScribeClassRegistry used to lookup renderers.
    part_builder: Contains helper functions for defining parts of a composed
        data model.
  """

  @property
  def empty_list(self):
    return '<empty list>'

  @property
  def registry(self):
    return self._registry

  @property
  def part_builder(self):
    return self._part_builder

  def __init__(self, registry=None):
    """Constructor

    Args:
      registry: The ScribeClassRegistry to bind. If None use the default.
    """
    self._registry = registry or DEFAULT_SCRIBE_REGISTRY
    self._part_builder = ScribePartBuilder(self)

  def render_to_string(self, obj, default_renderer=None):
    out = Doodle(self)
    self.render(out, obj, default_renderer)
    return str(out)

  def render_parts_to_string(self, parts):
    out = Doodle(self)
    self.render_parts(out, parts)
    return str(out)

  def render(self, out, obj, default_renderer=None):
    """Render the given object by calling its registered renderer.

    Args:
     out: The Doodle to render to.
     obj: The object to render.
     unknown: If there is no renderer, and unknown is provided, return that.
    """
    default_renderer = default_renderer or self._registry.default_renderer
    renderer = self._registry.find_with_default(obj, default_renderer)
    orig_level = out.level
    try:
      renderer(out, obj)
    finally:
      to_pop = out.level - orig_level
      if to_pop:
        out.pop_level(count=to_pop)

  def render_classname(self, out, obj):
    """Renders the class of the given object."""
    out.write('CLASS {0}'.format(obj.__class__.__name__))

  def render_part(self, out, part):
    """Renders an individual ScribeRegistererPart.

    This method can be overwritten to change the presentation of individual
    items. If the registry also registers a custom renderer for
    ScribeRegistererSection then it can control the presentation of the overall
    structure.

    Args:
      out: The Doodle to render to.
      part: The ScribeRegistererPart to render.
    """

    part_out = out.new_at_level()
    if part.explicit_renderer:
      part.explicit_renderer(part_out, part.value)
    else:
      self.render(part_out, part.value)

    part_segments = part_out.segments
    if part.name and part_segments:
      sep = '' if part_segments[0][0].isspace() else ' '
      out.write('{0}:{1}{2}'.format(part.name, sep, part_out))
    elif part.name:
      out.write('{0}:'.format(part.name))
    else:
      out.write(str(part_out))

  def render_parts(self, out, parts):
    """Renders an sequence of ScribeRegistererPart.

    Args:
      out: The Doodle to render to.
      parts: A list of ScribeRegistererPart.
    """
    sep = ''
    for part in parts:
      out.write(sep)
      self.render_part(out, part)
      sep = '\n{0}'.format(out.line_indent)

  def build_classname_parts(self, obj):
    """Returns a ScribeRegistererPart for rendering an objects class name."""
    return [self.build_part('CLASS', obj.__class__.__name__)]

  def build_part(self, name, value, renderer=None, relation=None):
    """ScribeRendererPart factory."""
    return ScribeRendererPart(name, value, renderer, relation)

  def build_json_part(self, name, value, relation=None, summary=None):
    """ScribeRendererPart factory using render_json_if_possible."""
    return self._part_builder.build_nested_part(
        name, value, renderer=self.render_json_if_possible,
        summary=summary, relation=relation)

  def make_object_count_summary(self, obj, subject='object', plural='s'):
    count = 0 if not obj else len(obj)
    if count == 1:
      plural = ''
    return '{count} {subject}{plural}'.format(
        count=count, subject=subject, plural=plural)

  def make_section(self, title=None):
    """ScribeRendererSection factory."""
    return ScribeRendererSection(title=title)

  @classmethod
  def render_json_if_possible(cls, out, obj):
    """Method for rendering objects as json, if the object is valid json.

    If the object is not valid json then just return the string.
    """
    try:
      if isinstance(obj, basestring):
        tmp = json.JSONDecoder().decode(obj)
        text = json.JSONEncoder(indent=out.indent_factor,
                                separators=(',', ': ')).encode(tmp)
      else:
        text = json.JSONEncoder(indent=out.indent_factor,
                                separators=(',', ': ')).encode(obj)
    except (ValueError, UnicodeEncodeError):
      out.write(repr(obj))
      return

    # json doesnt give a leading indent level, so we'll add that ourselves
    # so that the whole result can be placed within the callers indent level.
    return out.write(text.replace('\n', '\n{0}'.format(out.line_indent)))

  @classmethod
  def render_nothing(cls, out, obj):
    """Renders empty string without going through encoding."""
    pass

  @classmethod
  def render_list_elements(cls, out, obj):
    """Method for rendering lists.

    Args:
       out: The Doodle to render to.
       obj: The list to render.
    """
    sep = ''
    scribe = out.scribe
    for elem in obj:
      out.write(sep)
      scribe.render(out, elem)
      sep = ', '

  @staticmethod
  def identity_renderer(out, value):
    out.write(value)

  @staticmethod
  def render_list_elements_hook(out, obj):
    """Renderer for list objects."""
    return out.scribe.__class__.render_list_elements(out, obj)


class Scribable(object):
  """A mixin class to facilitate supporting scribes using ScribeRendererPart.

  The derived classes could be registered with this class's build_scribe_parts
  method, then override the _make_scribe_parts method for themselves.
  """

  @staticmethod
  def build_scribe_parts(scribable, scribe):
    """Scribe the scribable object using individual ScribeRendererParts.

    Derived classes should override _make_scribe_parts for this to be useful.
    This method will inject a class identification at the beginning of the
    parts.

    Args:
      scribable: The object to render should be derived from this class
      scribe: The Scribe to scribe the scribable with.

    Returns:
      A list of ScribeRendererPart to be rendered.
    """
    section = scribe.make_section()
    section.parts.extend(scribable._make_scribe_parts(scribe))
    parts = scribe.build_classname_parts(scribable)
    parts.append(scribe.build_part(None, section))
    return parts

  def _make_scribe_parts(self, scribe):
    """Default implementation of make_scribe_parts.

    Specialized classes should override this.
    The default implementation just gets our default string representation.

    Returns:
      A list of ScribeRendererPart to be rendered.
    """
    return [scribe.build_part(None, str(self))]


DEFAULT_SCRIBE_REGISTRY = _BaseScribeClassRegistry(
    'Default', overrides_registry=None)

# Add a basic section renderer into the default registry.
# This can still be overriden for specialized registries.
DEFAULT_SCRIBE_REGISTRY.add(
    ScribeRendererSection, ScribeRendererSection.render)

# Registry Scribable mixin so anything using it is implicitly registered.
DEFAULT_SCRIBE_REGISTRY.add_part_builder(
    Scribable, Scribable.build_scribe_parts)

# Adds a list renderer that enumerates over the individual elements
# and renders them in a comma-separated list (using registered renderers).
DEFAULT_SCRIBE_REGISTRY.add(
    list, Scribe.render_list_elements_hook)


class ScribeClassRegistry(_BaseScribeClassRegistry):
  """Base class for creating custom registries."""
  def __init__(self, name, overrides_registry=DEFAULT_SCRIBE_REGISTRY):
    super(ScribeClassRegistry, self).__init__(name, overrides_registry)


DETAIL_SCRIBE_REGISTRY = ScribeClassRegistry('Detail')
