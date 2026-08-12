# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_accounts
# Purpose:      Identify the existence of a given account on various sites using
#               the WhatsMyName dataset.
#
# Author:       Steve Micallef <steve@binarypool.com>
# MooSight:     hardened username validation and result quality improvements
# Licence:      MIT
# -------------------------------------------------------------------------------

import json
import random
import threading
import time
from queue import Empty as QueueEmpty
from queue import Queue
from urllib.parse import urlparse

from spiderfoot import SpiderFootEvent, SpiderFootHelpers, SpiderFootPlugin


class sfp_accounts(SpiderFootPlugin):

    meta = {
        'name': "Account Finder",
        'summary': "Look for possible associated accounts across social and other websites using the current WhatsMyName dataset.",
        'useCases': ["Footprint", "Passive"],
        'categories': ["Social Media"]
    }

    opts = {
        "ignorenamedict": True,
        "ignoreworddict": True,
        "musthavename": True,
        "userfromemail": True,
        "permutate": False,
        "usernamesize": 4,
        "allow_insecure_tls": False,
        "_maxthreads": 20
    }

    optdescs = {
        "ignorenamedict": "Don't bother looking up names that are just stand-alone first names (too many false positives).",
        "ignoreworddict": "Don't bother looking up names that appear in the dictionary.",
        "musthavename": "Require the username to appear in returned text when the dataset does not already provide a positive fingerprint.",
        "userfromemail": "Extract usernames from e-mail addresses.",
        "permutate": "Look for similar username permutations. This can be noisy and is disabled by default.",
        "usernamesize": "Minimum username length to query.",
        "allow_insecure_tls": "Allow account checks to bypass TLS certificate verification. Disabled by default.",
        "_maxthreads": "Maximum concurrent account checks."
    }

    results = None
    reportedUsers = list()
    siteResults = dict()
    sites = list()
    errorState = False
    distrustedChecked = False
    lock = None

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.commonNames = list()
        self.reportedUsers = list()
        self.siteResults = dict()
        self.sites = list()
        self.errorState = False
        self.distrustedChecked = False
        self.__dataSource__ = "Social Media"
        self.lock = threading.Lock()

        self.opts = dict(type(self).opts)
        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

        self.commonNames = SpiderFootHelpers.humanNamesFromWordlists()
        self.words = SpiderFootHelpers.dictionaryWordsFromWordlists()

        content = self.sf.cacheGet("sfaccountsv3", 12)
        if content is None:
            url = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"
            data = self.sf.fetchUrl(url, useragent="SpiderFoot")
            if not data or data.get('content') is None:
                self.error(f"Unable to fetch {url}")
                self.errorState = True
                return
            content = data['content']
            self.sf.cachePut("sfaccountsv3", content)

        try:
            rawsites = json.loads(content)['sites']
            self.sites = [
                site for site in rawsites
                if site.get('valid', True) is not False
                and site.get('uri_check')
                and site.get('name')
            ]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self.error(f"Unable to parse social media accounts list: {exc}")
            self.errorState = True

    def watchedEvents(self):
        return ["EMAILADDR", "DOMAIN_NAME", "HUMAN_NAME", "USERNAME"]

    def producedEvents(self):
        return ["USERNAME", "ACCOUNT_EXTERNAL_OWNED", "SIMILAR_ACCOUNT_EXTERNAL"]

    @staticmethod
    def _normalize_username(name):
        if not isinstance(name, str):
            return None
        name = name.strip().strip('"').strip("'").strip()
        if not name or any(c in name for c in ('/', '\\', '\r', '\n', '\t')):
            return None
        return name

    @staticmethod
    def _host(url):
        try:
            return (urlparse(url).hostname or '').lower()
        except (TypeError, ValueError):
            return ''

    @staticmethod
    def _header(headers, name):
        wanted = name.lower()
        for key, value in (headers or {}).items():
            if str(key).lower() == wanted:
                return value
        return ''

    @staticmethod
    def _format_site_value(value, account):
        if not isinstance(value, str):
            return value
        return value.replace('{account}', account)

    @staticmethod
    def _confidence(site):
        """Return evidence strength for a positive username-existence match.

        Confidence describes the quality of the site's detection fingerprint,
        not whether the researched person owns the account.
        """
        expected = bool(site.get('e_string'))
        missing = bool(site.get('m_string'))
        expected_code = site.get('e_code')
        missing_code = site.get('m_code')

        if expected and missing:
            return "HIGH", "site-specific positive and negative fingerprints matched"
        if expected and expected_code is not None:
            return "MEDIUM", "site-specific positive fingerprint and HTTP status matched"
        if missing and expected_code is not None and expected_code != missing_code:
            return "MEDIUM", "HTTP status matched and known missing-page fingerprint was absent"
        return "LOW", "HTTP response and username-presence heuristic matched"

    @staticmethod
    def _result_text(site, ret_url):
        confidence, evidence = sfp_accounts._confidence(site)
        return (
            f"{site['name']} (Category: {site.get('cat', 'unknown')})\n"
            f"Confidence: {confidence}\n"
            f"Evidence: {evidence}\n"
            "Interpretation: username appears to exist on this service; identity/ownership is not established.\n"
            f"<SFURL>{ret_url}</SFURL>"
        )

    def checkSite(self, name, site):
        name = self._normalize_username(name)
        if not name:
            return

        try:
            url = site['uri_check'].format(account=name)
            ret_url = site.get('uri_pretty', site['uri_check']).format(account=name)
        except (KeyError, ValueError, IndexError):
            return

        if not self._host(url) or not url.lower().startswith(('http://', 'https://')):
            return

        retname = self._result_text(site, ret_url)
        post = self._format_site_value(site.get('post_body'), name)
        headers = {
            str(key): self._format_site_value(value, name)
            for key, value in (site.get('headers') or {}).items()
        }

        res = self.sf.fetchUrl(
            url,
            postData=post,
            headers=headers or None,
            timeout=self.opts['_fetchtimeout'],
            useragent=self.opts['_useragent'],
            noLog=True,
            verify=bool(self.opts.get('allow_insecure_tls', False)) is False
        )

        if not res:
            with self.lock:
                self.siteResults[retname] = False
            return

        content = res.get('content')
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='replace')
        elif content is not None and not isinstance(content, str):
            content = str(content)

        code = str(res.get('code') or '')
        if not content:
            with self.lock:
                self.siteResults[retname] = False
            return

        expected_code = site.get('e_code')
        missing_code = site.get('m_code')
        if expected_code != missing_code and code != str(expected_code):
            with self.lock:
                self.siteResults[retname] = False
            return

        expected = site.get('e_string')
        missing = site.get('m_string')
        if expected and expected not in content:
            with self.lock:
                self.siteResults[retname] = False
            return
        if missing and missing in content:
            with self.lock:
                self.siteResults[retname] = False
            return

        if self.opts['musthavename'] and not expected:
            ctype = str(self._header(res.get('headers'), 'content-type')).lower()
            textual = not ctype or any(t in ctype for t in ('text/', 'json', 'javascript', 'xml'))
            if textual and name.lower() not in content.lower():
                self.debug(f"Skipping {site['name']} because the username was not present in the response.")
                with self.lock:
                    self.siteResults[retname] = False
                return

        with self.lock:
            self.siteResults[retname] = True

    def checkSites(self, username, sites=None):
        username = self._normalize_username(username)
        if not username:
            return []

        def processSiteQueue(username, queue):
            while True:
                try:
                    site = queue.get_nowait()
                except QueueEmpty:
                    return
                try:
                    self.checkSite(username, site)
                except Exception as exc:
                    self.debug(f'Thread {threading.current_thread().name} exception: {exc}')
                finally:
                    queue.task_done()

        startTime = time.monotonic()
        self.siteResults = {}
        sites = self.sites if sites is None else sites
        queue = Queue()
        for site in sites:
            queue.put(site)

        threads = []
        for i in range(min(len(sites), int(self.opts['_maxthreads']))):
            thread = threading.Thread(name=f'sfp_accounts_scan_{i}', target=processSiteQueue,
                                      args=(username, queue), daemon=True)
            thread.start()
            threads.append(thread)

        queue.join()
        for thread in threads:
            thread.join(timeout=0.5)

        duration = max(time.monotonic() - startTime, 0.001)
        self.debug(f'Scan statistics: name={username}, sites={len(sites)}, responses={len(self.siteResults)}, duration={duration:.2f}, rate={len(sites) / duration:.0f}')
        return sorted([site for site, found in self.siteResults.items() if found])

    def generatePermutations(self, username):
        permutations = set()
        for marker in ('_', '-'):
            permutations.add(username + marker)
            permutations.add(marker + username)
        return sorted(permutations)

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data
        users = list()

        if self.errorState:
            return
        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventName != "USERNAME" and srcModuleName == "sfp_accounts":
            return
        if eventData in list(self.results.keys()):
            return
        self.results[eventData] = True

        if not self.distrustedChecked:
            content = self.sf.cacheGet("sfaccounts_state_v4", 24)
            if content:
                if content != "None":
                    distrusted = [line for line in content.split("\n") if line]
                    self.sites = [d for d in self.sites if d['name'] not in distrusted]
            else:
                randpool = 'abcdefghijklmnopqrstuvwxyz1234567890'
                randuser = ''.join(random.SystemRandom().choice(randpool) for _ in range(14))
                res = self.checkSites(randuser)
                if res:
                    distrusted = []
                    for site in res:
                        sitename = site.split(" (Category:")[0]
                        self.debug(f"Distrusting {sitename}: it matched a random username.")
                        distrusted.append(sitename)
                    self.sites = [d for d in self.sites if d['name'] not in distrusted]
                    self.sf.cachePut("sfaccounts_state_v4", "\n".join(distrusted))
                else:
                    self.sf.cachePut("sfaccounts_state_v4", "None")
            self.distrustedChecked = True

        if eventName == "HUMAN_NAME":
            users.extend([eventData.lower().replace(" ", ""), eventData.lower().replace(" ", ".")])
        elif eventName == "DOMAIN_NAME":
            kw = self.sf.domainKeyword(eventData, self.opts['_internettlds'])
            if kw:
                users.append(kw)
        elif eventName == "EMAILADDR" and self.opts['userfromemail']:
            users.append(eventData.split("@")[0].lower())
        elif eventName == "USERNAME":
            normalized = self._normalize_username(eventData)
            if normalized:
                users.append(normalized)

        for user in set(users):
            if user in self.opts['_genericusers'].split(","):
                continue
            if self.opts['ignorenamedict'] and user in self.commonNames:
                continue
            if self.opts['ignoreworddict'] and user in self.words:
                continue
            if len(user) < int(self.opts['usernamesize']):
                continue
            if user not in self.reportedUsers and eventData != user:
                evt = SpiderFootEvent("USERNAME", user, self.__name__, event)
                self.notifyListeners(evt)
                self.reportedUsers.append(user)

        if eventName != "USERNAME" or not users:
            return

        user = users[0]
        for site in self.checkSites(user):
            self.notifyListeners(SpiderFootEvent("ACCOUNT_EXTERNAL_OWNED", site, self.__name__, event))

        if self.opts['permutate']:
            for puser in self.generatePermutations(user):
                for site in self.checkSites(puser):
                    self.notifyListeners(SpiderFootEvent("SIMILAR_ACCOUNT_EXTERNAL", site, self.__name__, event))
# End of sfp_accounts class
