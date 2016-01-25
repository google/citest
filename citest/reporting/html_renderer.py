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

"""Helper classes and methods for rendering JSON into HTML.

This is particular to the JSON emitted by the Journal.
"""

import cgi
import datetime
import json

from .journal_processor import (JournalProcessor, ProcessedEntityManager)


def _to_string(value):
  """Converts value to string, handling unicode encoding if needed."""
  if isinstance(value, basestring):
    return value.encode('utf-8')
  return str(value)


class HtmlFormatter(object):
  """Object for helping format HTML"""

  @property
  def line_indent(self):
    """Current indentation string."""
    return ' ' * self.__level * self.indent_factor

  @property
  def indent_factor(self):
    """Number of spaces to indent per level."""
    return 2

  @property
  def level(self):
    """Numeric 'depth' of indentation levels."""
    return self.__level

  def __init__(self):
    """Constructor."""
    self.__level = 0

  def push_level(self, count=1):
    """Increment indentation level.

    Args:
      count: [int] If specified, the number of levels to increment by.
    """
    if count < 0:
      raise ValueError('count={0} cannot be negative'.format(count))
    self.__level += count

  def pop_level(self, count=1):
    """Decrement indentation level.

    Args:
      count: [int] If specified, the number of levels to decrement by.
    """
    if count < 0:
      raise ValueError('count={0} cannot be negative'.format(count))
    if self.__level < count:
      raise ValueError('Popped too far.')
    self.__level -= count


class HtmlInfo(object):
  """Specifies an HTML encoding of an object.

  The info contains two parts. A detailed encoding, and summary encoding.
  If the summary encoding is empty, then there is no summary.
  Otherwise, the summary can be used in place of the detail, typically
  as a link or facade for it.
  """

  @property
  def detail_html(self):
    """The fully detailed HTML."""
    return self.__detail_html

  @property
  def summary_html(self):
    """If non-empty then this is a summary of the detail_html.

    The summary can be used to collapse the detail.
    """
    return self.__summary_html

  def __init__(self, html='', summary_html=None):
    """Constructor."""
    self.__detail_html = html
    self.__summary_html = None if not summary_html else summary_html


class ProcessToRenderInfo(object):
  """Helper class to convert JSON objets into detail and summary HTML blocks.
  """

  def __init__(self, document_manager, entity_manager):
    """Constructor.

    Args:
      document_manager: [HtmlDocumentManager] For access when a document
         manager is needed to make rendering decisions.
      entity_manager: [ProcessedEntityManager] For access when an entity
         manager is needed to make rendering decisions.
    """
    self.__document_manager = document_manager
    self.__entity_manager = entity_manager
    self.__formatter = HtmlFormatter()

    # The following attributes are used to determine when to render collapsable
    # details vs inline expand for different types of data.
    # At some point the overhead in making something expandable isnt worth the
    # savings of hiding it (also a function of how interesting it is likely to
    # be).
    # A value of N indicates the item will be completely inlined if # <= N,
    # otherwise will be completely collapsable.
    self.max_uncollapsable_json_lines = 3   # Text rendered as JSON.
    self.max_uncollapsable_pre_lines = 3    # Lines rendered with HTML pre tag.
    self.max_uncollapsable_entity_rows = 0  # Num attributes within an entity.
    self.max_uncollapsable_metadata_rows = 0  # Num metadata keys.
    self.max_uncollapsable_message_lines = 0  # Always collapse log messages.
    self.max_message_summary_length = 100

  def determine_default_expanded(self, relation):
    """Determine whether entities should be expanded by default or not.

    Args:
      relation: [string] The relation to the entity is used as a signal.
    """
    # The default policy is to expand verification results and only those.
    return relation in ['VALID', 'INVALID']

  def __tr_for_html_info(self, label_html, info,
                         relation=None, default_expanded=None):
    """Constructs a table row from HtmlInfo.

    Args:
      label_html: [string] The HTML for the row TH element.
      info: [HtmlInfo] Specifies the data we want to write into the row.
      relation: [string] The relation for the row to make CSS choices.
      default_expanded: [bool] Whether the detail is expanded by default
          or not. If None then use the default value depending on the relation.

    Returns:
      HTML TR block.
    """
    # pylint: disable=too-many-locals
    th_css, td_css = self.__document_manager.determine_attribute_css(relation)
    formatter = self.__formatter
    line_indent = formatter.line_indent
    formatter.push_level()
    cell_indent = formatter.line_indent
    formatter.push_level()
    span_indent = formatter.line_indent
    formatter.push_level()
    data_indent = formatter.line_indent
    formatter.pop_level(3)

    if not info.summary_html:
      label = label_html
      if info.detail_html:
        if info.detail_html[-1] == '\n':
          data_fragments = ['\n',  # end <td> line
                            data_indent,
                            info.detail_html]
          maybe_td_indent = cell_indent
        else:
          data_fragments = info.detail_html
          maybe_td_indent = ''
      else:
        data_fragments = []
        maybe_td_indent = ''
    else:
      document_manager = self.__document_manager
      if default_expanded is None:
        default_expanded = self.determine_default_expanded(relation)
      section_id = document_manager.new_section_id()
      label = document_manager.make_expandable_control_for_section_id(
          section_id, label_html)
      summary = document_manager.make_expandable_control_for_section_id(
          section_id, 'show {0}'.format(info.summary_html))
      detail_tag_attrs, summary_tag_attrs = (
          self.__document_manager.make_expandable_tag_attr_pair(
              section_id=section_id, default_expanded=default_expanded))
      data_fragments = [
          '\n',  # end <td> line
          '{indent}<span {summary_tag_attrs}>{summary}</span>\n'.format(
              indent=span_indent,
              summary_tag_attrs=summary_tag_attrs,
              summary=summary),
          '{indent}<span {detail_tag_attrs}>{detail}'.format(
              indent=span_indent,
              detail_tag_attrs=detail_tag_attrs,
              detail=info.detail_html),
          '{indent}</span>\n'.format(indent=span_indent)
          ]
      maybe_td_indent = cell_indent

    fragments = ['{indent}<tr>\n'.format(indent=line_indent),
                 '{indent}<th{th_css}>{label}</th>\n'.format(
                     indent=cell_indent, th_css=th_css, label=label),
                 '{indent}<td{td_css}>'.format(
                     td_css=td_css, indent=cell_indent)]
    fragments.extend(data_fragments)
    fragments.extend(['{indent}</td>\n'.format(indent=maybe_td_indent),
                      '{indent}</tr>\n'.format(indent=line_indent)])
    return ''.join(fragments)

  def process_json_html_if_possible(self, value):
    """Render value as HTML. Indicate it is JSON if in fact it is.

    Args:
      value: [obj] The value to render.

    Returns:
      HtmlInfo encoding of value.
    """
    summary = ''
    try:
      if isinstance(value, basestring):
        tmp = json.JSONDecoder(encoding='utf-8').decode(value)
        text = json.JSONEncoder(indent=self.__formatter.indent_factor,
                                encoding='utf-8',
                                separators=(',', ': ')).encode(tmp)
      elif isinstance(value, (list, dict)):
        text = json.JSONEncoder(indent=self.__formatter.indent_factor,
                                encoding='utf-8',
                                separators=(',', ': ')).encode(value)
      else:
        raise ValueError()

      escaped_text = '<pre>{0}</pre>'.format(cgi.escape(text))
      num_lines = text.count('\n')
      if num_lines > self.max_uncollapsable_json_lines:
        summary = 'Json details'
      else:
        summary = None
    except (ValueError, UnicodeEncodeError):
      if isinstance(value, basestring):
        escaped_text = '"{0}"'.format(cgi.escape(value, quote=True))
      else:
        escaped_text = cgi.escape(repr(value))
    return HtmlInfo(escaped_text, summary)

  def process_edge_value(self, edge, value):
    """Render value as HTML.

    Args:
      edge: [dict] The JSON encoding of a JsonSnapshot Edge containing the
         value. This is used for hints as to how to interpret the value.
      value: [obj] The value to render.

    Returns:
      HtmlInfo encoding of value.
    """
    text_format = edge.get('format', None)
    if text_format == 'json':
      return self.process_json_html_if_possible(value)
    elif text_format == 'pre':
      count = value.count('\n')
      summary = ('{0} lines'.format(count)
                 if count > self.max_uncollapsable_pre_lines
                 else None)
      # The ff tag here is a custom tag for "Fixed Format"
      # It is like 'pre' but inline rather than block to be more compact.
      return HtmlInfo('<ff>{0}</ff>'.format(value), summary)
    else:
      return HtmlInfo(cgi.escape(_to_string(value)))

  def process_list(self, value, snapshot, edge_to_list, default_expanded=None):
    """Renders value as HTML.

    The individual elements in the list are interpreted and rendered as well.

    Args:
      value: [list] The value to render.
      snapshot: [dict] JSON object representing the JsonSnapshot is used
         if the value contains or references entities.
      edge_to_list: [edge] The edge to the containing list has the attributes
         for the elements in the list.
    Returns:
      HtmlInfo encoding of value.
    """
    if not value:
      return HtmlInfo('<i>Empty list</i>')

    list_indent = self.__formatter.line_indent
    self.__formatter.push_level()

    fragments = ['<table>\n']
    for index, elem in enumerate(value):
        # pylint: disable=bad-indentation
        elem_info = self.process_list_value(elem, snapshot, edge_to_list)
        elem_relation = edge_to_list.get('relation')
        if isinstance(elem, dict):
          elem_relation = elem.get('_default_relation') or elem_relation

        fragments.extend([
            self.__tr_for_html_info('[{0}]'.format(index), elem_info,
                                    relation=elem_relation,
                                    default_expanded=default_expanded)])
    fragments.append('{indent}</table>\n'.format(indent=list_indent))
    self.__formatter.pop_level()
    summary = '{0} item{1}'.format(len(value), 's' if len(value) != 1 else '')
    return HtmlInfo(''.join(fragments), summary)

  def process_list_value(self, value, snapshot, edge_to_list):
    """Renders value from within a list as HTML.

    Args:
      value: [any] The value to render.
      snapshot: [dict] JSON object representing the JsonSnapshot is used
         if the value contains or references entities.
      edge_to_list: [dict] Represents the edge to the containing list.
    Returns:
      HtmlInfo encoding of value.
    """
    if isinstance(value, list):
      value_info = self.process_list(value, snapshot, edge_to_list)
    elif isinstance(value, dict) and value.get('_type') == 'EntityReference':
      self.__formatter.push_level()
      value_info = self.process_entity_id(value['_id'], snapshot)
      self.__formatter.pop_level()
    else:
      value_info = self.process_edge_value(edge_to_list, value)

    return value_info

  def process_metadata(self, obj, blacklist=[]):
    """Renders object metadata as an HTML table

    Args:
      obj: [dict] The JSON encoded journal object's fields are all metadata
      backlist: [list] List of keys to ignore from the metadata.
    Returns:
      HtmlInfo encoding of the metadata table.
    """
    # pylint: disable=dangerous-default-value
    formatter = self.__formatter
    table_indent = formatter.line_indent
    fragments = ['<table>\n']
    formatter.push_level()
    line_indent = formatter.line_indent
    row_count = 0
    for name, value in obj.items():
      if name not in blacklist:
        row_count += 1
        fragments.append(
            '{indent}<tr><th>{name}</th><td>{value}</td></tr>\n'
            .format(indent=line_indent, name=name,
                    value=cgi.escape(_to_string(value))))

    formatter.pop_level() # both data and table
    if row_count == 0:
      return HtmlInfo()

    fragments.append('{indent}</table>\n'.format(indent=table_indent))
    return HtmlInfo(''.join(fragments),
                    ('metadata'
                     if row_count > self.max_uncollapsable_metadata_rows
                     else ''))

  def process_entity(self, subject, snapshot):
    """Renders a JsonSnapshot Entity into HtmlInfo

    Args:
      subject: [dict] The JSON object denoting the entity to encode.
      snapshoft: [dict] Represents JsonSnapshot containing the subject.
         This may be needed if the subject references other entities in
         the snapshot.
    Returns:
      HtmlInfo encoding of the subject.
    """
    formatter = self.__formatter
    formatter.push_level(2)
    table_indent = formatter.line_indent
    fragments = ['\n{indent}<table>\n'.format(indent=table_indent)]

    formatter.push_level() # table lines

    blacklist = ['_edges']
    formatter.push_level(2)  # the data will be under an additional tr and td.
    meta_info = self.process_metadata(subject, blacklist=blacklist)
    formatter.pop_level(2)
    if meta_info.detail_html:
      fragments.extend([
          self.__tr_for_html_info('<i>metadata</i>', meta_info,
                                  relation='meta',
                                  default_expanded=False)])

    num_rows = 0
    for edge in subject.get('_edges', []):
        # pylint: disable=bad-indentation
        label = edge.get('label', '?unlabled')
        target_id = None
        value_info = None
        value = edge.get('_value', None)
        if isinstance(value, list):
          formatter.push_level()
          value_info = self.process_list(value, snapshot, edge)
          formatter.pop_level()
        elif (isinstance(value, dict)
              and value.get('_type') == 'EntityReference'):
          target_id = value.get['_id']
        elif value is not None:
          formatter.push_level()
          value_info = self.process_edge_value(edge, value)
          formatter.pop_level()
        else:
          target_id = edge.get('_to', None)

        if target_id is not None:
            formatter.push_level()
            value_info = self.process_entity_id(target_id, snapshot)
            formatter.pop_level()
        elif value_info is None:
          value_info = HtmlInfo('<i>empty<i>')

        fragments.append(
            self.__tr_for_html_info(label, value_info,
                                    relation=edge.get('relation')))
        num_rows += 1

    formatter.pop_level(3) # Pop line level + original inner-2
    fragments.append('{indent}</table>\n'.format(indent=table_indent))

    if num_rows > self.max_uncollapsable_entity_rows:
      summary_html = (subject.get('_title')
                      or subject.get('summary') or subject.get('class')
                      or 'Details')
    else:
      summary_html = None

    return HtmlInfo(''.join(fragments), summary_html=summary_html)

  def process_entity_id(self, subject_id, snapshot):
    """Renders a JsonSnapshot Entity into HtmlInfo.

    Args:
      subject_id: [int] The ID of the JSON encoded entity to process.
      snapshoft: [dict] Represents JsonSnapshot containing the subject.
         This may be needed if the subject references other entities in
         the snapshot.
    Returns:
      HtmlInfo encoding of the referenced subject.
    """
    if subject_id in self.__entity_manager.ids_in_progress:
      return HtmlInfo('<i>Cyclic link to entity id={0}</i>'.format(subject_id))

    try:
      self.__entity_manager.begin_id(subject_id)
      subject = self.__entity_manager.lookup_entity_with_id(subject_id)
      entity_info = self.process_entity(subject, snapshot)
    finally:
      self.__entity_manager.end_id(subject_id)

    return entity_info


class HtmlRenderer(JournalProcessor):
  """Specialized JournalProcessor to produce HTML."""

  def __init__(self, document_manager, registry=None):
    """Constructor.

    Args:
      document_manager: [HtmlDocumentManager] Helps with look & feel,
         and structure.
      registry: [dict] Registry of processing methods keyed by record type
         in the journal. If not defined, then use the default.
    """
    if registry is None:
      registry = {
          'JsonSnapshot': self.render_snapshot,
          'JournalMessage': self.render_message
      }

    super(HtmlRenderer, self).__init__(registry)
    self.__entity_manager = ProcessedEntityManager()
    self.__document_manager = document_manager

  def render_snapshot(self, snapshot):
    """Default method for rendering a JsonSnapshot into HTML."""
    subject_id = snapshot.get('_subject_id')
    entities = snapshot.get('_entities', {})
    self.__entity_manager.push_entity_map(entities)
    date_str = self.timestamp_to_string(snapshot.get('_timestamp'))

    # This is only for the final relation.
    subject = self.__entity_manager.lookup_entity_with_id(subject_id)
    final_relation = subject.get('_default_relation')

    # Delegate the whole thing.
    document_manager = self.__document_manager
    processor = ProcessToRenderInfo(document_manager, self.__entity_manager)
    try:
      info = processor.process_entity_id(subject_id, snapshot)
    finally:
      self.__entity_manager.pop_entity_map(entities)

    if not info.summary_html:
      self._do_render(
          '<tr><th class="nw">{timestamp}</th><td>{html}</td></tr>\n'.format(
              timestamp=date_str, html=info.detail_html))
      return

    final_css = document_manager.determine_attribute_css(final_relation)[0]
    title = '"{0}"'.format(info.summary_html) if info.summary_html else None
    self.render_log_tr(snapshot.get('_timestamp'),
                       title, info.detail_html, collapse_decorator=title,
                       css=final_css)
    return

  @staticmethod
  def timestamp_to_string(timestamp):
    """Return human-readable timestamp.

    Args:
      timestamp: [float]  Seconds since epoch.
    """

    millis = ('%.3f' % (timestamp - int(timestamp)))[2:]
    return datetime.datetime.fromtimestamp(timestamp).strftime(
        '%Y-%m-%d %H:%M:%S.{millis}'.format(millis=millis))

  def render_log_tr(self, timestamp, summary, detail,
                    collapse_decorator='', css=''):
    """Render a top level entry into the log as a table row.

    Args:
      timestamp: [float] The timestamp for the entry.
      summary: [string] If provided, this is an abbreviation.
      detail: [string] This is the full detail for the entry.
    """
    date_str = self.timestamp_to_string(timestamp)
    if not summary:
      self._do_render(
          '<tr><th class="nw">{timestamp}</th><td>{html}</td></tr>\n'.format(
              timestamp=date_str, html=detail))
      return

    # pylint: disable=bad-continuation
    collapse_html = ('collapse {decorator}'
                         .format(decorator=collapse_decorator)
                     if collapse_decorator
                     else 'collapse')

    document_manager = self.__document_manager
    section_id = document_manager.new_section_id()
    show = document_manager.make_expandable_control_for_section_id(
        section_id, 'expand')
    hide = document_manager.make_expandable_control_for_section_id(
        section_id, collapse_html)
    detail_tag_attrs, summary_tag_attrs = (
        document_manager.make_expandable_tag_attr_pair(
            section_id=section_id, default_expanded=False))
    # pylint: disable=bad-continuation
    self._do_render(
        ''.join(
            ['<tr><th class="nw">{timestamp}</th><td>\n'
                 .format(timestamp=date_str),
             '<span{css} {hide_attrs} padding:8px>{show} {summary}</span>\n'
                 .format(css=css,
                         hide_attrs=summary_tag_attrs,
                         summary=summary,
                         show=show),
             '<span{css} {show_attrs}>\n'
                 .format(css=css, show_attrs=detail_tag_attrs),
             '{hide}\n'.format(hide=hide),
             '{detail}\n</span>\n'.format(detail=detail)]))

  def render_message(self, message):
    """Default method for rendering a JournalMessage into HTML."""
    text = message.get('_value')

    document_manager = self.__document_manager
    processor = ProcessToRenderInfo(document_manager, self.__entity_manager)

    html = ""
    if text is not None:
      html = cgi.escape(text) if text is not None else '<i>Empty Message</i>'

    html_format = message.get('format', None)
    summary = None
    if html_format == 'pre':
        # pylint: disable=bad-indentation
        # The ff tag here is a custom tag for "Fixed Format"
        # It is like 'pre' but inline rather than block to be more compact.
        num_lines = html.count('\n')
        if num_lines > processor.max_uncollapsable_message_lines:
          summary = '<ff>{0}...</ff>'.format(html[0:html.find('\n')])
        elif len(text) > processor.max_message_summary_length:
          summary = '<ff>{0}...</ff>'.format(
              html[0:processor.max_message_summary_length - 3])
        html = '<ff>{0}</ff>'.format(html)

    self.render_log_tr(message.get('_timestamp'), summary, html)


  def _do_render(self, html):
    """Helper function that renders html fragment into the HTML document."""
    self.__document_manager.write(html)
