import os

def app_version(request):
    sha = os.environ.get('GIT_SHA', 'dev')
    return {'APP_VERSION': sha[:7]}
