# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import re
import json
import tempfile
import time
import random
import logging
import datetime
import warnings
from http import HTTPStatus
from urllib.parse import urlencode, quote, quote_plus, unquote, urlparse
import aiohttp

from .constants import BASE_URI, HOST, SEARCH_BASE_URI
from .auth import Auth
from .exceptions import ImdbAPIError

logger = logging.getLogger(__name__)


class Imdb(Auth):

    def __init__(self, locale=None, exclude_episodes=False, session=None):
        self.locale = locale or 'en_US'
        self.exclude_episodes = exclude_episodes
        self.session = session or aiohttp.ClientSession()
        self._cachedir = tempfile.gettempdir()

    async def __aenter__(self):
        return self

    async def __aexit__(self, etype, evalue, etb):
        if self.session is not None:
            await self.session.close()

    async def get_name(self, imdb_id):
        logger.info(f'getting name {imdb_id}')
        self.validate_imdb_id(imdb_id)
        return await self._get_resource(f'/name/{imdb_id}/fulldetails')

    async def get_name_filmography(self, imdb_id):
        logger.info(f'getting name {imdb_id} filmography')
        self.validate_imdb_id(imdb_id)
        return await self._get_resource(f'/name/{imdb_id}/filmography')

    async def get_title(self, imdb_id):
        logger.info(f'getting title {imdb_id}')
        self.validate_imdb_id(imdb_id)
        await self._redirection_title_check(imdb_id)
        try:
            resource = await self._get_resource(f'/title/{imdb_id}/auxiliary')
        except LookupError:
            self._title_not_found()

        if (
            self.exclude_episodes is True and
            resource['base']['titleType'] == 'tvEpisode'
        ):
            raise LookupError(
                'Title not found. Title was an episode and '
                '"exclude_episodes" is set to true'
            )
        return resource

    async def get_title_credits(self, imdb_id):
        logger.info(f'getting title {imdb_id} credits')
        self.validate_imdb_id(imdb_id)
        await self._redirection_title_check(imdb_id)
        return await self._get_resource(f'/title/{imdb_id}/fullcredits')

    async def get_title_quotes(self, imdb_id):
        logger.info(f'getting title {imdb_id} quotes')
        self.validate_imdb_id(imdb_id)
        await self._redirection_title_check(imdb_id)
        return await self._get_resource(f'/title/{imdb_id}/quotes')

    async def get_title_ratings(self, imdb_id):
        logger.info(f'getting title {imdb_id} ratings')
        self.validate_imdb_id(imdb_id)
        await self._redirection_title_check(imdb_id)
        return await self._get_resource(f'/title/{imdb_id}/ratings')

    async def get_title_genres(self, imdb_id):
        logger.info(f'getting title {imdb_id} genres')
        self.validate_imdb_id(imdb_id)
        await self._redirection_title_check(imdb_id)
        return await self._get_resource(f'/title/{imdb_id}/genres')

    async def get_title_similarities(self, imdb_id):
        logger.info(f'getting title {imdb_id} similarities')
        self.validate_imdb_id(imdb_id)
        await self._redirection_title_check(imdb_id)
        return await self._get_resource(f'/title/{imdb_id}/similarities')

    async def get_title_awards(self, imdb_id):
        logger.info(f'getting title {imdb_id} awards')
        self.validate_imdb_id(imdb_id)
        await self._redirection_title_check(imdb_id)
        return await self._get_resource(f'/title/{imdb_id}/awards')

    async def get_title_connections(self, imdb_id):
        logger.info(f'getting title {imdb_id} connections')
        self.validate_imdb_id(imdb_id)
        await self._redirection_title_check(imdb_id)
        return await self._get_resource(f'/title/{imdb_id}/connections')

    async def get_title_releases(self, imdb_id):
        logger.info(f'getting title {imdb_id} releases')
        self.validate_imdb_id(imdb_id)
        await self._redirection_title_check(imdb_id)
        return await self._get_resource(f'/title/{imdb_id}/releases')

    async def get_title_versions(self, imdb_id):
        logger.info(f'getting title {imdb_id} versions')
        self.validate_imdb_id(imdb_id)
        await self._redirection_title_check(imdb_id)
        return await self._get_resource(f'/title/{imdb_id}/versions')

    async def get_title_plot(self, imdb_id):
        logger.info(f'getting title {imdb_id} plot')
        self.validate_imdb_id(imdb_id)
        await self._redirection_title_check(imdb_id)
        return await self._get_resource(f'/title/{imdb_id}/plot')

    async def get_title_plot_synopsis(self, imdb_id):
        logger.info(f'getting title {imdb_id} plot synopsis')
        self.validate_imdb_id(imdb_id)
        await self._redirection_title_check(imdb_id)
        return await self._get_resource(f'/title/{imdb_id}/plotsynopsis')

    async def title_exists(self, imdb_id):
        self.validate_imdb_id(imdb_id)
        page_url = f'http://www.imdb.com/title/{imdb_id}/'

        async with self.session.head(page_url) as response:
            if response.status == HTTPStatus.OK:
                return True
            elif response.status == HTTPStatus.NOT_FOUND:
                return False
            elif response.status == HTTPStatus.MOVED_PERMANENTLY:
                # redirection result
                return False
            else:
                response.raise_for_status()

    async def search_for_name(self, name):
        logger.info(f'searching for name {name}')
        name = re.sub(r'\W+', '_', name).strip('_')
        query = quote(name)
        first_alphanum_char = self._query_first_alpha_num(name)
        url = (
            '{0}/suggests/{1}/{2}.json'.format(SEARCH_BASE_URI,
                                               first_alphanum_char, query)
        )
        search_results = await self._get(url=url, query=query)
        results = []
        for result in search_results.get('d', ()):
            if not result['id'].startswith('nm'):
                # ignore non-person results
                continue
            result_item = {
                'name': result['l'],
                'imdb_id': result['id'],
            }
            results.append(result_item)
        return results

    async def search_for_title(self, title):
        logger.info(f'searching for title {title}')
        title = re.sub(r'\W+', '_', title).strip('_')
        query = quote(title)
        first_alphanum_char = self._query_first_alpha_num(title)
        url = (
            '{0}/suggests/{1}/{2}.json'.format(SEARCH_BASE_URI,
                                               first_alphanum_char, query)
        )
        search_results = await self._get(url=url, query=query)
        results = []
        for result in search_results.get('d', ()):
            result_item = {
                'title': result['l'],
                'year': str(result['y']) if result.get('y') else None,
                'imdb_id': result['id'],
                'type': result.get('q'),
            }
            results.append(result_item)
        return results

    async def get_popular_titles(self):
        return await self._get_resource('/chart/titlemeter')

    async def get_popular_shows(self):
        return await self._get_resource('/chart/tvmeter')

    async def get_popular_movies(self):
        return await self._get_resource('/chart/moviemeter')

    async def get_title_images(self, imdb_id):
        logger.info(f'getting title {imdb_id} images')
        self.validate_imdb_id(imdb_id)
        await self._redirection_title_check(imdb_id)
        return await self._get_resource(f'/title/{imdb_id}/images')

    async def get_title_videos(self, imdb_id):
        logger.info(f'getting title {imdb_id} videos')
        self.validate_imdb_id(imdb_id)
        await self._redirection_title_check(imdb_id)
        return await self._get_resource(f'/title/{imdb_id}/videos')

    async def get_title_user_reviews(self, imdb_id):
        logger.info(f'getting title {imdb_id} reviews')
        self.validate_imdb_id(imdb_id)
        await self._redirection_title_check(imdb_id)
        return await self._get_resource(f'/title/{imdb_id}/userreviews')

    async def get_title_metacritic_reviews(self, imdb_id):
        logger.info(f'getting title {imdb_id} metacritic reviews')
        self.validate_imdb_id(imdb_id)
        await self._redirection_title_check(imdb_id)
        return await self._get_resource(f'/title/{imdb_id}/metacritic')

    async def get_name_images(self, imdb_id):
        logger.info(f'getting namne {imdb_id} images')
        self.validate_imdb_id(imdb_id)
        return await self._get_resource(f'/name/{imdb_id}/images')

    async def get_name_videos(self, imdb_id):
        logger.info(f'getting namne {imdb_id} videos')
        self.validate_imdb_id(imdb_id)
        return await self._get_resource(f'/name/{imdb_id}/videos')

    async def get_title_episodes(self, imdb_id):
        logger.info(f'getting title {imdb_id} episodes')
        self.validate_imdb_id(imdb_id)
        if self.exclude_episodes:
            raise ValueError('exclude_episodes is current set to true')
        return await self._get_resource(f'/title/{imdb_id}/episodes')

    @staticmethod
    def _cache_response(file_path, resp):
        with open(file_path, 'w+') as f:
            json.dump(resp, f)

    def _parse_dirty_json(self, data, query=None):
        if query is None:
            match_json_within_dirty_json = r'imdb\$.+\({1}(.+)\){1}'
        else:
            query_match = ''.join(
                char if char.isalnum() else f'[{char}]'
                for char in unquote(query)
            )
            query_match = query_match.replace('[ ]', '.+')
            match_json_within_dirty_json = (
                r'imdb\${}\((.+)\)'.format(query_match)
            )
        data_clean = re.match(
            match_json_within_dirty_json, data, re.IGNORECASE
        ).groups()[0]
        return json.loads(data_clean)

    @staticmethod
    def validate_imdb_id(imdb_id):
        match_id = r'[a-zA-Z]{2}[0-9]{7}'
        try:
            re.match(match_id, imdb_id, re.IGNORECASE).group()
        except (AttributeError, TypeError):
            raise ValueError('invalid imdb id')

    @staticmethod
    def _is_redirection_result(response):
        """
        Return True if response is that of a redirection else False
        Redirection results have no information of use.
        """
        imdb_id = response['data'].get('tconst')
        if (
            imdb_id and
            imdb_id != response['data'].get('news', {}).get('channel')
        ):
            return True
        return False

    async def _get_resource(self, path):
        url = f'{BASE_URI}{path}'
        data = await self._get(url=url)
        return data['resource']

    async def _get(self, url, query=None):
        path = urlparse(url).path
        headers = {'Accept-Language': self.locale}
        headers.update(await self.get_auth_headers(path))

        async with self.session.get(url, headers=headers) as resp:
            if not resp.status == HTTPStatus.OK:
                if resp.status == HTTPStatus.NOT_FOUND:
                    raise LookupError(f'Resource {path} not found')
                else:
                    msg = f'{resp.status} {resp.text}'
                    raise ImdbAPIError(msg)
            resp_data = await resp.text(encoding='utf-8')
            try:
                resp_dict = json.loads(resp_data)
            except ValueError:
                resp_dict = self._parse_dirty_json(
                    data=resp_data, query=query
                )

            if resp_dict.get('error'):
                return None

        return resp_dict

    async def _redirection_title_check(self, imdb_id):
        if await self.is_redirection_title(imdb_id):
            self._title_not_found(msg=f'{imdb_id} is a redirection imdb id')

    async def is_redirection_title(self, imdb_id):
        self.validate_imdb_id(imdb_id)
        page_url = f'http://www.imdb.com/title/{imdb_id}/'
        async with self.session.head(page_url) as response:
            if response.status == HTTPStatus.MOVED_PERMANENTLY:
                return True
            else:
                return False

    def _query_first_alpha_num(self, query):
        for char in query.lower():
            if char.isalnum():
                return char
        raise ValueError(
            'invalid query, does not contain any alphanumeric characters'
        )

    def _title_not_found(self, msg=''):
        if msg:
            msg = f' {msg}'
        raise LookupError(f'Title not found.{msg}')
