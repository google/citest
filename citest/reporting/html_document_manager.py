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


# This is a javascript block that will go into each HTML file.
# It defines the toggle_visibility function used to display/hide elements.
_BUILTIN_JAVASCRIPT = """
<script type='text/javascript'>
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
</script>
"""


# This is a CSS stylesheet that will go into each HTML file.
# It defines the styles that we'll use when rendering the HTML.
_BUILTIN_CSS = """
<style>
  ff { display:inline; font-family:monospace; white-space:pre }
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
  pre { margin: 0 }
  div.valid, div.invalid, div.error,
  span.valid, span.invalid, span.error { padding:0.3em }
  div.fodder { font-size:8pt; }
  div.title { font-weight:bold; font-size:14pt;
              text-align:center; font-family:arial; margin:0 0 30pt 0 }
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
</style>
"""


class HtmlDocumentManager(object):
  """Helper class for organizing and rendering documents."""

  def __init__(self, title):
    """Constructor.

    Args:
      title: [string] Title to give the HTML document when rendered.
    """
    self.__section_count = 0
    self.__title = title
    self.__parts = []

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
  def determine_css_decorator(style_dict, key):
    """Returns decorator string for HTML tag using the CSS style in style_dict.

    Args:
      style_dict: [dict] Values are CSS style names.
      key: [string] The key to lookup in the dictionary.

    Returns:
      An HTML tag class attribute binding, or empty string if key not found.
    """
    style = style_dict.get(key, None)
    return ' class="{0}"'.format(style) if style else ''

  def determine_attribute_css(self, relation):
    """Determine the CSS style for a given attribute.

    Args:
      relation: The relation name
    Returns:
      pair of attribute decorators for TH and TD HTML tags.
    """
    return (
        self.determine_css_decorator(self._RELATION_TO_TH_CSS, relation),
        self.determine_css_decorator(self._RELATION_TO_TD_CSS, relation))

  def make_expandable_control_for_section_id(self, section_id, text_html):
    """Creates the HTML for the controller to toggle section visibility.

    This controller complements make_expandable_tag_attr_pair used to mark
    the on/off blocks that this will be controlling.

    Args:
      section_id: [string] The section id to control.
      text_html: [string] The html text for the control label.

    Returns:
      HTML encoding of the controller object.
    """
    fragments = [
        '<a class="toggle" onclick="toggle_inline(\'{id}\');">'.format(
            id=section_id),
        text_html,
        '</a>']
    return ''.join(fragments)

  def make_expandable_tag_attr_pair(self, section_id, default_expanded):
    """Creates the HTML tag attributes for blocks that toggle on and off.

    Args:
      section_id: [string] The section id to control.
      default_expanded: [bool] Whether the detail block should be expanded
         by default or left collapsed.

    Returns:
      A pair of attributes to decorate the HTML tags containing the toggled
      content. The first is for the detail (when on), the second is for the
      summary (when off).
    """
    expanded_tag_attrs = ' id="{id}.1"{visibility}'.format(
        id=section_id,
        visibility='' if default_expanded else ' style="display:none"')
    hidden_tag_attrs = ' id="{id}.0"{visibility}'.format(
        id=section_id,
        visibility='' if not default_expanded else ' style="display:none"')
    return ''.join(expanded_tag_attrs), ''.join(hidden_tag_attrs)

  def build_key_html(self):
    """Create an HTML block documenting this HTML document's notation."""

    table_html = """<table>
  <tr><th class="valid">Good</th>
      <td class="valid">The attribute is a result value or analysis that passed validated</td>
  <tr><th class="invalid">Bad</th>
      <td class="invalid">The attribute is a result value or analysis that failed validation</td>
  <tr><th class="error">Error</th>
      <td class="error">The attribute denotes an error that was encounted, other than a validation</td>
  <tr><th class="data">Data</th>
      <td class="data">The attribute denotes a data value that is likely either input or output.</td>
  <tr><th class="input">Input</th>
      <td class="input">The attribute denotes an input data value, or an object that acted as an input.</td>
  <tr><th class="output">Output</th>
      <td class="output">The attribute denotes an output data value, or an object that acted as an output.</td>
  <tr><th class="control">Control</th>
      <td class="control">The attribute denotes a control value used to configure some related component.</td>
  <tr><th class="mechanism">Mechanism</th>
      <td class="mechanism">The attribute denotes a component used as a mechanism providing behaviors to another component.</td>
</table>
"""
    section_id = self.new_section_id()
    control = self.make_expandable_control_for_section_id(
        section_id, '<b>Key:</b>')
    summary_html = self.make_expandable_control_for_section_id(
        section_id, 'show key')
    expanded_tag_attrs, hidden_tag_attrs = self.make_expandable_tag_attr_pair(
        section_id=section_id, default_expanded=False)

    indent = ''
    table_indent = '  '
    lines = [
        '{indent}<table><tr>'.format(indent=indent),
        '{indent}<td>{control}<td>'.format(indent=indent, control=control),
        '{indent}<div {attrs}>'.format(indent=indent,
                                       attrs=expanded_tag_attrs),
        '{indent}{table}'.format(indent=table_indent, table=table_html),
        '{indent}</div>'.format(indent=indent),
        '{indent}<div {attrs}>'.format(indent=indent, attrs=hidden_tag_attrs),
        '{indent}{summary}'.format(indent=table_indent, summary=summary_html),
        '{indent}</div>'.format(indent=indent),
        '{indent}</table>\n'.format(indent=indent)]
    return '\n'.join(lines)

  def build_html_head_block(self, title):
    """Builds text for the HTML HEAD section.

    The HEAD section will contain the standard Javascript and CSS used within.

    Args:
      title: [string] The unescaped text title of HTML will be escaped.
    """
    return '<head><title>{title}</title>{javascript}{css}</head>\n'.format(
        javascript=_BUILTIN_JAVASCRIPT,
        css=_BUILTIN_CSS,
        title=cgi.escape(title))

  def build_begin_html_document(self, title):
    """Builds the start of an html document up to the openening BODY tag.

    Args:
      title: [string] The unescaped text title of HTML will be escaped.
    """
    fragments = [
        '<!DOCTYPE html>\n',
        '<html>\n',
        self.build_html_head_block(title),
        '<body>\n']
    return ''.join(fragments)

  def build_end_html_document(self):
    """Writes the closing of the HTML document BODY and HTML tags."""
    return '</body>\n</html>'

  def write(self, html):
    """Writes some html into the document body."""
    self.__parts.append(html)

  def build_to_path(self, output_path):
    """Builds a complete HTML document and writes it to a file.

    This assumes we already wrote a body into it with write().

    Args:
      output_path: [string] Path of file to write.
    """
    with open(output_path, 'w') as f:
      f.write(self.build_begin_html_document(self.__title))
      f.write(
          '<a href="#" onclick="expand_tree(document.body,true)">'
          'Expand All</a>')
      f.write('&nbsp;&nbsp;&nbsp;')
      f.write(
          '<a href="#" onclick="expand_tree(document.body,false)">'
          'Collapse All</a>')
      f.write('\n<p/>\n')
      f.write(self.build_key_html())
      f.write(''.join(self.__parts))
      f.write(self.build_end_html_document())
