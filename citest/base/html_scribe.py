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
import threading
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
    source: [string] To be escaped.
    quote: [bool] If True then also escape quote characters.
  Returns:
    Escaped HTML string.
  """
  text = source.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
  if quote:
    text = text.replace('"', '&quot').replace("'", '&apos')
  return text


def _escape_repr_renderer(out, obj):
  """A renderer that escapes a python object string representation into HTML.

  Args:
    out: [Doodle] To render to.
    obj: [object] To render as a string.
  """
  out.write(_escape(str(obj)))


def _exception_renderer(out, obj):
  """A renderer for exceptions as HTML.

  Args:
    out: [Doodle] To render to.
    obj: [Exception] To render as a string.
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
  out.write(html)


class HtmlScribe(scribe_module.Scribe):
  """
  Implements a thread-safe scribe that renders into HTML.

  Attributes:
    next_section_id: The string ID to use to identify the next expandable
        HTML section.
  """

  @property
  def next_section_id(self):
    self._lock.acquire(True)
    self._section_count += 1
    id = self._section_count
    self._lock.release()
    return 'S{0}'.format(id)

  def __init__(self, registry=HTML_SCRIBE_REGISTRY):
    super(HtmlScribe, self).__init__(registry)
    self._lock = threading.Lock()
    self._section_count = 0

  def write_html_head_block(self, out, title):
    """Writes text for the HTML HEAD section.

    The HEAD section will contain the standard Javascript and CSS used within.

    Args:
      out: [Doodle] To render to.
      title: [string] The unescaped text title of HTML will be escaped.
    """
    out.write('<head><title>{title}</title>{javascript}{css}</head>\n'.format(
        javascript=_javascript, css=_css, title=_escape(title)))

  def write_begin_html_document(self, out, title):
    """Writes a new html document up to the openening BODY tag.

    Args:
      out: [Doodle] To render to.
      title: [string] The unescaped text title of HTML will be escaped.
    """
    html_out = out.new_at_level()
    self.write_html_head_block(html_out, title),
    out.write('\n'.join(
        ['<!DOCTYPE html>\n<html>',
         str(html_out),
         '<body>']))

  def write_end_html_document(self, out):
    """Writes the closing of the HTML document BODY and HTML tags."""
    out.write('\n'.join(['</body>', '</html>']))

  def write_notoggle_div(self, out, html, css='fodder'):
    """Writes an HTML div section that is not toggleable.

    Args:
      out: [Doodle] To render to.
      html: [string] The html to render inside the DIV tag.
      css: [string] The CSS style name to use, if any.
    """
    lines = ['<div class="{css}" style="display:block">'.format(css=css)]
    out.push_level()
    lines.append('{indent}{html}'.format(indent=out.line_indent, html=html))
    out.pop_level()
    lines.append('{indent}</div>'.format(indent=out.line_indent))
    out.write('\n'.join(lines))

  def write_expandable_content(
      self, out, summary_html, detail_html, detail_css, id,
      default_visible=True):
    """Writes an expandable DIV block.

    Args:
      out: [Doodle] To write to.
      summary_html: [string] The HTML to display when the block is not
         expanded. This is also displayed to close the block when expanded.
      detail_html: [string] The HTML to display when the block is expanded.
      detail_css: [string] The CSS stylesheet to use for the detail_html.
      id: [string] The javascript ID value to associate with this block must
         be unique within the document.
      default_visible: [bool] True should be visible by default.
    """

    # The summary line is a link.
    lines = ['<a class="toggle"'
             ' onclick="toggle_visibility(\'{id}\');">'.format(id=id)]
    out.push_level()
    lines.append('{indent}{summary}'
                 .format(indent=out.line_indent, summary=summary_html))
    out.pop_level()
    lines.append('{indent}</a><br/>'.format(indent=out.line_indent))

    # div tags are visible by default, so we only worry about hiding it.
    visibility = '' if default_visible else ' style="display:none"'

    # The detail is in a div tag.
    lines.append(
        '{indent}<div id="{id}"{visibility}>'.format(
            indent=out.line_indent, id=id, visibility=visibility))
    out.push_level()
    lines.append('{indent}{detail}'
                 .format(indent=out.line_indent, detail=detail_html))
    out.pop_level()
    lines.append('{indent}</div>'.format(indent=out.line_indent))

    out.write('\n'.join(lines))

  def maybe_rewrite_class_parts(self, parts):
    """If the parts is a CLASS expansion then flatten it out.

    Normally a CLASS part is followed by a section containing the class'
    attributes. For HTML, we'll flatten that out so the CLASS is the first
    part, followed by the parts that were in the section.

    Args:
      parts: [list of ScribeRendererPart]

    Returns:
      List of ScribeRendererPart
    """
    if parts[0].name == 'CLASS':
      return [parts[0]] + parts[1].value.parts
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

  def write_key_html(self, out):
    table = """
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
    content_out = scribe_module.Doodle(self)
    self.write_expandable_content(
        content_out, summary_html='Report Key',
        detail_html=table, detail_css='meta',
        id='key', default_visible=False)
    out.write('<b>Key:</b>{table}\n<p/>'.format(table=content_out))

  @staticmethod
  def determine_css_decorator(d, key):
    """Returns decorator string for HTML tag using the CSS style in d, if any.

    Args:
      d: [dict] Values are CSS style names.
      key: [string] The key to lookup in the dictionary.

    Returns:
      An HTML tag class attribute binding, or empty string.
    """
    style = d.get(key, None)
    return ' class="{0}"'.format(style) if style else ''

  def determine_part_css(self, part):
    """Determine the CSS style for a given part.

    Args:
      part: [ScribeRendererPart] to be rendered.
    Returns:
      pair of attribute decorators for TH and TD HTML tags.
    """
    return (
        self.determine_css_decorator(self._RELATION_TO_TH_CSS, part.relation),
        self.determine_css_decorator(self._RELATION_TO_TD_CSS, part.relation))

  def render_parts(self, out, parts):
    """Implements scribe part rendering method to produce a [nested] table.

    Args:
      out: [Doodle] To write to.
      parts: [list of ScribeRendererPart]
    """
    parts = self.maybe_rewrite_class_parts(parts)

    lines = ['<table>']
    out.push_level()
    for p in parts:
      label = _escape(p.name) if p.name else ''
      detail = out.render_to_string(p.value, p.explicit_renderer)

      if not label.strip() and not detail.strip():
        continue
      th_css, td_css = self.determine_part_css(p)

      lines.append('{indent}<tr><th{th_css}>{label}</th><td{td_css}>\n'
                   '{indent}{detail}</td>'
                   .format(indent=out.line_indent, label=label, detail=detail,
                           th_css=th_css, td_css=td_css))
    out.pop_level()
    lines.append('{indent}</table>'.format(indent=out.line_indent))
    out.write('\n'.join(lines))

  @staticmethod
  def section_renderer(out, section):
    """Scribe rendering method for rendering ScribeRendererSection as HTML.

    Sections are rendered as expandable DIV tags containing the normally
    rendered object within.

    Args:
      out: [Scribable] to write to.
      section: [ScribeRendererSection] to render.
    """
    scribe = out.scribe
    id = scribe.next_section_id
    summary_html = section.title or 'Details'
    detail_out = out.new_at_level()
    scribe.render_parts(detail_out, section.parts)
    detail_html = str(detail_out)
    if len(re.sub(' +', ' ', detail_html)) < 120:
      out.write(detail_html)
    else:
      detail_css = None
      scribe.write_expandable_content(
          out, summary_html, detail_html, detail_css, id)

  @classmethod
  def render_json_if_possible(cls, out, obj):
    json_out = out.new_at_level()
    super(HtmlScribe, cls).render_json_if_possible(json_out, obj)

    # The JSON is going to be indented to our current level (and beyond),
    # but we only need to indent relative to our current level, so remove
    # our level indentation.
    text = str(json_out)
    text = text.replace('\n{indent}'.format(indent=json_out.line_indent),
                        '\n').strip()
    out.write('<pre>{text}</pre>'.format(text=_escape(text)))

  @classmethod
  def render_list_elements(cls, out, l):
    """Scribe rendering method for rendering python lists as HTML.

    Args:
      cls: [class] The HtmlScribe class rendering the list.
      out: [Doodle] To write to.
      l: The python list to render.
    """
    lines = ['<ul>']
    out.push_level()
    scribe = out.scribe
    for e in l:
      line_text = out.render_to_string(e)
      lines.append('{indent}<li> {content}'.format(
          indent=out.line_indent, content=line_text.strip()))
    out.pop_level()
    lines.append('{indent}</ul>'.format(indent=out.line_indent))
    out.write('\n'.join(lines))


HTML_SCRIBE_REGISTRY.add(basestring, _escape_repr_renderer)
HTML_SCRIBE_REGISTRY.add(dict, _escape_repr_renderer)
HTML_SCRIBE_REGISTRY.add(tuple, _escape_repr_renderer)
HTML_SCRIBE_REGISTRY.add(Exception, _exception_renderer)
HTML_SCRIBE_REGISTRY.add(
    scribe_module.ScribeRendererSection, HtmlScribe.section_renderer)
