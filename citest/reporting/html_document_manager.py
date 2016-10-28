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


"""This module provides routines to help generate HTML documents.

This module focuses on structural aspects and general look and feel.
The renderer module handles more of the data encoding and type specific things.
"""

import cgi


class MyTag(object):
  """Denotes an HTML tag and its content.

  This interface is a minimal subset of BeautifulSoup that we use on tags.
  The class is a more efficient implementation that runs in 25% of the time
  (but still about 2.5x longer than hand-constructing HTML).
  """
  # pylint: disable=too-few-public-methods

  def __init__(self, name, **kwargs):
    """Construct a tag

    Args:
      name: [string] The tag name
      kwargs: [kwargs] Optional tag key/value attributes
    """
    self.__name = name
    self.__attrs = dict(kwargs)
    self.__parts = []
    self.string = ''

  def __setitem__(self, key, value):
    """Add additional key/value attributes."""
    self.__attrs[key] = value

  def append(self, part):
    """Add additional contents (children) to a tag.

    Args:
      part: [MyTag/String/DocFragment] The thing to add.
    """
    self.__parts.append(part)

  def __str__(self):
    attributes = [' {key}="{value}"'.format(key=key, value=value)
                  for key, value in self.__attrs.items()]
    return '<{name}{attributes}>{text}{parts}</{name}>'.format(
        name=self.__name,
        attributes=''.join(attributes),
        text=self.string,
        parts=''.join([str(part) for part in self.__parts]))


class MyDocFragment(object):
  """Denotes a block of HTML text.

  This interface is a minimal subset of BeautifulSoup that we use.
  Note that unlike BeautifulSoup, we wont parse raw HTML we are given.
  Therefore we wont be able to navigate or edit the internal structure.
  However, since we are constructing the document, we shouldnt need to.

  The class is a more efficient implementation that runs in 25% of the time
  (but still about 2.5x longer than hand-constructing HTML).
  """
  def __init__(self, html):
    """Construct fragment from initial HTML.

    Args:
      html: [string] Escaped HTML text that starts the fragment.
    """
    self.__parts = [html]

  def append(self, part):
    """Add a block to the end of the current fragment.

    Args:
      part: [any]  Part should be a Tag/String/DocFragment
    """
    self.__parts.append(part)

  def __str__(self):
    return ''.join([str(part) for part in self.__parts])

  def new_tag(self, name, **kwargs):
    """Create a new tag.

    Args:
      name: [string] The tag name.
      kwargs: [kwargs] The tag attributes.
    """
    return MyTag(name, **kwargs)


class MyStringFragment(object):
  """Create a fragment from unescaped text with no additional structure.

  This corresponds to NavigableText.
  """
  # pylint: disable=too-few-public-methods

  def __init__(self, text):
    self.__html = cgi.escape(text)

  def __eq__(self, value):
    return self.__html == value

  def __str__(self):
    return self.__html

  def __nonzero__(self):
    return True if self.__html else False


# This is a javascript block that will go into each HTML file.
# It defines the toggle_visibility function used to display/hide elements.
_BUILTIN_JAVASCRIPT = """
function expand_tree(node, expand) {
  if (node && node.id) {
    if (node.id.endsWith('.0')) {
       if (expand){
          if (node.style.display != 'none') {
             node.style.display = 'none'
          }
       } else {
          if (node.style.display != 'inline') {
             node.style.display = 'inline'
          }
       }
    } else if (node.id.endsWith('.1')) {
       if (expand){
          if (node.style.display != 'inline') {
             node.style.display = 'inline'
          }
       } else {
          if (node.style.display != 'none') {
             node.style.display = 'none'
          }
       }
    }
  }

  node = node.firstChild;
  while (node) {
    expand_tree(node, expand)
    node = node.nextSibling;
  }
}

function toggle_inline_visibility(id) {
  var e = document.getElementById(id);
  if (e.style.display == 'none')
    e.style.display = 'inline';
  else
    e.style.display = 'none';
 }

function toggle_inline(id) {
 toggle_inline_visibility(id + '.0')
 toggle_inline_visibility(id + '.1')
}
"""


# This is a CSS stylesheet that will go into each HTML file.
# It defines the styles that we'll use when rendering the HTML.
_BUILTIN_CSS = """
  ff { display:inline; font-family:monospace; white-space:pre; padding:8px }
  padded { padding:8px }
  context0 { font-weight:bold; white-space:pre; font-size:10pt; padding:0.3em }
  context1 { font-weight:bold; white-space:pre; font-size:8pt; padding:0.3em }
  body { font-size:10pt }
  table { font-size:8pt;border-width:none;
          border-spacing:0px;border-color:#F8F8F8;border-style:solid }
  th, td { padding:2px;vertical-align:top;
           border-width:1px;border-color:#F8F8F8;border-style:solid; }
  th { font-weight:bold;text-align:left;font-family:times }
  th { color:#666666 }
  th.nw, td.nw { white-space:nowrap }
  a, a.toggle:link, a.toggle:visited {
      background-color:#FFFFFF;color:#000099 }
  a.toggle:hover, a.toggle:active {
      color:#FFFFFF;background-color:#000099 }
  pre { margin:0; background-color:inherit }
  div.valid, div.invalid, div.error,
  span.valid, span.invalid, span.error { padding:0.3em }
  div.title { font-weight:bold; font-size:14pt;
              color:white; background-color:black;
              text-align:left; font-family:arial;
              padding:0.3em; margin-bottom:0.5em; }
  th.error { color:#FFEEEE; background-color:#990033 }
  *.error { background-color:#FFEEEE; color:#990033 }
  th.data { color:#fffae3; background-color:#996633 }
  *.data { background-color:#fffae3; color:#996633 }
  th.input { color:#efefff; background-color:#000099 }
  *.input { background-color:#efefff; color:#000099 }
  th.output { color:#d7d7ff; background-color:#000099 }
  *.output { background-color:#d7d7ff; color:#000099 }
  th.control { color:#f1cbff; background-color:#660099 }
  *.control { background-color:#f1cbff; color:#660099 }
  th.mechanism { color:#dabcff; background-color:#663399 }
  *.mechanism { background-color:#dabcff; color:#663399 }
  th.valid { color:#CCFFCC; background-color:#009900 }
  *.valid { background-color:#CCFFCC; color:#006600 }
  th.invalid { color:#FFCCCC; background-color:#CC0000 }
  *.invalid { background-color:#FFCCCC; color:#CC0000 }
"""


class HtmlDocumentManager(object):
  """Helper class for organizing and rendering documents."""

  def __init__(self, title):
    """Constructor.

    Args:
      title: [string] Title to give the HTML document when rendered.
    """
    self.has_global_expand = True
    self.has_key = True
    self.__section_count = 0
    self.__title = title
    self.__body_tags = []
    self.__string_factory = MyStringFragment
    self.__tag_factory = MyTag
    self.__fragment_factory = MyDocFragment

    # The BeautifulSoup implementation would like this:
    # self.__tag_factory = self.__doc.new_tag
    # self.__string_factory = NavigableString
    # self.__fragment_factory = lambda html : BeautifulSoup(html, 'html.parser')


  def new_section_id(self):
    """Allocates a new HTML name used to reference its CSS from javascript."""
    self.__section_count += 1
    return 'S{0}'.format(self.__section_count)

  # Map part relation to the CSS style to render it with.
  # Only special relations change the style. Otherwise the style
  # is inherited from its scope.
  _RELATION_TO_TD_CSS = {
      'ERROR': 'error',
      'VALID': 'valid',
      'INVALID': 'invalid',
      'DATA': 'data',
      'INPUT': 'input',
      'OUTPUT': 'output',
      'CONTROL': 'control',
      'MECHANISM': 'mechanism'
  }

  # Map part relation to the CSS style to render the label with.
  # Only special relations change the style. Otherwise the style
  # is inherited from its scope.
  _RELATION_TO_TH_CSS = {
      'DATA': 'data',
      'MECHANISM': 'mechanism',
      'CONTROL': 'control',
      'INPUT': 'input',
      'OUTPUT': 'output',
      'ERROR': 'error',
      'VALID': 'valid',
      'INVALID': 'invalid',
  }

  @staticmethod
  def determine_css_kwargs(style_dict, key):
    """Returns kwargs for HTML tag using the CSS style in style_dict.

    Args:
      style_dict: [dict] Values are CSS style names.
      key: [string] The key to lookup in the dictionary.

    Returns:
      A dictionary containing keyword args for tag creation that specify CSS.
    """
    style = style_dict.get(key, None)
    return {'class_': style} if style else {}

  def make_html_block(self, html):
    """Returns a block from existing HTML text."""
    return None if html is None else self.__fragment_factory(html)

  def make_text_block(self, text):
    """Returns a block from unescaped text."""
    return None if text is None else self.__string_factory(text)

  def new_tag(self, tag, class_=None, **kwargs):
    """Returns a new tag.

    Args:
      tag: [string] The tag name.
      class_: [string] If not none, the tag's CSS 'class' attribute.
      kwargs: [kwargs] Additional tag attributes to pass through.
    """
    tag = self.__tag_factory(tag, **kwargs)
    if class_ is not None:
      tag['class'] = class_
    return tag

  def make_tag_html(self, tag, html, class_=None, **kwargs):
    """Returns a new tag with html content.

    Args:
      tag: [string] The tag name.
      html: [string] HTML content for the tag.
      class_: [string] If not none, the tag's CSS 'class' attribute.
      kwargs: [kwargs] Additional tag attributes to pass through.
    """
    tag = self.new_tag(tag, class_=class_, **kwargs)
    tag.append(self.make_html_block(html))
    return tag

  def make_tag_text(self, tag, text, class_=None, **kwargs):
    """Returns a new tag with html content.

    Args:
      tag: [string] The tag name.
      text: [string] Unescaped text content for the tag.
      class_: [string] If not none, the tag's CSS 'class' attribute.
      kwargs: [kwargs] Additional tag attributes to pass through.
    """
    tag = self.new_tag(tag, class_=class_, **kwargs)
    tag.string = cgi.escape(text)
    return tag

  def make_tag_container(self, tag, children, class_=None, **kwargs):
    """Returns a new tag wrapped around existing tags or blocks.

    Args:
      tag: [string] The tag name.
      children: [MyTag] tags or block content for the new tag.
      class_: [string] If not none, the tag's CSS 'class' attribute.
      kwargs: [kwargs] Additional tag attributes to pass through.
    """
    tag = self.new_tag(tag, class_=class_, **kwargs)
    for child in children:
      tag.append(child)
    return tag

  def determine_attribute_css_kwargs(self, relation):
    """Determine the CSS style for a given attribute.

    Args:
      relation: The relation name
    Returns:
      pair of attribute dictionaries for TH and TD HTML tags.
    """
    return (
        self.determine_css_kwargs(self._RELATION_TO_TH_CSS, relation),
        self.determine_css_kwargs(self._RELATION_TO_TD_CSS, relation))

  def make_expandable_control_tag(self, section_id, text_html):
    """Creates the tag for the controller to toggle section visibility.

    This controller complements make_expandable_tag_attr_pair used to mark
    the on/off blocks that this will be controlling.

    Args:
      section_id: [string] The section id to control.
      text_html: [string] The html text for the control label.

    Returns:
      tag defining the controller object.
    """
    tag = self.new_tag('a', class_='toggle',
                       onclick="toggle_inline('{id}');".format(id=section_id))
    tag.append(self.__fragment_factory(text_html))
    return tag

  def make_expandable_tag_attr_kwargs_pair(self, section_id, default_expanded):
    """Creates the HTML tag attributes for blocks that toggle on and off.

    Args:
      section_id: [string] The section id to control.
      default_expanded: [bool] Whether the detail block should be expanded
         by default or left collapsed.

    Returns:
      A pair of attribute dictionaries for HTML tags containing the toggled
      content. The first is for the detail (when on), the second is for the
      summary (when off).
    """
    expanded_attrs_dict = {'id': '{id}.1'.format(id=section_id)}
    if not default_expanded:
      expanded_attrs_dict['style'] = 'display:none'

    hidden_attrs_dict = {'id': '{id}.0'.format(id=section_id)}
    if default_expanded:
      hidden_attrs_dict['style'] = 'display:none'
    return expanded_attrs_dict, hidden_attrs_dict

  def build_key_tag(self):
    """Create an HTML block documenting this HTML document's notation."""

    add_row = lambda klass, name, help: (self.make_tag_container(
        'tr', [self.make_tag_text('th', name, class_=klass),
               self.make_tag_text('td', help, class_=klass)]))

    table = self.make_tag_container('table', [
        add_row('valid', 'Good',
                'The attribute is a result value or analysis that'
                ' passed validated.'),
        add_row('invalid', 'Bad',
                'The attribute is a result value or analysis that'
                ' failed validation.'),
        add_row('error', 'Error',
                'The attribute denotes an error that was encounted,'
                ' other than a validation.'),
        add_row('data', 'Data',
                'The attribute denotes a data value that is likely'
                ' either input or output.'),
        add_row('input', 'Input',
                'The attribute denotes an input data value,'
                ' or an object that acted as an input.'),
        add_row('output', 'Output',
                'The attribute denotes an output data value,'
                ' or an object that acted as an output.'),
        add_row('control', 'Control',
                'The attribute denotes a control value used to'
                ' configure some related component.'),
        add_row('mechanism', 'Mechanism',
                'The attribute denotes a component used as a'
                ' mechanism providing behaviors to another component.')
        ])

    section_id = self.new_section_id()
    expanded_tag_attrs_dict, hidden_tag_attrs_dict = (
        self.make_expandable_tag_attr_kwargs_pair(
            section_id=section_id, default_expanded=False))

    expand_tag = self.make_tag_container(
        'div', [table], **expanded_tag_attrs_dict)

    hide_tag = self.new_tag('div', **hidden_tag_attrs_dict)
    hide_tag.append(
        self.make_expandable_control_tag(section_id, 'show key'))

    td_tag = self.new_tag('td')
    td_tag.append(self.make_expandable_control_tag(section_id, '<b>Key:</b>'))

    td_tag.append(expand_tag)
    td_tag.append(hide_tag)

    table_tag = self.new_tag('table')
    tr_tag = self.new_tag('tr')
    tr_tag.append(td_tag)
    table_tag.append(tr_tag)
    return table_tag

  def append_tag(self, tag):
    """Accumulate a tag into the document body."""
    self.__body_tags.append(tag)

  def wrap_tag(self, tag):
    """Wrap the tag around the accumulated tags, and accumulate it."""
    for child in self.__body_tags:
      tag.append(child)
    self.__body_tags = [tag]

  def build_to_path(self, output_path):
    """Builds a complete HTML document and writes it to a file.

    This assumes we already wrote a body into it with write().

    Args:
      output_path: [string] Path of file to write.
    """
    head_html = ('<title>{title}</title>\n'
                 '<script type="text/javascript">{script}</script>\n'
                 '<style>{style}</style>\n'.format(
                     title=self.__title,
                     script=_BUILTIN_JAVASCRIPT,
                     style=_BUILTIN_CSS))

    body_list = ['<div class="title">{title}</div>'.format(title=self.__title)]

    if self.has_global_expand:
      body_list.append(
          '<a href="#" onclick="expand_tree(document.body, true)">'
          'Expand All</a>'
          '&nbsp;&nbsp;&nbsp;&nbsp;'
          '<a href="#" onclick="expand_tree(document.body, false">'
          'Collapse All</a>'
          '<p/>\n')

    if self.has_key:
      body_list.append(str(self.build_key_tag()))

    for tag in self.__body_tags:
      body_list.append(str(tag))

    html = ('<!DOCTYPE html>\n'
            '<html><head>{head}</head>\n'
            '<body>{body}</body></html>'.format(
                head=head_html,
                body=''.join(body_list)))

    with open(output_path, 'w') as f:
      f.write(html)
