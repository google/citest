import re
from json import JSONDecoder
from json import JSONEncoder


class JsonScrubber(object):
  """Scrubber to redact output from content."""

  REDACTED = '*' * 5

  def __init__(self, regex='(?i)(?:password|secret|private)'):
    self.__re = re.compile(regex)

    base64='[a-zA-Z0-9+/\n]'
    pad='(?:=|\u003d)'
    begin_marker='-+BEGIN [A-Z0-9 ]*KEY-+'
    end_marker='-+END [A-Z0-9 ]*KEY-+'
    self.__key_re = re.compile('(?ms){begin}\n{base64}+{pad}*\n{end}\n'.format(
        begin=begin_marker, base64=base64, pad=pad, end=end_marker))


  def process_text(self, value):
    """Scrub text.
    Args:
      value: The value to scrub.
    Returns:
      scrubbed value.
    """
    match = self.__key_re.search(value)
    if not match:
      return value
    else:
      return self.REDACTED

  def process_list(self, l):
    """Scrub elements of a list.

    Args:
      l: The list to redact from.

    Returns:
      Redacted list.
    """
    result = []
    for e in l:
       if isinstance(e, dict):
         result.append(self.process_dict(e))
       elif isinstance(e, list):
         result.append(self.process_list(e))
       else:
         result.append(e)
    return result

  def process_dict(self, d):
    """Scrub elements of a dictionary.

    Args:
      d: The dictionary to redact from.

    Returns:
      Redacted dict.
    """
    if len(d) == 2:
        keys = d.keys()
        if 'key' in keys and 'value' in keys:
          match = self.__re.search(d['key'])

          if match:
            d['value'] = self.REDACTED
            
    for name, value in d.items():
        match = self.__re.search(name)
        if match:
          d[name] = self.REDACTED
        elif isinstance(value, list):
          d[name] = self.process_list(value)
        elif isinstance(value, dict):
          d[name] = self.process_dict(value)
        elif isinstance(value, basestring):
          d[name] = self.process_text(value)
    return d

  def __call__(self, data):
    """Scrub data.

    Args:
      data: The data to scrub.

    Returns:
      Redacted data.
    """
    if isinstance(data, dict):
        return self.process_dict(data)
    if isinstance(data, list):
        return self.process_list(data)
    if isinstance(data, basestring):
        try:
          d = JSONDecoder().decode(data)
          d = self(d)
          return JSONEncoder().encode(d)
        except:
          pass

    return data
            
