import random
from os import environ
from urllib3 import disable_warnings

from locust import HttpLocust, TaskSet, task

class UserBehavior(TaskSet):
    TIMEOUT_SECONDS = 60

    APPLICATIONS = ['dailytelegraph']
    SECTIONS = dict()
    ARTICLES = dict()

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

    def on_start(self):
        """Called when a Locust start before any task is scheduled"""
        self.client.verify = False
        self._headers = {}
        if 'X_ACCESS_TOKEN' in environ:
            self._headers['x-access-token'] = environ['X_ACCESS_TOKEN']

        self.set_sections()

    @task(1)
    def app_task1_root(self):
        self.client.get('/apps/' + self.get_random_application(), headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False)
    
    @task(1)
    def app_task2_top_stories(self):
        self.client.get('/apps/' + self.get_random_application() + '/theaters/top-stories', headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False)

    @task(1)
    def app_task2_sections(self):
        application = self.get_random_application()
        section = self.get_random_item_from_dict(self.SECTIONS, application)
        self.client.get('/apps/' + application + '/theaters/' + section, headers=self._headers, timeout=self.TIMEOUT_SECONDS, verify=False)

class WebsiteUser(HttpLocust):
    task_set = UserBehavior
    min_wait = 1000
    max_wait = 1000