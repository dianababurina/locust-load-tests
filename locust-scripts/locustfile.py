import random
from os import environ
from urllib3 import disable_warnings
from datetime import datetime

from locust import HttpLocust, TaskSet, task

disable_warnings()

LOGGER_INFO_FILE = "locustfile-info.log"
LOGGER_ERROR_FILE = "locustfile-error.log"

def extract_data(data, path_fragments):
    child_path = path_fragments.pop(0)
    is_array = child_path.endswith('[]')

    if is_array: child_path = child_path[:len(child_path) - 2]
    if not child_path in data: return []
    
    child_data = data[child_path]
    if (child_data is None): return []
    
    if len(path_fragments) == 0:
        if (isinstance(child_data, str)): return [child_data]
        if (isinstance(child_data, list)): return child_data
        return [child_data]
        
    if (is_array and isinstance(child_data, list)):
        results = []
        for item in child_data:
            results.extend(extract_data(item, path_fragments[:]))
        return results
        
    return extract_data(child_data, path_fragments)

def get_random_value(list):
    return random.choice(list)

def extract_frames(screen_response, frame_type, extract_value):
    extracted_frames = []
    frames = extract_data(screen_response, 'screens[].frames[]'.split('.'))

    for frame in frames:
        if frame['type'] == frame_type:
            extracted_frames.append(frame[extract_value])

    return extracted_frames

def get_random_item_from_dict(dict, application):
    return random.choice(dict.get(application, []))

class UserBehavior(TaskSet):
    TIMEOUT_SECONDS = 60

    APPLICATIONS = ['dailytelegraph']
    HOROSCOPES_ZODIAC_SIGNS = ['aquarius', 'pisces', 'aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra', 'scorpio', 'sagittarius', 'capricorn']
    COMICS = ['calvin-and-hobbes', 'dilbert', 'garfield', 'mark-knight-cartoons', 'valdmans-view']
    PODCASTS_MAP = { 'dailytelegraph': 'dt', 'couriermail': 'cm', 'heraldsun': 'hs', 'adelaidenow': 'aa' }

    SECTIONS = dict()
    ARTICLES = dict()
    LIVE_SCORES_CENTRE = dict()
    SPORT_STATISTICS = list()
    
    MAX_SECTIONS_FOR_ARTICLES_REQUEST = 5

    def logger(self, type, message):
        logger_file = self.LOGGER_ERROR if type == 'error' else self.LOGGER_INFO
        logger_file.write(f'[{datetime.today().strftime("%Y-%m-%d-%H:%M:%S")}] {message} \n')
            
    def check_payload(self, response):
        json_var = response.json()
        id = json_var['id']
        screens = json_var['screens']
        frames = screens[0]['frames'] if len(screens) > 0 else []

        if len(frames) < 1 or response.status_code != 200:
            response.failure("No frames")
            self.logger('error', f'id: {id}, http status: {response.status_code}, total payload (bytes): {len(response.content)}, number of frames: {len(frames)}, url: {response.url}')
        else:
            self.logger('info', f'id: {id}, http status: {response.status_code}, total payload (bytes): {len(response.content)}, number of frames: {len(frames)}')

    def set_sections_screens(self):
        # set sections -> collection theaters
        if self.application not in self.SECTIONS or len(self.SECTIONS.get(self.application, [])) == 0:
            app_response = self.client.get(f'/apps/{self.application}', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='app response').json() 
            
            for theater in app_response['theaters']:
                theater_id = theater['id']
                if theater_id.endswith('--collection') and not theater_id == 'top-stories--collection':
                    self.SECTIONS[self.application] = self.SECTIONS.get(self.application, []) + [theater_id]

    def set_articles(self, section_response, application):
        frames = extract_data(section_response, 'screens[].frames[]'.split('.'))
        for frame in frames:
            if frame['type'] == 'article':
                self.ARTICLES[application] = self.ARTICLES.get(application, []) + [{ 'theater_id': frame['theaterId'], 'article_id': frame['articleId'] }]

    def set_top_stories_articles_screens(self):
        # set top stories articles -> article theater + screen ids
        if self.application not in self.ARTICLES or len(self.ARTICLES.get(self.application, [])) == 0:
            top_stories_response = self.client.get(f'/apps/{self.application}/theaters/top-stories', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='top stories')
            self.set_articles(top_stories_response, self.application)    
            
    def set_section_articles_screens(self):
        # set section articles -> article theater + screen ids
        if self.application not in self.ARTICLES or len(self.ARTICLES.get(self.application, [])) == 0:
            for _ in range(0, self.MAX_SECTIONS_FOR_ARTICLES_REQUEST):
                section = get_random_item_from_dict(self.SECTIONS, self.application)
                section_response = self.client.get(f'/apps/{self.application}/theaters/{section}', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='sections').json()
                self.set_articles(section_response, self.application)

    def set_live_scores_centre_screens(self):
        # set live scores centre -> theater + screen ids
        if len(self.LIVE_SCORES_CENTRE.keys()) == 0:
            app_response = self.client.get(f'/apps/{self.application}', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='app response').json()

            for theater in app_response['theaters']:
                theater_id = theater['id']
                if theater_id.endswith('-live-scores-centre'):
                    screen_ids = theater['screenIds']
                    self.LIVE_SCORES_CENTRE[theater_id] = self.LIVE_SCORES_CENTRE.get(theater_id, []) + screen_ids

    def set_sport_event_statistics_screens(self):
        # set sport event statistics -> theater + screen ids
        if len(self.SPORT_STATISTICS) == 0:
            theater_id = get_random_value(list(self.LIVE_SCORES_CENTRE.keys()))
            screen_id = get_random_value(self.LIVE_SCORES_CENTRE.get(theater_id, []))
            live_scores_response = self.client.get(f'/apps/{self.application}/theaters/{theater_id}?screen_ids={screen_id}', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='live scores centre').json()

            sport_event_statistics_screen_ids = extract_frames(live_scores_response, 'metrosSportLiveScore', 'screenIds')
            for screen_id in sport_event_statistics_screen_ids:
                self.SPORT_STATISTICS.extend(screen_id)

    def extract_podcast_categories(self, application):
        podcasts_response = self.client.get(f'/apps/{application}/theaters/podcasts?screen_ids={self.PODCASTS_MAP.get(application)}/channels', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='podcast channels').json()
        return extract_frames(podcasts_response, 'podcastCategory', 'articleId')
    
    def extract_podcast_channels(self, application):
        podcasts_response = self.client.get(f'/apps/{application}/theaters/podcasts?screen_ids={self.PODCASTS_MAP.get(application)}/channels', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='podcast channels').json()
        return extract_frames(podcasts_response, 'podcastChannel', 'articleId')

    def extract_podcast_episodes(self, application):
        podcast_channel_ids = self.extract_podcast_channels(application)
        channel_id = get_random_value(podcast_channel_ids)
        podcasts_channel_response = self.client.get(f'/apps/{application}/theaters/podcasts?screen_ids={channel_id}', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='podcast channel episodes').json()
        return extract_frames(podcasts_channel_response, 'podcastEpisode', 'articleId')

    def on_start(self):
        """Called when a Locust start before any task is scheduled"""
        self.client.verify = False
        self._headers = {
            'device-type': 'phone'
        }
        if 'X_ACCESS_TOKEN' in environ:
            self._headers['x-access-token'] = environ['X_ACCESS_TOKEN']

        self.application = random.choice(self.APPLICATIONS)

        self.set_sections_screens()
        self.set_top_stories_articles_screens()
        self.set_section_articles_screens()
        self.set_live_scores_centre_screens()
        self.set_sport_event_statistics_screens()

        self.LOGGER_INFO = open(LOGGER_INFO_FILE, "a")
        self.LOGGER_ERROR = open(LOGGER_ERROR_FILE, "a")

    def on_stop(self):
        self.LOGGER_INFO.close()
        self.LOGGER_ERROR.close()

    @task(1)
    def app_task_1_root(self):
        self.client.get(f'/apps/{self.application}', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='app response')
    
    @task(1)
    def app_task_2_top_stories(self):
        with self.client.get(f'/apps/{self.application}/theaters/top-stories', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='top stories', catch_response=True) as response:
            self.check_payload(response)

    @task(1)
    def app_task_3_sections(self):
        section = get_random_item_from_dict(self.SECTIONS, self.application)
        with self.client.get(f'/apps/{self.application}/theaters/{section}', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='sections', catch_response=True) as response:
            self.check_payload(response)

    @task(1)
    def app_task_4_articles(self):
        article = get_random_item_from_dict(self.ARTICLES, self.application)
        with self.client.get(f'/apps/{self.application}/theaters/{article.get("theater_id")}?screen_ids={article.get("article_id")}', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='articles', catch_response=True) as response:
            self.check_payload(response)

    @task(1)
    def app_task_5_horoscopes(self):
        with self.client.get(f'/apps/{self.application}/theaters/horoscopes-home?screen_ids=horoscopes', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='horoscopes home', catch_response=True) as response:
            self.check_payload(response)

    @task(1)
    def app_task_6_horoscopes_zodiac_sign(self):
        zodiac_sign = get_random_value(self.HOROSCOPES_ZODIAC_SIGNS)
        with self.client.get(f'/apps/{self.application}/theaters/horoscopes?screen_ids={zodiac_sign}', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='horoscopes zodiac sign', catch_response=True) as response:
            self.check_payload(response)

    @task(1)
    def app_task_7_comics_home(self):
        with self.client.get(f'/apps/{self.application}/theaters/comics-home?screen_ids=comics', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='comics home', catch_response=True) as response:
            self.check_payload(response)

    @task(1)
    def app_task_8_comics_info(self):
        comics_name = get_random_value(self.COMICS)
        with self.client.get(f'/apps/{self.application}/theaters/comics?screen_ids={comics_name}', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='comics info', catch_response=True) as response:
            self.check_payload(response)

    @task(1)
    def app_task_9_podcast_channels(self):
        with self.client.get(f'/apps/{self.application}/theaters/podcasts?screen_ids={self.PODCASTS_MAP.get(self.application)}/channels', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='podcast channels', catch_response=True) as response:
            self.check_payload(response)

    @task(1)
    def app_task_10_podcast_category_channels(self):
        podcast_category_id = get_random_value(self.extract_podcast_categories(self.application))
        with self.client.get(f'/apps/{self.application}/theaters/podcasts?screen_ids={podcast_category_id}/channels', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='podcast category channels', catch_response=True) as response:
            self.check_payload(response)

    @task(1)
    def app_task_11_podcast_channel_episodes(self):
        podcast_channel_id = get_random_value(self.extract_podcast_channels(self.application))
        with self.client.get(f'/apps/{self.application}/theaters/podcasts?screen_ids={podcast_channel_id}', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='podcast channel episodes', catch_response=True) as response:
            self.check_payload(response)

    @task(1)
    def app_task_12_podcast_episode(self):
        podcast_episode_id = get_random_value(self.extract_podcast_episodes(self.application))
        with self.client.get(f'/apps/{self.application}/theaters/podcasts?screen_ids={podcast_episode_id}', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='podcast episode', catch_response=True) as response:
            self.check_payload(response)

    @task(1)
    def app_task_13_live_scorres_centre(self):
        theater_id = get_random_value(list(self.LIVE_SCORES_CENTRE.keys()))
        screen_id = get_random_value(self.LIVE_SCORES_CENTRE.get(theater_id, []))
        with self.client.get(f'/apps/{self.application}/theaters/{theater_id}?screen_ids={screen_id}', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='live scores centre', catch_response=True) as response:
            self.check_payload(response)

    @task(1)
    def app_task_14_sport_event_statistics(self):
        statistics_screen_id = get_random_value(self.SPORT_STATISTICS)
        with self.client.get(f'/apps/{self.application}/theaters/sports-event-statistics?screen_ids={statistics_screen_id}', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False, name='sport event statistics', catch_response=True) as response:
            self.check_payload(response)


class WebsiteUser(HttpLocust):
    task_set = UserBehavior
    min_wait = 1000
    max_wait = 1000