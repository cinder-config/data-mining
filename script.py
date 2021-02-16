import requests
import csv
import numpy as np
import random
import time
import urllib.parse as url

GITHUB_API_TOKEN = "CHANGE_ME"  # GitHub API TOKEN (PRIVATE!!!)
TRAVIS_CI_ORG_TOKEN = "CHANGE_ME"  # GitHub API TOKEN (PRIVATE!!!)
TRAVIS_CI_COM_TOKEN = "CHANGE_ME"  # GitHub API TOKEN (PRIVATE!!!)

WRITE_TO_FILE = 'data/truth.csv'
PROJECTS_CSV = 'data/results.csv'

GITHUB_RATE_LIMIT = 3  # 30 Requests per minute, sleep 3 seconds after every query
languages = ["JavaScript", "Java", "Python", "Ruby", "PHP", "C++"]

medium_projects = {}
small_projects = {}
popupar_projects = {}
big_projects = {}
extracted_projects = []

for lang in languages:
    small_projects[lang] = []
    popupar_projects[lang] = []
    big_projects[lang] = []
    medium_projects[lang] = []

f = open(WRITE_TO_FILE, 'w')
writer = csv.writer(f)
writer.writerow(
    ['id', 'name', 'language', 'description', 'watchers', 'pull_requests', 'commits', 'members', 'issues',
     'bucket', 'full_name'])


def block_until_github_limit_resetted():
    print('Checking GitHub Quota..')
    resp = requests.get("https://api.github.com/rate_limit",
                        headers={'Authorization': "token " + GITHUB_API_TOKEN})
    data = resp.json()
    ts = int(round(time.time(), 0))
    reset = data.get('resources').get('core').get('reset')
    remaining = data.get('resources').get('core').get('remaining')
    if remaining > 0:
        print('We have some quota remaining, yay!')
        return
    if ts > reset:
        print('Yay, time is up, new quota!')
        return
    else:
        print('Sleeping for 10 Seconds...')
        time.sleep(10)
        block_until_github_limit_resetted()


# between 1000 and 5000 commits and at least 10 contributors
def add_if_medium(project):
    if 500 < int(project[6]) < 5000 and int(project[7]) >= 10:
        medium_projects[project[2]].append(project)
        return True
    return False


# less than 1000 commits and 5 contributors
def add_if_small(project):
    if int(project[6]) < 1000 and int(project[7]) < 5:
        small_projects[project[2]].append(project)
        return True
    return False


# More than 100 watchers, 20 contributors and 200 issues
def add_if_popular(project):
    if int(project[4]) > 100 and int(project[7]) > 20 and int(project[8]) > 200:
        popupar_projects[project[2]].append(project)
        return True
    return False


# More than 5000 commits and 500 pull requests
def add_if_big(project):
    if int(project[6]) > 5000 and int(project[5]) > 500:
        big_projects[project[2]].append(project)
        return True
    return False


# Index
# 0 = id
# 1 = url
# 2 = lang
# 3 = description
# 4 = watcher_count
# 5 = pull_request_count
# 6 = commit_count
# 7 = project_member_count
# 8 = issue count

def buckify():
    print('Start bucketing projects')
    start = time.time()
    with open(PROJECTS_CSV, newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        next(reader)
        for row in reader:
            if add_if_big(row):
                continue
            if add_if_popular(row):
                continue
            if add_if_medium(row):
                continue
            if add_if_small(row):
                continue
        print('Done bucketing projects')
        end = time.time()
        print("Took: " + str(end - start) + " seconds")


QUERY_STRING = "repo:%repo%+filename:.travis.yml"


def extract_projects(bucket, lang, amount, identifier):
    found = 0
    candidates = bucket[lang]
    random.shuffle(candidates)
    # Shuffle list
    for candidate in candidates:
        resp = requests.get(candidate[1], headers={'Authorization': "token " + GITHUB_API_TOKEN})
        print("Accessing: " + candidate[1])
        if resp.status_code == 200:
            data = resp.json()
            print("Checking repo " + data.get('full_name') + " for .travis-ci.yml")
            # Exclude Forks, archived, disabled and projects without activity (1 year)
            if data.get('fork') == False and data.get('disabled') == False and data.get(
                    'archived') == False and data.get('pushed_at') > "2019":
                travis_file_resp = requests.get(
                    "https://github.com/" + data.get('full_name') + "/blob/" + data.get(
                        'default_branch') + "/.travis.yml")
                if travis_file_resp.status_code == 200:
                    # Check if exists on TravisCI/ORG
                    travis_ci_org_resp = requests.get(
                        "https://api.travis-ci.org/repo/" + url.quote(data.get('full_name'), safe=''),
                        headers={'Authorization': "token " + TRAVIS_CI_ORG_TOKEN, 'Travis-API-Version': '3'})
                    travis_org = travis_ci_org_resp.json()
                    if travis_org.get('@type') == 'error' or travis_org.get('active') == False:
                        travis_ci_com_resp = requests.get(
                            "https://api.travis-ci.com/repo/" + url.quote(data.get('full_name'), safe=''),
                            headers={'Authorization': "token " + TRAVIS_CI_COM_TOKEN, 'Travis-API-Version': '3'})
                        travis_ci_com = travis_ci_com_resp.json()
                        if travis_ci_com.get('@type') == 'error' or travis_ci_com.get('active') == False:
                            print('Nope...')
                            continue
                    print('Yikes!')
                    candidate.append(identifier)
                    candidate.append(data.get('full_name'))
                    extracted_projects.append(candidate)
                    writer.writerow(candidate)
                    found = found + 1
                else:
                    print('Nope...')
            else:
                print('Does not meet critieria')
        block_until_github_limit_resetted()
        if found == amount:
            print("Found enough projects for lang: " + lang + " and bucket: " + identifier)
            break


def calculate_stats():
    stats = {}
    for lang in languages:
        stats[lang] = {
            'Watchers': list(),
            'PullRequests': list(),
            'Commits': list(),
            'Members': list(),
            'Issues': list(),
        }

    with open('data/results.csv', newline='') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        next(reader)
        index = 0
        for row in reader:
            stats[row[2]]['Watchers'].append(row[4])
            stats[row[2]]['PullRequests'].append(row[5])
            stats[row[2]]['Commits'].append(row[6])
            stats[row[2]]['Members'].append(row[7])
            stats[row[2]]['Issues'].append(row[8])
            index = index + 1
            if index % 100 == 0:
                print(index)

    print("")
    for lang in languages:
        print("Evaluation for " + lang)
        for stat in stats[lang].items():
            np_array = np.array(stat[1], dtype=int)
            print(stat[0] + "\t\t" + "Min: " + str(np_array.min()) + "\t" + "Max: " + str(
                round(np_array.max(), 2)) + "\t" + "Mean: " + str(
                round(np_array.mean(), 2)) + "\t" + "Median: " + str(
                np.median(np_array)))


buckify()
for lang in languages:
    extract_projects(big_projects, lang, 3, "big")
    extract_projects(popupar_projects, lang, 3, "popular")
    extract_projects(medium_projects, lang, 3, "medium")
    extract_projects(small_projects, lang, 15, "small")
