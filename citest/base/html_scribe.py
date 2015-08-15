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

import re
import sys
import traceback

from . import scribe as scribe_module


HTML_SCRIBE_REGISTRY = scribe_module.ScribeClassRegistry('html')


# This is a javascript block that will go into each HTML file.
# It defines the toggle_visibility function used to display/hide elements.
_javascript = """
<script type='text/javascript'>
function toggle_visibility(id) {
  var e = document.getElementById(id);
  if (e.style.display == 'none')
    e.style.display = 'block';
  else
    e.style.display = 'none';
 }
</script>
"""


# This is a CSS stylesheet that will go into each HTML file.
# It defines the styles that we'll use when rendering the HTML.
_css = """
<style>
  body { font-size:10pt }
  table { font-size:8pt;border-width:none;
          border-spacing:0px;border-color:#F8F8F8;border-style:solid }
  th, td { padding:2px;vertical-align:top;
           border-width:1px;border-color:#F8F8F8;border-style:solid; }
  th { font-weight:bold;text-align:left;font-family:times }
  th { color:#666666 }
  th.error { color:#FFEEEE; background-color:#990033 }
  th.valid { color:#CCFFCC; background-color:#009900 }
  th.invalid { color:#FFCCCC; background-color:#CC0000 }
  a, a.toggle:link, a.toggle:visited {
      background-color:#FFFFFF;color:#000099 }
  a.toggle:hover, a.toggle:active {
      color:#FFFFFF;background-color:#000099 }
  pre { margin: 0 }
  div { margin-left:1em; }
  div.fodder { font-size:8pt; }
  div.title { font-weight:bold; font-size:14pt;
              text-align:center; font-family:arial; margin:0 0 30pt 0 }
  *.error { background-color:#FFEEEE; color:#990033 }
  *.data { background-color:#fffae3; color:#996633 }
  *.input { background-color:#efefff; color:#000099 }
  *.output { background-color:#d7d7ff; color:#000099 }
  *.control { background-color:#f1cbff; color:#660099 }
  *.mechanism { background-color:#dabcff; color:#663399 }
  *.valid { background-color:#CCFFCC; color:#006600 }
  *.invalid { background-color:#FF999; color:#CC0000 }
</style>
"""


def _escape(source, quote=False):
  """Escape source string into valid HTML.

  Args:
    source: String to be escaped.
    quote: If True then also escape quote characters.
  Returns:
    Escaped HTML string.
  """
  s = source.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
  if quote:
    s = s.replace('"', '&quot').replace("'", '&apos')
  return s


def _escape_repr_renderer(obj, scribe):
  """A renderer that escapes a python object string representation into HTML.

  Args:
    obj: A python object to render as a string.
    scribe: The scribe rendering the object.

  Returns:
    Escaped string representation.
  """
  return _escape(str(obj))


def _exception_renderer(obj, scribe):
  """A renderer for exceptions as HTML.

  Args:
    obj: A python Exception to render as a string.
    scribe: The scribe rendering the object.

  Returns:
    HTML string representation.
  """
  # TODO(ewiseblatt): 20150810
  # This is assuming we're calling this from an exception handler,
  # and the one that emitted the exception at that.
  # However this could be an exception that is a property in another object.
  # in which case we probably want to wrap the exception and bundle the
  # stack at the time of the exception, and have a renderer for that.
  ex_type, ex, tb = sys.exc_info()
  preformatted_trace = _escape(''.join(traceback.format_tb(tb)))
  html = ('<div class="error">{message}<br/>\n'
          '<pre><code>{traceback}</code></pre></div>\n').format(
           message=_escape(str(obj)),
           traceback=preformatted_trace.replace('\\n', '\n'))

  return html


class HtmlScribe(scribe_module.Scribe):
  """
  Implements a scribe that renders into HTML.

  Attributes:
    next_section_id: The string ID to use to identify the next expandable
        HTML section.
  """

  @property
  def next_section_id(self):
    self._section_count += 1
    return 'S{0}'.format(self._section_count)

  def __init__(self, registry=HTML_SCRIBE_REGISTRY):
    super(HtmlScribe, self).__init__(registry)
    self._section_count = 0

  def render_html_head_block(self, title):
    """Renders text for the HTML HEAD section.

    The HEAD section will contain the standard Javascript and CSS used within.

    Args:
      title: The unescaped text title of HTML will be escaped.
    """
    return '<head><title>{title}</title>{javascript}{css}</head>\n'.format(
        javascript=_javascript, css=_css, title=_escape(title))

  def render_begin_html_document(self, title):
    """Renders a new html document up to the openening BODY tag.

    Args:
      title: The unescaped text title of the HTML.
    """
    return '\n'.join(
      ['<!DOCTYPE html>\n<html>',
       self.render_html_head_block(title),
       '<body>'])

  def render_end_html_document(self):
    """Renders the closing of the HTML document BODY and HTML tags."""
    return '\n'.join(['</body>', '</html>'])

  def render_notoggle_div(self, html, css='fodder'):
    """Renders an HTML div section that is not toggleable.

    Args:
      html: The html to render inside the DIV tag.
      css: The CSS style name to use, if any.
    """
    lines = ['<div class="{css}" style="display:block">'.format(css=css)]
    self.push_level()
    lines.append('{indent}{html}', indent=self.line_indent, html=html)
    self.pop_level()
    lines.append('{indent}</div>'.format(self.line_indent))
    return '\n'.join(lines)

  def render_expandable_content(
      self, summary_html, detail_html, detail_css, id, default_visible=True):
    """Renders an expandable DIV block.

    Args:
      summary_html: The HTML to display when the block is not expanded.
         This is also displayed to close the block when expanded.
      detail_html: This is the HTML to display when the block is expanded.
      detail_css: This is the CSS stylesheet to use for the detail_html.
      id: The javascript ID value to associate with this block must be unique
          within the document.
      default_visible: True if should be visible by default, False otherwise.
    """

    # The summary line is a link.
    lines = ['<a class="toggle"'
             ' onclick="toggle_visibility(\'{id}\');">'.format(id=id)]
    self.push_level()
    lines.append('{indent}{summary}'.format(
            indent=self.line_indent, summary=summary_html))
    self.pop_level()
    lines.append('{indent}</a><br/>'.format(indent=self.line_indent))

    # div tags are visible by default, so we only worry about hiding it.
    visibility = '' if default_visible else ' style="display:none"'

    # The detail is in a div tag.
    lines.append(
        '{indent}<div id="{id}"{visibility}>'.format(
            indent=self.line_indent, id=id, visibility=visibility))
    self.push_level()
    lines.append('{indent}{detail}'.format(
            indent=self.line_indent, detail=detail_html))
    self.pop_level()
    lines.append('{indent}</div>'.format(indent=self.line_indent))

    return '\n'.join(lines)

  def maybe_rewrite_class_parts(self, parts):
    """If the parts is a CLASS expansion then flatten it out.

    Normally a CLASS part is followed by a section containing the class'
    attributes. For HTML, we'll flatten that out so the CLASS is the first
    part, followed by the parts that were in the section.

    Args:
      parts: List of ScribeRendererPart

    Returns:
      List of ScribeRendererPart
    """
    if parts[0].name == 'CLASS':
      return [parts[0]] + parts[1].value._parts
    else:
      return parts

  # Map part relation to the CSS style to render it with.
  # Only special relations change the style. Otherwise the style
  # is inherited from its scope.
  _RELATION_TO_TD_CSS = {
    scribe_module.ScribePartBuilder.ERROR: 'error',
    scribe_module.ScribePartBuilder.VALID: 'valid',
    scribe_module.ScribePartBuilder.INVALID: 'invalid',
    scribe_module.ScribePartBuilder.DATA: 'data',
    scribe_module.ScribePartBuilder.INPUT: 'input',
    scribe_module.ScribePartBuilder.OUTPUT: 'output',
    scribe_module.ScribePartBuilder.CONTROL: 'control',
    scribe_module.ScribePartBuilder.MECHANISM: 'mechanism'
  }

  # Map part relation to the CSS style to render the label with.
  # Only special relations change the style. Otherwise the style
  # is inherited from its scope.
  _RELATION_TO_TH_CSS = {
    scribe_module.ScribePartBuilder.ERROR: 'error',
    scribe_module.ScribePartBuilder.VALID: 'valid',
    scribe_module.ScribePartBuilder.INVALID: 'invalid',
  }

  def build_key_html(self):
    table="""
<table>
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
<hr/>
"""
    return '<b>Key:</b>{table}\n<p/>'.format(
        table=self.render_expandable_content(
        summary_html='Report Key', detail_html=table, detail_css='meta',
        id='key', default_visible=False))

  @staticmethod
  def determine_css_decorator(d, key):
    """Returns decorator string for HTML tag using the CSS style in d, if any.

    Args:
      d: A dictionary whose values are CSS style names.
      key: The key to lookup in the dictionary

    Returns:
      An HTML tag class attribute binding, or empty string.
    """
    style = d.get(key, None)
    return ' class="{0}"'.format(style) if style else ''

  def determine_part_css(self, part):
    """Determine the CSS style for a given part.

    Args:
      part: The ScribeRendererPart to be rendered.
    Returns:
      pair of attribute decorators for TH and TD HTML tags.
    """
    return (
      self.determine_css_decorator(self._RELATION_TO_TH_CSS, part.relation),
      self.determine_css_decorator(self._RELATION_TO_TD_CSS, part.relation))

  def render_parts(self, parts):
    """Implements scribe part rendering method to produce a [nested] table.

    Args:
      parts: List of ScribeRendererPart

    Returns:
      HTML for parts.
    """
    parts = self.maybe_rewrite_class_parts(parts)

    lines = ['<table>']
    self.push_level()
    for p in parts:
      label = _escape(p.name) if p.name else ''
      detail = (p.explicit_renderer(p.value, self)
                   if p.explicit_renderer
                   else self.render(p.value))
      if not label.strip() and not detail.strip():
        continue
      th_css, td_css = self.determine_part_css(p)

      lines.append('{indent}<tr><th{th_css}>{label}</th><td{td_css}>\n'
                   '{indent}{detail}</td>'.format(
          indent=self.line_indent, label=label, detail=detail,
          th_css=th_css, td_css=td_css))
    self.pop_level()
    lines.append('{indent}</table>'.format(indent=self.line_indent))
    return '\n'.join(lines)

  @staticmethod
  def section_renderer(section, scribe):
    """Scribe rendering method for rendering ScribeRendererSection as HTML.

    Sections are rendered as expandable DIV tags containing the normally
    rendered object within.

    Args:
      section: The ScribeRendererSection to render.
      scribe: The HtmlScribe to render the section with.
    Returns:
      HTML encoding of the section.
    """
    id = scribe.next_section_id
    summary_html=section.title or 'Details'
    detail_html=scribe.render_parts(section._parts)
    if len(re.sub(' +', ' ', detail_html)) < 120:
      return detail_html
    detail_css=None
    return scribe.render_expandable_content(
      summary_html, detail_html, detail_css, id)

  @classmethod
  def render_json_if_possible(cls, obj, scribe):
    text = super(HtmlScribe, cls).render_json_if_possible(obj, scribe)
    # The JSON is going to be indented to our current level (and beyond),
    # but we only need to indent relative to our current level, so remove
    # our level indentation.
    text = text.replace('\n{indent}'.format(indent=scribe.line_indent),
                        '\n').strip()
    return '<pre>{text}</pre>'.format(text=_escape(text))

  @classmethod
  def render_list_elements(cls, l, scribe):
    """Scribe rendering method for rendering python lists as HTML.

    Args:
      cls: The HtmlScribe class rendering the list.
      l: The python list to render.
      scribe: The HtmlScribe to render the section with.
    Returns:
      HTML encoding of the list.
    """
    lines = ['<ul>']
    scribe.push_level()
    for e in l:
      lines.append('{indent}<li> {content}'.format(
          indent=scribe.line_indent, content=scribe.render(e).strip()))
    scribe.pop_level()
    lines.append('{indent}</ul>'.format(indent=scribe.line_indent))
    return '\n'.join(lines)


HTML_SCRIBE_REGISTRY.add(basestring, _escape_repr_renderer)
HTML_SCRIBE_REGISTRY.add(dict, _escape_repr_renderer)
HTML_SCRIBE_REGISTRY.add(tuple, _escape_repr_renderer)
HTML_SCRIBE_REGISTRY.add(Exception, _exception_renderer)
HTML_SCRIBE_REGISTRY.add(
    scribe_module.ScribeRendererSection, HtmlScribe.section_renderer)
