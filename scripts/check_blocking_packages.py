#!/usr/bin/env python

import argparse

import rosdistro

import rosdistro.dependency_walker
# Inputs: distribution name
# Default is latest

# TODO: Give an argument, "depth", which specifies how far into the dependency tree to look

index = rosdistro.get_index(rosdistro.get_index_url())
valid_distribution_keys = index.distributions.keys()
valid_distribution_keys.sort()

parser = argparse.ArgumentParser(description='')
parser.add_argument('--distro', metavar='distribution', type=str,
    help='The distribution to check packages for', default=valid_distribution_keys[-1])

# If not specified, check for all repositories in the previous distribution
parser.add_argument('--repositories', metavar='repositories', type=str, nargs='*',
    help='The unreleased repositories to check the dependencies for')

args = parser.parse_args()

distribution_key = args.distro
repository_names = args.repositories
prev_distribution_key = None

# Find the previous distribution to the current one
for key, i in zip(valid_distribution_keys, range(len(valid_distribution_keys))):
    if key == distribution_key:
        assert i > 0
        prev_distribution_key = valid_distribution_keys[i-1]
        break

distribution = rosdistro.get_cached_distribution(index, distribution_key)
prev_distribution = rosdistro.get_cached_distribution(index, prev_distribution_key)

distribution_file = rosdistro.get_distribution_file(index, distribution_key)
prev_distribution_file = rosdistro.get_distribution_file(index, prev_distribution_key)

dependency_walker = rosdistro.dependency_walker.DependencyWalker(prev_distribution)

if repository_names is None:
    # Check missing dependencies for packages that were in the previous distribution that
    # have not yet been released in the current distribution
    # Crawl the previous distribution file for all packages previously released 
    prev_repository_names = set(prev_distribution_file.get_data()['repositories'].keys())
else:
    # Check the input arguments and remove any entries that were already released.
    prev_repository_names = set(repository_names)

current_repository_names = set(distribution_file.get_data()['repositories'].keys())
repository_names_set = prev_repository_names.difference(current_repository_names)
if len(repository_names_set) == 0:
    if repository_names is None:
        print "Everything in distribution {0} was released into the next distribution {1}! This was either a bug, or we did a great job with the new release.".format(prev_distribution_key, distribution_key)
    else:
        print "All requested repositories have already been released into distribution " + distribution_key
    exit(0)

repository_names = list(repository_names_set)


# Get a list of currently released packages
current_package_names = set()

for repo in current_repository_names:
    repo_data = distribution_file.get_data()['repositories'][repo]['release']
    if repo_data.has_key('packages'):
        current_package_names = current_package_names | set(repo_data['packages'])
    else:
        # Assume the repo name is the same as the package name
        current_package_names.add(repo)

# Construct a dictionary where keys are repository names and values are a list of the missing
# dependencies for that repository
# TODO: Could also check which packages are blocked by the input package
# since DependencyWalker offers a get_depends_on() function
blocked_packages = {}
for repository_name in repository_names:
    # Check all the dependencies for the repository
    # Get all packages (based on info from the previous repository)
    repo_data = prev_distribution_file.get_data()['repositories'][repository_name]
    # Check if the repo has a release, skip it if it doesn't
    if not repo_data.has_key('release'):
        # This repo doesn't have a release entry; skip it (should we warn the user?)
        continue
    if not repo_data['release'].has_key('version'):
        # This repo doesn't have a valid version so it's technically not released, skip it
        continue
    package_dependencies = set()
    if repo_data['release'].has_key('packages'):
        packages = repo_data['release']['packages']
    else:
        packages = [repository_name]
    # Accumulate all dependencies for those packages
    # TODO: could implement depth here easily by using get_recursive_depends
    for package in packages:
        print package
        build_package_dependencies = dependency_walker.get_depends(package, 'build', ros_packages_only=True)
        package_dependencies = package_dependencies.union(build_package_dependencies)
        run_package_dependencies = dependency_walker.get_depends(package, 'run', ros_packages_only=True)
        package_dependencies = package_dependencies.union(run_package_dependencies)
        #recursive_package_dependencies = dependency_walker.get_recursive_depends(package, ['build', 'run', 'buildtool'], ros_packages_only=True)
    # For all package dependencies, check if they are released yet
    # TODO: List the repos that need to be released, not the packages

    unreleased_packages = package_dependencies.difference(current_package_names)
    # remove the packages which this repo provides.
    unreleased_packages = unreleased_packages.difference(packages)
    blocked_packages[repository_name] = unreleased_packages

print blocked_packages
