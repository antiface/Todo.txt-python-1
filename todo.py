#!/usr/bin/env python

# TODO.TXT-CLI-python
# Copyright (C) 2011  Sigmavirus24
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# 
# TLDR: This is licensed under the GPLv3. See LICENSE for more details.

import os
import re
import string
import sys
from optparse import OptionParser
from datetime import datetime, date

VERSION = "0.1-optgit_dev"
REVISION = "$Id$"

try:
	import readline
except ImportError:
	# This isn't crucial to the execution of the script.
	# But it is a nice feature to have. Sucks to be an OSX user.
	pass

try:
	intern = intern
except NameError:
	# Python 3 moved the built-in intern() to sys.intern()
	intern = sys.intern

try:
	PRIORITIES = string.uppercase[0:24]
except AttributeError:
	# Python 3 again
	PRIORITIES = string.ascii_uppercase[0:24]

# concat() is necessary long before the grouping of function declarations
concat = lambda str_list, sep='': sep.join(str_list)
_path = lambda p: os.path.abspath(os.path.expanduser(p))
_pathc = lambda plist: _path(concat(plist))
_git = None

TERM_COLORS = {
		"black" : "\033[0;30m", "red" : "\033[0;31m",
		"green" : "\033[0;32m", "brown" : "\033[0;33m",
		"blue" : "\033[0;34m", "purple" : "\033[0;35m",
		"cyan" : "\033[0;36m", "light grey" : "\033[0;37m",
		"dark grey" : "\033[1;30m", "light red" : "\033[1;31m",
		"light green" : "\033[1;32m", "yellow" : "\033[1;33m",
		"light blue" : "\033[1;34m", "light purple" : "\033[1;35m",
		"light cyan" : "\033[1;36m", "white" : "\033[1;37m",
		"default" : "\033[0m", "reverse" : "\033[7m",
		"bold" : "\033[1m",
		}

FROM_CONFIG = {}
TO_CONFIG = {}
for key in TERM_COLORS.keys():
	bkey = concat(["$", re.sub(' ', '_', key).upper()])
	FROM_CONFIG[bkey] = key
	TO_CONFIG[key] = bkey
del(key, bkey)  # If someone were to import this as a module, these show up.

TODO_DIR = _path('~/.todo')

CONFIG = {
		"TODO_DIR" : TODO_DIR,
		"TODOTXT_DEFAULT_ACTION" : "",
		"TODOTXT_CFG_FILE" : _pathc([TODO_DIR, "/config"]),
		"TODO_FILE" : _pathc([TODO_DIR, "/todo.txt"]),
		"TMP_FILE" : _pathc([TODO_DIR, "/todo.tmp"]),
		"DONE_FILE" : _pathc([TODO_DIR, "/done.txt"]),
		"REPORT_FILE" : _pathc([TODO_DIR, "/report.txt"]),
		"USE_GIT" : False,
		"GIT" : None,
		"PLAIN" : False,
		"NO_PRI" : False,
		"PRE_DATE" : False,
		"INVERT" : False,
		"HIDE_PROJ" : False,
		"HIDE_CONT" : False,
		"HIDE_DATE" : False,
		"LEGACY" : False,
		}

for p in PRIORITIES:
	CONFIG["PRI_{0}".format(p)] = "default"
del(p, TODO_DIR)


### Helper Functions
def todo_padding():
	lines = [1 for line in iter_todos()]
	i = len(lines)
	pad = 1
	while i >= 10:
		pad += 1
		i /= 10
	return pad


def iter_todos():
	"""
	Opens the file in read-only mode, and returns an iterator for the todos.
	"""
	tfile=CONFIG["TODO_FILE"]
	if not os.path.isfile(tfile):
		return
	with open(CONFIG["TODO_FILE"]) as fd:
		for line in fd:
			yield line


def separate_line(number):
	"""
	Takes an integer and returns a string and a list. The string is the item at
	that position in the list. The list is the rest of the todos.
	"""
	lines = [line for line in iter_todos()]
	if lines:
		separate = lines.pop(number - 1)
	else:
		separate = None
	return separate, lines


def rewrite_file(fd, lines):
	"""
	Simple wrapper for three lines used all too frequently.
	Sets the access position to the beginning of the file, truncates the
	file's length to 0 and then writes all the lines to the file.
	"""
	fd.seek(0, 0)
	fd.truncate(0)
	fd.writelines(lines)


def rewrite_and_post(line_no, old_line, new_line, lines):
	"""
	Wraps the following code used frequently in post-production functions.
	"""
	with open(CONFIG["TODO_FILE"], "w") as fd:
		rewrite_file(fd, lines)
	post_success(line_no, old_line, new_line)


def _git_err(g):
	"""
	Print any errors that result from GitPython and exit.
	"""
	if g.stderr:
		print(g.stderr)
	else:
		print(g)
	sys.exit(g.status)


def _git_pull():
	"""
	Pull any commits that exist on the remote to the local repository.
	"""
	try:
		print(CONFIG["GIT"].pull())
	except _git.exc.GitCommandError, g:
		_git_err(g)


def _git_push():
	"""
	Push commits made locally to the remote.
	"""
	try:
		s = CONFIG["GIT"].push()
	except _git.exc.GitCommandError, g:
		_git_err(g)
	if s:
		print(s)
	else:
		print("TODO: 'git push' executed.")


def _git_status():
	"""
	Print the status of the local repository if the version of git is 1.7
	or later.
	"""
	try:
		print(CONFIG["GIT"].status())
	except _git.exc.GitCommandError, g:
		_git_err(g)


def _git_log():
	"""
	Print the two latest commits in the local repository's log.
	"""
	lines = CONFIG["GIT"].log("-2")
	flines = []
	commit_re = re.compile("commit")
	for line in lines.split("\n"):
		if commit_re.match(line):
			flines.append(concat([TERM_COLORS["yellow"],
				line[:-1], TERM_COLORS["default"], "\n"]))
		else:
			flines.append(concat([line, "\n"]))

	flines[-1] = flines[-1][:-1]
	print(concat(flines))


def _git_commit(files, message):
	"""
	Make a commit to the git repository.
		* files should be a list like ['file_a', 'file_b'] or ['-a']
	"""
	try:
		CONFIG["GIT"].commit(files, "-m", message)
	except _git.exc.GitCommandError, g:
		_git_err(g)
	if "-a" not in files:
		print(concat(["TODO: ", concat(files, ", "), " archived."]))
	else:
		print(concat(["TODO: ", CONFIG["TODO_DIR"], " archived."]))


def prompt(*args, **kwargs):
	"""
	Sanitize input collected with raw_input().
	Prevents someone from entering 'y\' to attempt to break the program.

	args can be any collection of strings that require formatting.
	kwargs will collect the tokens and values.
	"""
	args = list(args)  # [a for a in args]
	args.append(' ')
	prompt_str = concat(args)
	prompt_str = prompt_str.format(**kwargs)
	input = raw_input(prompt_str)
	return re.sub(r"\\", "", input)


def print_x_of_y(x, y):
	t_str = "--\nTODO: {0} of {1} tasks shown"
	if len(x) > len(y):  # EXTREMELY hack-ish
		print(t_str.format(len(y), len(y)))  # There can't logically be
			# more lines of items to do than there actually are.
	else:
		print(t_str.format(len(x), len(y)))
### End Helper Functions


### Configuration Functions
def import_git():
	if CONFIG["USE_GIT"]:
		_import_gitpython()
	else:
		_gitpython_mock()

	CONFIG["GIT"] = _git.Git(CONFIG["TODO_DIR"])

def _import_gitpython():
	global _git
	try:
		import git
	except ImportError:
		if sys.version_info < (3, 0):
				print("You must download and install GitPython from: \
http://pypi.python.org/pypi/GitPython")
		else:
			print("GitPython is not available for Python3 last I checked.")
		sys.exit(52)
	_git = git

def _gitpython_mock():
	global _git
	class git_mock:
		class Git:
			def __init__(self, foo):
				pass
			def add(self, name):
				pass
			def pull(self):
				pass
			def push(self):
				pass
			def status(self):
				pass
			def log(self):
				pass
			def ls_files(self):
				return ()
			def commit(self, *args):
				pass
		class exc:
			class GitCommandError:
				pass
	_git = git_mock

def get_config(config_name="", dir_name=""):
	"""
	Read the config file
	"""
	if config_name:
		CONFIG["TODOTXT_CFG_FILE"] = config_name
	if dir_name:
		CONFIG["TODO_DIR"] = _path(dir_name)

	if not CONFIG["TODOTXT_CFG_FILE"]:
		config_file = concat([CONFIG["TODO_DIR"], "/config"])
	else:
		config_file = CONFIG["TODOTXT_CFG_FILE"]

	config_file = _path(config_file)
	if not (os.access(CONFIG["TODO_DIR"], 
		os.F_OK | os.R_OK | os.W_OK | os.X_OK) and \
			os.access(config_file, os.F_OK | os.R_OK | os.W_OK)):
		default_config()
	else:
		f = open(config_file, 'r')
		skip_re = re.compile('^\s*(#|$)')
		strip_re = re.compile('\w+\s([A-Za-z_$="./]+).*')
		pri_re = re.compile('(PRI_[A-X]|DEFAULT)')

		with open(config_file, 'r') as f:
			for line in f:
				if not skip_re.match(line):
					# Extract VAR=VAL and then split VAR and VAL
					items = strip_re.sub('\g<1>', line.strip()).split('=')
					items[1] = items[1].strip('"')

					if pri_re.match(items[0]):
						CONFIG[items[0]] = FROM_CONFIG[items[1]]
					else:
						items[1] = os.path.expandvars(items[1])
						CONFIG[items[0]] = items[1]

					# make expandvars work for our vars too
					os.environ[items[0]] = items[1]

	import_git()
	repo = CONFIG["GIT"]
	if CONFIG["TODOTXT_CFG_FILE"] not in repo.ls_files():
		repo.add([CONFIG["TODOTXT_CFG_FILE"]])


def repo_config(yes_re):
	"""
	Help the user configure their git repository.
	"""
	from getpass import getuser
	from os import getenv
	g = CONFIG["GIT"]
	# local configuration
	try:
		user_name = g.config("--global", "--get", "user.name")
	except:
		user_name = getuser()

	try:
		user_email = g.config("--global", "--get", "user.email")
	except:
		user_email = concat([user.name, "@", getenv("HOSTNAME")])

	print("First configure your local repository options.")
	ret = prompt("git config user.name ", user_name, "?")
	if ret:
		user_name = ret
	ret = prompt("git config user.email ", user_email, "?")
	if ret:
		user_email = ret

	g.config("user.name", user_name)
	g.config("user.email", user_email)

	# remote configuration
	ret = prompt("Would you like to add a remote repository?")
	if yes_re.match(ret):
		remote_host = None
		remote_path = None
		remote_user = None
		remote_branch = None

		while not remote_host:
			remote_host = prompt("Remote hostname:")
			if not remote_host:
				print("Please enter the remote's hostname.")
		while not remote_path:
			remote_path = prompt("Remote path:")
			if not remote_path:
				print("Please enter the path to the remote's repository.")
		while not remote_user:
			remote_user = prompt("Remote user:")
			if not remote_user:
				print("Please enter the user on the remote machine.")
		while not remote_branch:
			remote_branch = prompt("Remote branch:")
			if not remote_branch:
				print("Please enter the branch to push to on the remote machine.")
		prompt("Press enter when you have initialized a bare\n",
			" repository on the remote or are ready to proceed.")
		local_branch = g.branch()
		if not local_branch:
			local_branch = "master"
		else:
			branch_re = re.compile('^\*\s.*')
			for l in local_branch.split("\n"):
				if branch_re.match(l):
					local_branch = branch_re.sub("", l)
					break

		g.remote("add", "origin", concat([remote_user, "@", remote_host,
				":", remote_path]))
		g.config(concat(["branch.", local_branch, ".remote"]), "origin")
		g.config(concat(["branch.", local_branch, ".merge"]),
				concat(["refs/heads/", remote_branch]))
	# TODO: if config file isn't in TODO_DIR, this will cause an error
	files=[CONFIG["TODOTXT_CFG_FILE"], CONFIG["TODO_FILE"]]
	for setting in ["DONE_FILE", "REPORT_FILE", "TMP_FILE"]:
		if CONFIG[setting]:
			files.append(CONFIG[setting])
	g.add(files)
	g.commit("-m", CONFIG["TODO_PY"] + " initial commit.")

def init_repo():
	repo = CONFIG["GIT"]
	try:
		v = repo.status()
	except _git.exc.GitCommandError, g:
		val = prompt("Would you like to create a new git repository in\n ",
				CONFIG["TODO_DIR"], "? [y/N]")
		yes_re = re.compile('y(?:es)?', re.I)
		if yes_re.match(val):
			print(repo.init())
			val = prompt("Would you like {prog} to help\n you",
			" configure your new git repository? [y/n]",
			prog=CONFIG["TODO_PY"])
			if yes_re.match(val):
				repo_config(yes_re)

def default_config():
	"""
	Set up the default configuration file.
	"""

	# set the defaults for the colors
	CONFIG["PRI_A"] = "yellow"
	CONFIG["PRI_B"] = "green"
	CONFIG["PRI_C"] = "light blue"
	CONFIG["PRI_X"] = "white"

	val = prompt("Do you want to use git? [y/N]")
	yes_re = re.compile('y(?:es)?', re.I)
	if yes_re.match(val):
		CONFIG["USE_GIT"] = True
	else:
		CONFIG["USE_GIT"] = False
	import_git()

	def touch(filename):
		"""
		Create files if they aren't already there.
		"""
		open(filename, "w").close()

	if not os.path.exists(CONFIG["TODO_DIR"]):
		os.makedirs(CONFIG["TODO_DIR"])

	# touch/create files needed for the operation of the script
	for item in ['TODO_FILE', 'TMP_FILE', 'DONE_FILE', 'REPORT_FILE']:
		if CONFIG[item]:
			touch(CONFIG[item])

	cfg = open(concat([CONFIG["TODO_DIR"], "/config"]), 'w')
	for k, v in CONFIG.items():
		if v and k not in ("GIT", "INVERT", "LEGACY", "PLAIN", "PRE_DATE",
				"HIDE_DATE", "HIDE_CONT", "HIDE_PROJ", "NO_PRI"):
			if v == True or v == False:
				v = int(v)
			if v in TO_CONFIG.keys():
				cfg.write(concat(["export ", k, "=", TO_CONFIG[v], "\n"]))
			else:
				cfg.write(concat(["export ", k, '="', str(v), '"\n']))
	init_repo()
	cfg.close()

	print(concat(["Default configuration completed. Please ",
		"re-run\n {prog} with '-h' and 'help' separately.".format(
			prog=CONFIG["TODO_PY"])]))
	sys.exit(0)
### End Config Functions


### New todo Functions
def add_todo(args):
	"""
	Add a new item to the list of things todo.
	"""
	l = len(args)
	if str(args) == args:
		line = args
	elif l == 1:
		line = args[0]
	elif l > 1:
		line = " ".join(args)
	else:
		line = raw_input("Add: ")
	prepend = CONFIG["PRE_DATE"]
	l = len([1 for l in iter_todos()]) + 1
	pri_re = re.compile('(\([A-X]\))')
	if pri_re.match(line) and prepend:
		line = pri_re.sub(concat(["\g<1>",
			datetime.now().strftime(" %Y-%m-%d ")]),
			line)
	elif prepend:
		line = concat([datetime.now().strftime("%Y-%m-%d "), line])
	with open(CONFIG["TODO_FILE"], "a") as fd:
		fd.write(concat([line, "\n"]))
	s = "TODO: '{0}' added on line {1}.".format(
		line, l)
	print(s)
	_git_commit([CONFIG["TODO_FILE"]], s)


def addm_todo(args):
	"""
	Add new items to the list of things todo.
	"""
	if str(args) == args:
		lines = args
	else:
		lines = " ".join(args)
	lines = lines.split("\n")
	map(add_todo, lines)
### End new todo functions


### Start do/del functions
def do_todo(line):
	"""
	Mark an item on a specified line as done.
	"""
	if not line.isdigit():
		print("Usage: {0} do item#".format(CONFIG["TODO_PY"]))
	else:
		removed, lines = separate_line(int(line))

		fd = open(CONFIG["TODO_FILE"], "w")
		rewrite_file(fd, lines)
		fd.close()

		today = datetime.now().strftime("%Y-%m-%d")
		removed = re.sub("\([A-X]\)\s?", "", removed)
		removed = "x " + today + " " + removed

		files = [CONFIG["TODO_FILE"]]
		dfile = CONFIG["DONE_FILE"]
		if dfile:
			fd = open(dfile, "a")
			fd.write(removed)
			fd.close()
			files.append(dfile)

		print(removed[:-1])
		print("TODO: Item {0} marked as done.".format(line))
		_git_commit(files, removed)


def delete_todo(line):
	"""
	Delete an item without marking it as done.
	"""
	if not line.isdigit():
		print("Usage: {0} (del|rm) item#".format(CONFIG["TODO_PY"]))
	else:
		removed, lines = separate_line(int(line))

		fd = open(CONFIG["TODO_FILE"], "w")
		rewrite_file(fd, lines)
		fd.close()

		removed = "'{0}' deleted.".format(removed[:-1])
		print(removed)
		print("TODO: Item {0} deleted.".format(line))
		_git_commit([CONFIG["TODO_FILE"]], removed)
### End do/del Functions


### Post-production todo functions
def post_error(command, arg1, arg2):
	"""
	If one of the post-production todo functions isn't given the proper
	arguments, the function calls this to notify the user of what they need to
	supply.
	"""
	if arg2:
		print(concat(["'", CONFIG["TODO_PY"], " ", command, "' requires a(n) ",
			arg1, " then a ", arg2, "."]))
	else:
		print(concat(["'", CONFIG["TODO_PY"], " ", command, "' requires a(n) ",
			arg1, "."]))


def post_success(item_no, old_line, new_line):
	"""
	After changing a line, pring a standard line and commit the change.
	"""
	old_line = old_line.rstrip()
	new_line = new_line.rstrip()
	print_str = "TODO: Item {0} changed from '{1}' to '{2}'.".format(
		item_no, old_line, new_line)
	print(print_str)
	_git_commit([CONFIG["TODO_FILE"]], print_str)


def append_todo(args):
	"""
	Append text to the item specified.
	"""
	if args[0].isdigit():
		line_no = int(args.pop(0))
		old_line, lines = separate_line(line_no)
		new_line = concat([concat([old_line[:-1], concat(args, " ")],  " "), "\n"],)
		lines.insert(line_no - 1, new_line)

		rewrite_and_post(line_no, old_line, new_line, lines)
	else:
		post_error('append', 'NUMBER', 'string')


def prioritize_todo(args):
	"""
	Add or modify the priority of the specified item.
	"""
	if len(args) == 2 and args[0].isdigit() and len(args[1]) == 1 and args[1] in PRIORITIES:
		line_no = int(args.pop(0))
		old_line, lines = separate_line(line_no)
		new_pri = concat(["(", args[0], ") "])
		r = re.match("(\([A-X]\)\s).*", old_line)
		if r:
			new_line = re.sub(re.escape(r.groups()[0]), new_pri, old_line)
		else:
			new_line = concat([new_pri, old_line])

		lines.insert(line_no - 1, new_line)

		rewrite_and_post(line_no, old_line, new_line, lines)
	else:
		post_error('pri', 'NUMBER', 'capital letter in [A-X]')


def de_prioritize_todo(number):
	"""
	Remove priority markings from the beginning of the line if they're there.
	Don't complain otherwise.
	"""
	if number.isdigit():
		number = int(number)
		old_line, lines = separate_line(number)
		new_line = re.sub("(\([A-X]\)\s)", "", old_line)
		lines.insert(number - 1, new_line)

		rewrite_and_post(number, old_line, new_line, lines)
	else:
		post_err('depri', 'NUMBER', None)


def prepend_todo(args):
	"""
	Take in the line number and prepend the rest of the arguments to the item
	specified by the line number.
	"""
	if args[0].isdigit():
		line_no = int(args.pop(0))
		prepend_str = concat(args, " ") + " "
		old_line, lines = separate_line(line_no)
		pri_re = re.compile('^(\([A-X]\)\s)')

		if pri_re.match(old_line):
			new_line = pri_re.sub(concat( ["\g<1>", prepend_str]), old_line)
		else:
			new_line = concat([prepend_str, old_line])

		lines.insert(line_no - 1, new_line)

		rewrite_and_post(line_no, old_line, new_line, lines)
	else:
		post_error('prepend', 'NUMBER', 'string')
### End Post-production todo functions


### HELP
def cmd_help():
	print(concat(["Use", CONFIG["TODO_PY"], "-h for option help"], " "))
	print("")
	print(concat(["Usage:", CONFIG["TODO_PY"], "command [arg(s)]"], " "))
	print('\tadd | a "Item to do +project @context #{yyyy-mm-dd}"')
	print("\t\tAdds 'Item to do +project @context #{yyyy-mm-dd}' to your todo.txt")
	print("\t\tfile.")
	print("\t\t+project, @context, #{yyyy-mm-dd} are optional")
	print("")
	print('\taddm "First item to do +project @context #{yyyy-mm-dd}')
	print("\t\tSecond item to do +project @context #{yyyy-mm-dd}")
	print("\t\t...")
	print("\t\tLast item to do +project @context #{yyyy-mm-dd}")
	print("\t\tAdds each line as a separate item to your todo.txt file.")
	print("")
	print('\tappend | app NUMBER "text to append"')
	print('\t\tAppend "text to append" to item NUMBER.')
	print("")
	print("\tdepri | dp NUMBER")
	print("\t\tRemove the priority of the item on line NUMBER.")
	print("")
	print("\tdo NUMBER")
	print("\t\tMarks item with corresponding number as done and moves it to")
	print("\t\tyour done.txt file.")
	print("")
	print("\tlist | ls")
	print("\t\tLists all items in your todo.txt file sorted by priority.")
	print("")
	print("\tlistcon | lsc")
	print("\t\tLists all items in your todo.txt file sorted by context.")
	print("")
	print("\tlistdate | lsd")
	print("\t\tLists all items in your todo.txt file sorted by date.")
	print("")
	print("\tlistproj | lsp")
	print("\t\tLists all items in your todo.txt file sorted by project title.")
	print("")
	print("\thelp | h")
	print("\t\tShows this message and exits.")
	print("")
	print('\tprepend | pre NUMBER "text to prepend"')
	print('\t\tAdd "text to prepend" to the beginning of the item.')
	print("")
	print("\tpri | p NUMBER [A-X]")
	print("\t\tAdd priority specified (A, B, C, etc.) to item NUMBER.")
	if CONFIG["USE_GIT"]:
		print("")
		print("\tpull")
		print("\t\tPulls from the remote for your git repository.")
		print("")
		print("\tpush")
		print("\t\tPushs to the remote for your git repository.")
		print("")
		print("\tstatus")
		print("\t\tIf using $(git --version) > 1.7, shows the status of your")
		print("\t\tlocal git repository.")
		print("")
		print("\tlog")
		print("\t\tShows the last two commits in your local git repository.")
	sys.exit(0)
### HELP


### List Printing Functions
def format_lines(color_only=False):
	"""
	Take in a list of lines to do, return them formatted with the TERM_COLORS
	and organized based upon priority.
	"""
	def _m(i):
		formatted[i] = []
	plain = CONFIG["PLAIN"]
	default = TERM_COLORS[CONFIG.get("DEFAULT", "default")] if not plain else ""
	no_priority = CONFIG["NO_PRI"]
	category = ""
	invert = TERM_COLORS["reverse"] if CONFIG["INVERT"] else ""

	formatted = []
	if not color_only:
		formatted = {}
		map(_m, PRIORITIES)

	pri_re = re.compile('^\(([A-W])\)\s')
	pad = todo_padding()
	for (i, line) in enumerate(iter_todos()):
		r = pri_re.match(line)
		if r:
			category = r.groups()[0]
			if plain:
				color = default
			else:
				k = CONFIG["PRI_{0}".format(category)]
				if k in TERM_COLORS.keys():
					color = TERM_COLORS[k]
				else:
					color = default
			if no_priority:
				line = pri_re.sub("", line)
		else:
			category = "X"
			color = default

		j = i + 1
		l = concat([color, invert, str(j).zfill(pad), " ", line[:-1], default, "\n"])
		if color_only:
			formatted.append(l)
		else:
			formatted[category].append(l)

	return formatted


def _legacy_sort(items):
	"""
	Sort items alphabetically, i.e.
	# (pri_a) Abc
	# (pri_a) Bcd
	# (pri_b) Abc
	# (pri_c) Bcd
	etc., etc., etc.
	"""
	line_re = re.compile('^.*\d+\s(\([A-X]\)\s)?')
	# The .* in the regexp is needed for the \033[* codes
	items = [(line_re.sub("", i), i) for i in items]
	items.sort()
	items = [line for (k, line) in items]
	return items


def _list_(by, regexp):
	"""
	Master list_*() function.
	"""
	nonetype = concat(["no", by])
	todo = {nonetype : []}
	by_list = []
	sorted = []

	if by in ["date", "project", "context"]:
		lines = format_lines(color_only=True)
		regexp = re.compile(regexp)
		for line in lines:
			r = regexp.findall(line)
			if r:
				line = concat(["\t", line])
				if by == "date":
					for tup in r:
						d = date(int(tup[0]), int(tup[1]), int(tup[2]))
						if d not in by_list:
							by_list.append(d)
							todo[d] = [line]
						else:
							todo[d].append(line)
				elif by in ["project", "context"]:
					for i in r:
						if i not in by_list:
							by_list.append(i)
							todo[i] = [line]
						else:
							todo[i].append(line)
			else:
				todo[nonetype].append(line)

	elif by == "pri":
		lines = format_lines()
		todo.update(lines)
		by_list = list(PRIORITIES)

	by_list.sort()

	hide_proj_re = re.compile('(\+\w+\s?)')
	hide_cont_re = re.compile('(@\w+\s?)')
	hide_date_re = re.compile('(#\{\d+-\d+-\d+\}\s?)')

	for b in by_list:
		if CONFIG["HIDE_PROJ"]:
			todo[b] = [hide_proj_re.sub("", l) for l in todo[b]]
		if CONFIG["HIDE_CONT"]:
			todo[b] = [hide_cont_re.sub("", l) for l in todo[b]]
		if CONFIG["HIDE_DATE"]:
			todo[b] = [hide_date_re.sub("", l) for l in todo[b]]
		if CONFIG["LEGACY"]:
			todo[b] = _legacy_sort(todo[b])
		if by != "pri":
			sorted.append(concat([str(b), ":\n"]))
		sorted.extend(todo[b])

	sorted.extend(todo[nonetype])
	return (lines, sorted)


def _list_by_(*args):
	"""
	print lines matching items in args
	"""
	esc = re.escape  # keep line length down
	relist = [re.compile(concat(["\s?(", esc(arg), ")\s?"])) for arg in args]
	del(esc)  # don't need it anymore

	alines = format_lines() # Retrieves all lines.
	lines = []
	for p in PRIORITIES:
		lines.extend(alines[p])

	alines = lines[:]
	matched_lines = []

	for regexp in relist:
		matched_lines = [line for line in lines if regexp.search(line)]
		lines = matched_lines[:]
	
	if lines:
		print(concat(lines)[:-1])
	print_x_of_y(lines, alines)


def list_todo(args=None, plain=False, no_priority=False):
	"""
	Print the list of todo items in order of priority and position in the
	todo.txt file.
	"""
	if not args:
		lines, sorted = _list_("pri", "")
		print(concat(sorted)[:-1])
		print_x_of_y(sorted, sorted)
	else:
		_list_by_(*args)


def list_date():
	"""
	List todo items by date #{yyyy-mm-dd}.
	"""
	lines, sorted = _list_("date", "#\{(\d{4})-(\d{1,2})-(\d{1,2})\}")
	print(concat(sorted)[:-1])
	print_x_of_y(sorted, lines)


def list_project():
	"""
	Organizes items by project +prj they belong to.
	"""
	lines, sorted = _list_("project", "\+(\w+)")
	print(concat(sorted)[:-1])
	print_x_of_y(sorted, lines)


def list_context():
	"""
	Organizes items by context @context associated with them.
	"""
	lines, sorted = _list_("context", "@(\w+)")
	print(concat(sorted)[:-1])
	print_x_of_y(sorted, lines)
### End LP Functions


### Callback functions for options
def version(option, opt, value, parser):
	print("""TODO.TXT Command Line Interface v{version}

First release:
Original conception by: Gina Trapani (http://ginatrapani.org)
Original version project: https://github.com/ginatrapani/todo.txt-cli/
Contributors to original: https://github.com/ginatrapani/todo.txt-cli/network
Python version: https://github.com/sigmavirus24/Todo.txt-python/
Contributors to python version: \
https://github.com/sigmavirus24/Todo.txt-python/network
License: GPLv3
Code repository: \
https://github.com/sigmavirus24/Todo.txt-python/tree/master""".format(
	version=VERSION))
	sys.exit(0)


def toggle_opt(option, opt_str, val, parser):
	"""
	Check opt_str to see if it's one of ['-+', '-@', '-#', '-p', '-P', '-t',
	'--plain-mode', '--no-priority', '--prepend-date', '-i',
	'--invert-colors'] and toggle that option in CONFIG.
	"""
	toggle_dict = {"-+" : "HIDE_PROJ", "-@" : "HIDE_CONT", "-#" : "HIDE_DATE",
			"-p" : "PLAIN", "-P" : "NO_PRI", "-t" : "PRE_DATE",
			"--plain-mode" : "PLAIN", "--no-priority" : "NO_PRI",
			"--prepend-date" : "PRE_DATE", "-i" : "INVERT",
			"--invert-colors" : "INVERT", "-l" : "LEGACY",
			"--legacy" : "LEGACY",
			}
	if opt_str in toggle_dict.keys():
		CONFIG[toggle_dict[opt_str]] = not CONFIG[toggle_dict[opt_str]]
### End callback functions


### Main components
def opt_setup():
	opts = OptionParser("Usage: %prog [options] action [arg(s)]")
	opts.add_option("-c", "--config", dest="config", default="",
			type="string",
			nargs=1,
			help=concat(["Supply your own configuration file,",
				"must be an absolute path"])
			)
	opts.add_option("-d", "--dir", dest="todo_dir", default="",
			type="string",
			nargs=1,
			help="Directory you wish {prog} to use.".format(
				prog=CONFIG["TODO_PY"])
			)
	opts.add_option("-p", "--plain-mode", action="callback",
			callback=toggle_opt,
			help="Toggle coloring of items"
			)
	opts.add_option("-P", "--no-priority", action="callback",
			callback=toggle_opt,
			help="Toggle display of priority labels"
			)
	opts.add_option("-t", "--prepend-date", action="callback",
			callback=toggle_opt,
			help="Toggle whether the date is prepended to new items."
			)
	opts.add_option("-V", "--version", action="callback",
			callback=version,
			nargs=0,
			help="Print version, license, and credits"
			)
	opts.add_option("-i", "--invert-colors", action="callback",
			callback=toggle_opt,
			help="Toggle coloring the text of items or background of items."
			)
	opts.add_option("-l", "--legacy", action="callback",
			callback=toggle_opt,
			help="Toggle organization of items in the old manner."
			)
	opts.add_option("-+", action="callback", callback=toggle_opt,
			help="Toggle display of +projects in-line with items."
			)
	opts.add_option("-@", action="callback", callback=toggle_opt,
			help="Toggle display of @contexts in-line with items."
			)
	opts.add_option("-#", action="callback", callback=toggle_opt,
			help="Toggle display of #{dates} in-line with items."
			)
	return opts


import_git()
if __name__ == "__main__" :
	CONFIG["TODO_PY"] = sys.argv[0]
	opts = opt_setup()

	valid, args = opts.parse_args()

	get_config(valid.config, valid.todo_dir)

	commands = {
			# command 	: ( Args, Function),
			"a"			: ( True, add_todo),
			"add"		: ( True, add_todo),
			"addm"		: ( True, addm_todo),
			"app"		: ( True, append_todo),
			"append"	: ( True, append_todo),
			"do"		: ( True, do_todo),
			"p"			: ( True, prioritize_todo),
			"pri"		: ( True, prioritize_todo),
			"pre"		: ( True, prepend_todo),
			"prepend"	: ( True, prepend_todo),
			"dp"		: ( True, de_prioritize_todo),
			"depri"		: ( True, de_prioritize_todo),
			"del"		: ( True, delete_todo),
			"rm"		: ( True, delete_todo),
			"ls"		: ( True, list_todo),
			"list"		: ( True, list_todo),
			"lsc"		: (False, list_context),
			"listcon"	: (False, list_context),
			"lsd"		: (False, list_date),
			"listdate"	: (False, list_date),
			"lsp"		: (False, list_project),
			"listproj"	: (False, list_project),
			"h"			: (False, cmd_help),
			"help"		: (False, cmd_help),
			}
	if CONFIG["USE_GIT"]:
		commands.update(
				[("push", (False, _git_push)),
				("pull", (False, _git_pull)),
				("status", (False, _git_status)),
				("log", (False, _git_log))]
				)

	commandsl = [intern(key) for key in commands.keys()]

	if not len(args) > 0:
		args.append(CONFIG["TODOTXT_DEFAULT_ACTION"])

	allwords_re = re.compile('(p(?:ri)?|(app|pre)(?:end)?)')

	while args:
		# ensure this doesn't error because of a faulty CAPS LOCK key
		arg = args.pop(0).lower()
		if arg in commandsl:
			if not commands[arg][0]:
				commands[arg][1]()
			else:
				if allwords_re.match(arg) or arg in ["ls", "list", "a", "add", "addm"]:
					commands[arg][1](args)
					args = None
				else:
					commands[arg][1](args.pop(0))
		else:
			commandsl.sort()
			commandsl = ["\t" + i for i in commandsl]
			print("Unable to find command: {0}".format(arg))
			print("Valid commands: ")
			print(concat(commandsl, "\n"))
			sys.exit(1)


# vim:set noet:
