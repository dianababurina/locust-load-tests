import random
from os import environ
from urllib3 import disable_warnings

from locust import HttpLocust, TaskSet, task

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

class UserBehavior(TaskSet):
    TIMEOUT_SECONDS = 60

    APPLICATIONS = ['dailytelegraph']
    HOROSCOPES_ZODIAC_SIGNS = ['aquarius', 'pisces', 'aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo', 'libra', 'scorpio', 'sagittarius', 'capricorn']
    COMICS = ['calvin-and-hobbes', 'dilbert', 'garfield', 'mark-knight-cartoons', 'valdmans-view']

    SECTIONS = dict()
    ARTICLES = dict()
    
    MAX_SECTIONS_FOR_ARTICLES_REQUEST = 5

    def get_random_application(self):
        return random.choice(self.APPLICATIONS)

    def insert_to_dict(self, dict, item):
        for application in self.APPLICATIONS:
            dict[application] = dict.get(application, []) + [item]

    def get_random_item_from_dict(self, dict, application):
        return random.choice(dict.get(application))

    def set_sections(self):
        # set sections -> collection theaters
        for application in self.APPLICATIONS:
            app_response = self.client.get('/apps/' + application, headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False).json()
            
            for theater in app_response['theaters']:
                theater_id = theater['id']
                if theater_id.endswith('--collection') and not theater_id == 'top-stories--collection':
                    self.SECTIONS[application] = self.SECTIONS.get(application, []) + [theater_id]  

    def set_articles(self, section_response, application):
        frames = extract_data(section_response, 'screens[].frames[]'.split('.'))
        for frame in frames:
            if frame['type'] == 'article':
                self.ARTICLES[application] = self.ARTICLES.get(application, []) + [{ 'theater_id': frame['theaterId'], 'article_id': frame['articleId'] }]

    def set_top_stories_articles(self):
        for application in self.APPLICATIONS:
            top_stories_response = self.client.get('/apps/' + application + '/theaters/top-stories', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False)
            self.set_articles(top_stories_response, application)
            
    def set_section_articles(self):
        for _ in range(0, self.MAX_SECTIONS_FOR_ARTICLES_REQUEST):
            application = self.get_random_application()
            section = self.get_random_item_from_dict(self.SECTIONS, application)
            
            section_response = self.client.get('/apps/' + application + '/theaters/' + section, headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False).json()
            self.set_articles(section_response, application)

    def on_start(self):
        """Called when a Locust start before any task is scheduled"""
        self.client.verify = False
        self._headers = {}
        if 'X_ACCESS_TOKEN' in environ:
            self._headers['x-access-token'] = environ['X_ACCESS_TOKEN']

        self.set_sections()
        self.set_top_stories_articles()
        self.set_section_articles()

    @task(1)
    def app_task1_root(self):
        self.client.get('/apps/' + self.get_random_application(), headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False)
    
    @task(1)
    def app_task2_top_stories(self):
        self.client.get('/apps/' + self.get_random_application() + '/theaters/top-stories', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False)

    @task(1)
    def app_task3_sections(self):
        application = self.get_random_application()
        section = self.get_random_item_from_dict(self.SECTIONS, application)
        self.client.get('/apps/' + application + '/theaters/' + section, headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False)

    @task(1)
    def app_task4_articles(self):
        application = self.get_random_application()
        article = self.get_random_item_from_dict(self.ARTICLES, application)
        self.client.get('/apps/' + application + '/theaters/' + article['theater_id'] + '?screen_ids=' + article['article_id'], headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False)

    @task(1)
    def app_task5_horoscopes(self):
        application = self.get_random_application()
        self.client.get('/apps/' + application + '/theaters/horoscopes-home?screen_ids=horoscopes', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False)

    @task(1)
    def app_task6_horoscopes_zodiac_sign(self):
        application = self.get_random_application()
        zodiac_sign = get_random_value(self.HOROSCOPES_ZODIAC_SIGNS)
        self.client.get('/apps/' + application + '/theaters/horoscopes?screen_ids=' + zodiac_sign, headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False)

    @task(1)
    def app_task7_comics_home(self):
        application = self.get_random_application()
        self.client.get('/apps/' + application + '/theaters/comics-home?screen_ids=comics', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False)

    @task(1)
    def app_task8_comics_info(self):
        application = self.get_random_application()
        comics_name = get_random_value(self.COMICS)
        self.client.get('/apps/' + application + '/theaters/comics?screen_ids=' + comics_name, headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False)


class WebsiteUser(HttpLocust):
    task_set = UserBehavior
    min_wait = 1000
    max_wait = 1000