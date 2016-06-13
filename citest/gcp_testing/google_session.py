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

import requests

from bs4 import BeautifulSoup

class GoogleSession(object):
  """Utility class for automating HTTP sessions with Google.

  Automates both the Google account login and scope approval to create an
  authenticated HTTP session, and provides access to the session cookies
  for use with urllib2 Requests.

  Example usage:
    # login_url should forward to 'accounts.google.com/ServiceLogin' page
    # via an OAuth2 or SAML redirect.
    login_url = "http://<gate_host>/credentials"
    logout_url = "http://<gate_host>/auth/logout"
    session = GoogleSession(login_url,
                           "user@domain.net",
                           "secret_pass_word",
                           logout_url=logout_url)
    cookie_jar = session.cookies
    req = urllib2.Request(url=login_url)
    cookie_jar.add_cookie_header(req)
    resp = urllib2.urlopen(req)
    session.logout()
  """


  def __init__(
      self, login_url, login, password,
      user_approval_url ='https://accounts.google.com/ServiceLoginAuth',
      logout_url=None):
    """Construct an instance.

    Args:
      login_url: [String] A URL that will eventually redirect to
        'https://accounts.google.com/ServiceLogin'.
      login: [String] Username/email to login as.
      password: [String] Password for the provided login.
      user_approval_url: [String] (Optional) The URL for a Google user to grant approval
        to an application. Can override if necessary.
      logout_url: [String] (Optional) The logout url of the application we are
        authenticating to.
    """
    self.__session = requests.session()
    login_html = self.__session.get(login_url)
    login_form_inputs = (BeautifulSoup(login_html.content)
        .find('form')
        .find_all('input'))
    login_dict = {}
    for input in login_form_inputs:
      if input.has_attr('value'):
        login_dict[input['name']] = input['value']

    login_dict['Email'] = login
    login_dict['Passwd'] = password
    post_response = self.__session.post(user_approval_url, data=login_dict)
    approval_form = BeautifulSoup(post_response.content).find('form')

    approval_dict = {}
    for input in approval_form.find_all('input'):
      if input.has_attr('value'):
        approval_dict[input['name']] = input['value']
    approval_dict['submit_access'] = 'true'
    self.__session.post(approval_form['action'], data=approval_dict)
    self.__logout_url = logout_url


  def logout(self):
    """Log out of the current authenticated Google session and the target
    service's session if applicable.
    """
    if self.__logout_url:
      self.__session.post(self.__logout_url)
    self.__session.post("https://www.google.com/accounts/Logout")
    self.__session.cookies = None


  @property
  def cookies(self):
    """Get the HTTP session cookies from the current Google session.

    Returns:
      The collection of Cookie objects associated with the authenticated Google
      session as a CookieJar object.
      CookieJar documentation: https://docs.python.org/2.7/library/cookielib.html#cookiejar-and-filecookiejar-objects
    """
    if self.__session.cookies is None:
      raise AttributeError()
    return self.__session.cookies
