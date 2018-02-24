from fabric.api import *
import fabric.contrib.project as project
from fabric.contrib.console import confirm
import os
import shutil
import sys
import SocketServer

from pelican.server import ComplexHTTPRequestHandler

# Get absolute path of project's root directory
env.project_root = os.path.dirname(env.real_fabfile)
# Set absolute path of project's deploy directory
env.deploy_path = os.path.join(env.project_root, 'output')

# Github Pages configuration
env.github_pages_branch = 'master'
# Local path configuration (can be absolute or relative to fabfile)
env.deploy_path = 'output'
DEPLOY_PATH = env.deploy_path

# Remote server configuration
production = 'root@localhost:22'
dest_path = '/var/www'

# Rackspace Cloud Files configuration settings
env.cloudfiles_username = 'my_rackspace_username'
env.cloudfiles_api_key = 'my_rackspace_api_key'
env.cloudfiles_container = 'my_cloudfiles_container'

# Github Pages configuration
env.github_pages_branch = "master"

# Port for `serve`
PORT = 8000

def clean():
    """Remove generated files"""
    if os.path.isdir(DEPLOY_PATH):
        shutil.rmtree(DEPLOY_PATH)
        os.makedirs(DEPLOY_PATH)
    for root, dirs, files in os.walk(env.deploy_path):
        for name in dirs[:]:
            # Do not recurse into this directory
            dirs.remove(name)
            if name == '.git':
                # Do not remove .git/ directory
                pass
            else:
                shutil.rmtree(os.path.join(root, name))
        for name in files:
            os.remove(os.path.join(root, name))

def build():
    """Build local version of site"""
    local('pelican -s pelicanconf.py')

def rebuild():
    """`build` with the delete switch"""
    local('pelican -d -s pelicanconf.py')

def regenerate():
    """Automatically regenerate site upon file modification"""
    local('pelican -r -s pelicanconf.py')

def serve():
    """Serve site at http://localhost:8000/"""
    os.chdir(env.deploy_path)

    class AddressReuseTCPServer(SocketServer.TCPServer):
        allow_reuse_address = True

    server = AddressReuseTCPServer(('', PORT), ComplexHTTPRequestHandler)

    sys.stderr.write('Serving on port {0} ...\n'.format(PORT))
    server.serve_forever()

def reserve():
    """`build`, then `serve`"""
    build()
    serve()

def preview():
    """Build production version of site"""
    local('pelican -s publishconf.py')

def cf_upload():
    """Publish to Rackspace Cloud Files"""
    rebuild()
    with lcd(DEPLOY_PATH):
        local('swift -v -A https://auth.api.rackspacecloud.com/v1.0 '
              '-U {cloudfiles_username} '
              '-K {cloudfiles_api_key} '
              'upload -c {cloudfiles_container} .'.format(**env))

@hosts(production)
def publish():
    """Publish to production via rsync"""
    local('pelican -s publishconf.py')
    project.rsync_project(
        remote_dir=dest_path,
        exclude=".DS_Store",
        local_dir=DEPLOY_PATH.rstrip('/') + '/',
        delete=True,
        extra_opts='-c',
    )

def gh_pages():
    """Publish to GitHub Pages"""
    # rebuild()
    # local("ghp-import -b {github_pages_branch} {deploy_path} -p".format(**env))
    with lcd(env.project_root):
        # ensure the main git repository is clean
        main_git_unclean = local('git status --untracked-files=no --porcelain',
                                 capture=True)
        if main_git_unclean:
            abort("\n".join(["The main git repository is not clean:",
                             main_git_unclean]))
        # get main git repository's HEAD's sha checksum
        main_commit_sha = local('git rev-parse --short HEAD', capture=True)

    with lcd(env.deploy_path):
        # sync local GitHub Pages git repository with remote repository
        local('git fetch origin {github_pages_branch}'.format(**env))
        local('git reset --hard origin {github_pages_branch}'.format(**env))

    clean()
    # build a production version of the site
    preview()

    with lcd(env.deploy_path):
        pages_git_unclean = local('git status --porcelain', capture=True)
        if pages_git_unclean:
            local('git add --all')
            local('git commit -m "Build of source repo @ {}"'.format(main_commit_sha))
            if confirm("Do you wish to publish the current version of the "
                       "page to GitHub Pages?", default=False):
                local('git push origin {github_pages_branch}'.format(**env))
                commit_sha = local('git rev-parse --short HEAD', capture=True)
                puts("Pushed commit {} to GitHub Pages".format(commit_sha))
            else:
                # reset the git repo to the one on GitHub Pages
                local('git reset origin -- master')
                puts("Exiting on user request.")
        else:
            puts("Nothing has changed. Exiting.")



def publish():
    """Publish to GitHub Pages"""
    gh_pages()

