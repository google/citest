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

import collections
import datetime
import json

from .journal_processor import (JournalProcessor, ProcessedEntityManager)
from .simplify_entity_transforms import get_edge_label_value_transformer

class RenderedContext(
    collections.namedtuple('RenderedContext', ['control', 'html'])):
  """Holds information about a context being rendered."""
  pass


def _to_string(value):
  """Converts value to string, handling unicode encoding if needed."""
  if isinstance(value, basestring):
    return value.encode('utf-8')
  return str(value)


class HtmlInfo(object):
  """Specifies an HTML encoding of an object.

  The info contains two parts. A detailed encoding, and summary encoding.
  If the summary encoding is empty, then there is no summary.
  Otherwise, the summary can be used in place of the detail, typically
  as a link or facade for it.
  """

  @property
  def detail_block(self):
    """The fully detailed HTML block."""
    return self.__detail_block

  @property
  def summary_block(self):
    """If non-empty then this is a summary of the detail_block.

    The summary can be used to collapse the detail.
    """
    return self.__summary_block

  def __init__(self, detail=None, summary=None):
    """Constructor."""
    self.__detail_block = detail
    self.__summary_block = None if not summary else summary


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
    self.max_message_summary_length = 60

  def determine_default_expanded(self, relation):
    """Determine whether entities should be expanded by default or not.

    Args:
      relation: [string] The relation to the entity is used as a signal.
    """
    # The default policy is to expand verification results and only those.
    return relation in ['VALID', 'INVALID']

  def __html_info_to_tr_tag(self, title_html, info,
                            relation=None, default_expanded=None):
    """Constructs a table row from HtmlInfo.

    Args:
      title_html: [string] The title HTML for the row TH element.
      info: [HtmlInfo] Specifies the data we want to write into the row.
      relation: [string] The relation for the row to make CSS choices.
      default_expanded: [bool] Whether the detail is expanded by default
          or not. If None then use the default value depending on the relation.

    Returns:
      HTML TR block.
    """
    # pylint: disable=too-many-locals
    document_manager = self.__document_manager
    th_css, td_css = self.__document_manager.determine_attribute_css_kwargs(
        relation)

    data_tags = []
    if not info.summary_block:
      title_block = document_manager.make_html_block(title_html)
      if info.detail_block:
        data_tags = [info.detail_block]
    else:
      if default_expanded is None:
        default_expanded = self.determine_default_expanded(relation)
      section_id = document_manager.new_section_id()
      detail_tag_attrs, summary_tag_attrs = (
          self.__document_manager.make_expandable_tag_attr_kwargs_pair(
              section_id=section_id, default_expanded=default_expanded))

      title_block = document_manager.make_expandable_control_tag(
          section_id, title_html)

      summary = document_manager.make_expandable_control_tag(
          section_id, 'show {0}'.format(info.summary_block))
      data_tags = [
          document_manager.make_tag_container(
              'span', [summary], **summary_tag_attrs),
          document_manager.make_tag_container(
              'span', [info.detail_block], **detail_tag_attrs)
          ]

    tr = document_manager.make_tag_container(
        'tr',
        [document_manager.make_tag_container('th', [title_block], **th_css),
         document_manager.make_tag_container('td', data_tags, **td_css)])
    return tr


  def process_json_html_if_possible(self, value):
    """Render value as HTML. Indicate it is JSON if in fact it is.

    Args:
      value: [obj] The value to render.

    Returns:
      HtmlInfo encoding of value.
    """
    summary = ''
    document_manager = self.__document_manager
    try:
      if isinstance(value, basestring):
        tmp = json.JSONDecoder(encoding='utf-8').decode(value)
        text = json.JSONEncoder(encoding='utf-8', indent=2,
                                separators=(',', ': ')).encode(tmp)
      elif isinstance(value, (list, dict)):
        text = json.JSONEncoder(encoding='utf-8', indent=2,
                                separators=(',', ': ')).encode(value)
      else:
        raise ValueError('Invalid value={0!r}'.format(value))

      pre = document_manager.make_tag_text('pre', text)
      num_lines = text.count('\n')

      if num_lines > self.max_uncollapsable_json_lines:
        summary = document_manager.make_text_block('Json details')
      elif len(text) > 2 * self.max_message_summary_length:
        # If json is more than 2x normal log message, then truncate it.
        summary = document_manager.make_tag_text(
            'ff', '{0}...'.format(
                text[0:self.max_message_summary_length - 2*len('show')]))
      else:
        summary = None
    except (ValueError, UnicodeEncodeError):
      pre = document_manager.make_text_block(repr(value))

    return HtmlInfo(pre, summary)


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
      return HtmlInfo(self.__document_manager.make_tag_text('ff', value),
                      self.__document_manager.make_text_block(summary))
    else:
      return HtmlInfo(self.__document_manager.make_text_block(str(value)))

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
      return HtmlInfo(self.__document_manager.make_tag_text('i', 'Empty list'))

    table = self.__document_manager.new_tag('table')
    for index, elem in enumerate(value):
        # pylint: disable=bad-indentation
        elem_info = self.process_list_value(elem, snapshot, edge_to_list)
        elem_relation = edge_to_list.get('relation')
        if isinstance(elem, dict):
          elem_relation = elem.get('_default_relation') or elem_relation

        table.append(self.__html_info_to_tr_tag(
            '[{0}]'.format(index), elem_info,
            relation=elem_relation, default_expanded=default_expanded))

    summary = '{0} item{1}'.format(len(value), 's' if len(value) != 1 else '')
    return HtmlInfo(table, self.__document_manager.make_text_block(summary))

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
      value_info = self.process_entity_id(value['_id'], snapshot)
    else:
      value_info = self.process_edge_value(edge_to_list, value)

    return value_info

  def process_metadata(self, obj, blacklist=None):
    """Renders object metadata as an HTML table

    Args:
      obj: [dict] The JSON encoded journal object's fields are all metadata
      backlist: [list] List of keys to ignore from the metadata.
    Returns:
      HtmlInfo encoding of the metadata table.
    """
    table = self.__document_manager.new_tag('table')
    row_count = 0
    for name, value in obj.items():
      if name not in blacklist or []:
        row_count += 1
        table.append(self.__document_manager.make_tag_container(
            'tr', [self.__document_manager.make_tag_text('th', name),
                   self.__document_manager.make_tag_text('td', str(value))]))

    if row_count == 0:
      return HtmlInfo()

    return HtmlInfo(
        table,
        self.__document_manager.make_text_block(
            'metadata'
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
    table = self.__document_manager.new_tag('table')

    blacklist = ['_edges']
    meta_info = self.process_metadata(subject, blacklist=blacklist)
    if meta_info.detail_block:
      table.append(
          self.__html_info_to_tr_tag(
              '<i>metadata</i>', meta_info,
              relation='meta', default_expanded=False))
    num_rows = 0
    edge_label_value_transformer = get_edge_label_value_transformer(
        subject, self.__entity_manager)
    for edge in subject.get('_edges', []):
        # pylint: disable=bad-indentation
        label, value = edge_label_value_transformer(edge)
        if label is None:
          continue  # skip this edge

        target_id = None
        value_info = None
        if value and edge.get('format', None) in ['json', 'pre']:
          value_info = self.process_edge_value(edge, value)
        elif isinstance(value, list):
          value_info = self.process_list(value, snapshot, edge)
        elif (isinstance(value, dict)
              and value.get('_type') == 'EntityReference'):
          target_id = value.get('_id')
        elif value is not None:
          value_info = self.process_edge_value(edge, value)
        else:
          target_id = edge.get('_to', None)

        if target_id is not None:
          value_info = self.process_entity_id(target_id, snapshot)
        elif value_info is None:
          value_info = HtmlInfo(
              self.__document_manager.make_tag_text('i', 'empty'))
        table.append(
            self.__html_info_to_tr_tag(label, value_info,
                                       relation=edge.get('relation')))
        num_rows += 1

    if num_rows > self.max_uncollapsable_entity_rows:
      summary_html = (subject.get('_title')
                      or subject.get('summary') or subject.get('class')
                      or 'Details')
    else:
      summary_html = None

    return HtmlInfo(
        table,
        summary=self.__document_manager.make_text_block(
            summary_html))

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
      return HtmlInfo(self.__document_manager.make_tag_text(
          'i', 'Cyclic link to entity id={0}'.format(subject_id)))

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
          'JournalContextControl': self.handle_context_control,
          'JournalMessage': self.render_message
      }

    super(HtmlRenderer, self).__init__(registry)
    self.__entity_manager = ProcessedEntityManager()
    self.__document_manager = document_manager

    # The context stack is an array of array of strings,
    # Where each top level array is a context we've pushed, which
    # contains fragments of entities. If we've pushed a context, then
    # well render into the stack. Otherwise we'll render into the document.
    # When we pop a context we'll render it into the parent context until
    # we pop the root context, which will finally render into the document.
    self.__context_stack = []

  def terminate(self):
    """Implemets JournalProcessor interface."""
    if self.__context_stack:
      raise ValueError(
          'Still have {0} open contexts'.format(len(self.__context_stack)))

  def __render_context(self, end_control, rendered_context):
    """Render the context into HTML now that we've terminated it.

    Args:
      end_control: [dict] JournalContextControl for end context record.
      rendered_context: [RenderedContext] the context we just ended.
    """
    begin_control = rendered_context.control
    if begin_control.get('_title') == 'Execute':
      # If this context is "Execute", then unwrap this top context and the
      # execute context to promote the actual thing executed to this level.
      # This is a hack, but makes the reporting more readable.
      if rendered_context.html:
        if self.__context_stack:
          self.__context_stack[-1].html.extend(rendered_context.html)
      return

    # Relation here is used to indicate the test status.
    # Take that and turn it into a style.
    relation = end_control.get('relation', None)
    document_manager = self.__document_manager
    css = document_manager.determine_attribute_css_kwargs(relation)[0]
    title_html = document_manager.make_html_block(
        begin_control.get('_title', ''))
    if not rendered_context.html:
      title_html.append(document_manager.make_html_block(' (<i>empty</i>)'))
      self.render_log_tr(begin_control['_timestamp'], None,
                         title_html, css=css)
    else:
      delta_time = end_control['_timestamp'] - begin_control['_timestamp']
      if css:
        title_html = document_manager.make_tag_container(
            'span', [title_html], **css)
      lvl = min(1, len(self.__context_stack))
      title_html = document_manager.make_tag_container(
          'context{n}'.format(n=lvl), [title_html])
      summary = document_manager.make_html_block(
          '%s <small>+%.3fs</small>' % (title_html, delta_time))
      table = document_manager.new_tag('table')

      for row in rendered_context.html:
        table.append(row)
      detail = document_manager.make_html_block(str(title_html))
      detail.append(table)
      self.render_log_tr(begin_control['_timestamp'], summary, detail)

  def handle_context_control(self, control):
    """Begin or terminate contexts."""
    direction = control['control']
    if direction == 'BEGIN':
      self.__context_stack.append(RenderedContext(control, []))
    elif direction == 'END':
      context = self.__context_stack[-1]
      self.__context_stack.pop()
      if (not context.html
          and context.control.get('_title', '') in ['setUp', 'tearDown']):
        return
      self.__render_context(control, context)
    else:
      raise ValueError(
          'Invalid JournalContextControl control={0}'.format(direction))

  def render_snapshot(self, snapshot):
    """Default method for rendering a JsonSnapshot into HTML."""
    subject_id = snapshot.get('_subject_id')
    entities = snapshot.get('_entities', {})
    self.__entity_manager.push_entity_map(entities)

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

    if not info.summary_block:
      self.render_log_tr(snapshot.get('_timestamp'), None, info.detail_block)
      return

    final_css = document_manager.determine_attribute_css_kwargs(
        final_relation)[0]
    title = snapshot.get('_title', '')
    if not title and info.summary_block:
      title = '"{html}" Snapshot'.format(html=info.summary_block)
    if title:
      title_html = document_manager.make_tag_text('padded', title, **final_css)

    self.render_log_tr(snapshot.get('_timestamp'),
                       title_html, info.detail_block, collapse_decorator=title)
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

  def render_log_tr(self, timestamp, summary, detail, **kwargs):
    """Add row to accumulated output.

      timestamp: [float] The timestamp for the entry.
      summary: [string] If provided, this is an abbreviation.
      detail: [string] This is the full detail for the entry.
    """
    tag = self.render_log_tr_tag(timestamp, summary, detail, **kwargs)
    if self.__context_stack:
      self.__context_stack[-1].html.append(tag)
    else:
      self.__document_manager.append_tag(tag)

  def render_log_tr_tag(self, timestamp, summary, detail,
                        collapse_decorator='', css=None):
    """Render a top level entry into the log as a table row.

    Args:
      timestamp: [float] The timestamp for the entry.
      summary: [string] If provided, this is an abbreviation.
      detail: [string] This is the full detail for the entry.
    """
    document_manager = self.__document_manager
    date_str = self.timestamp_to_string(timestamp)

    tr = document_manager.new_tag('tr')
    th = document_manager.make_tag_text('th', date_str, class_='nw')
    td = document_manager.new_tag('td')
    tr.append(th)
    tr.append(td)

    if not summary:
      td.append(detail)
      return tr

    # pylint: disable=bad-continuation
    collapse_html = ('collapse {decorator}'
                         .format(decorator=collapse_decorator)
                     if collapse_decorator
                     else 'collapse')

    section_id = document_manager.new_section_id()
    show = document_manager.make_expandable_control_tag(
        section_id, 'expand')
    hide = document_manager.make_expandable_control_tag(
        section_id, collapse_html)
    detail_tag_attrs, summary_tag_attrs = (
        document_manager.make_expandable_tag_attr_kwargs_pair(
            section_id=section_id, default_expanded=False))

    css_class = None if css is None else css.get('class_')
    show_span = document_manager.make_tag_container(
        'span', [show, summary], class_=css_class, **summary_tag_attrs)

    hide_span = document_manager.make_tag_container(
          'span', [hide, detail], class_=css_class, **detail_tag_attrs)

    td.append(show_span)
    td.append(hide_span)
    return tr

  def render_message(self, message):
    """Default method for rendering a JournalMessage into HTML."""
    text = message.get('_value').strip()

    document_manager = self.__document_manager
    processor = ProcessToRenderInfo(document_manager, self.__entity_manager)

    html_info = HtmlInfo()
    html_format = message.get('format', None)
    if html_format == 'json':
      html_info = processor.process_json_html_if_possible(text)
    else:
      summary = None
      if text is None:
        html = document_manager.make_tag_text('i', 'Empty Message')
      elif html_format != 'pre':
        html = document_manager.make_text_block(text)
      else:
        last_offset = -1

        # pylint: disable=bad-indentation
        # The ff tag here is a custom tag for "Fixed Format"
        # It is like 'pre' but inline rather than block to be more compact.
        num_lines = text.count('\n')
        if num_lines > processor.max_uncollapsable_message_lines:
          last_offset = text.find('\n')
        elif len(text) > processor.max_message_summary_length:
          last_offset = processor.max_message_summary_length - 2*len('expand')

        if last_offset >= 0:
          summary = document_manager.make_tag_text(
              'ff', '{0}...'.format(text[0:last_offset]))
        html = document_manager.make_tag_text('ff', text)

      html_info = HtmlInfo(detail=html, summary=summary)

    self.render_log_tr(message.get('_timestamp'),
                       html_info.summary_block, html_info.detail_block)
