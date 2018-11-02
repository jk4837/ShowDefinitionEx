import sublime
import sublime_plugin
import re
import time

DEBUG = True
DEBUG = False
lastSymbol = None
lastStartTime = time.time()

def plugin_loaded():
	pass

def htmlEncode(html):
	return html.replace('&', '&amp;').replace('>', '&gt;').replace('<', '&lt;').replace(' ', '&nbsp;')

def symplify_path(path):
	s = path.split('/');
	count = 2
	if count*2 < len(s):
		return '/'.join(s[0:count] + ['..'] + s[-count:])
	return path

def get_file_ex(path):
	if path.endswith('Makefile'):
		return 'Makefile'
	return path[path.rfind('.')+1:]

def file_related(ex1, ex2):
	related_list = [['h', 'c', 'hpp', 'cpp'], ['js', 'css'], ['py', 'pyc'], ['php'], ['cs'], ['pl']]
	if ex1 == ex2:
		return True
	for r_list in related_list:
		rt1 = True if ex1 in r_list else False
		rt2 = True if ex2 in r_list else False
		if rt1 and rt2:
			return True
		elif not rt1 and not rt2:
			continue
	return False

hide_view = None
hide_view_filename = None
def get_lint_file(filename, own_file):
	global DEBUG, hide_view, hide_view_filename
	ex = get_file_ex(filename)
	own_ex = get_file_ex(own_file)
	if ex in ['css']:	# Not index file extension
		# print('skip css file')
		return
	if not file_related(ex, own_ex):
		# print('skip none related file', (ex, own_ex))
		return

	if hide_view is None:
		hide_view = sublime.active_window().create_output_panel("_show_definition", True)
	if DEBUG:
		sublime.active_window().run_command('show_panel', {'panel': 'output._show_definition'})
		sublime.active_window().focus_view(hide_view)

	if hide_view_filename == filename:
		print('skip reopen file')
		return hide_view

	content = None
	try:
		with open(filename, 'r', encoding = 'utf8') as file:
			content = file.read()
		# print('Open file:', filename)
		global open_cnt
		open_cnt += 1
	except Exception as e:
		print(e, 'Cant open file:', filename)
		return

	hide_view_filename = filename

	hide_view.run_command("select_all")
	hide_view.run_command("left_delete")
	hide_view.run_command("append", {"characters": content})
	# test hide_view.settings().get("syntax", {"extension": ex})
	if ex in ['h', 'cpp', 'hpp']:
		hide_view.assign_syntax("C++.sublime-syntax")
	elif ex in ['py', 'pyc']:
		hide_view.assign_syntax("Python.sublime-syntax")
	elif ex in ['c']:
		hide_view.assign_syntax("C.sublime-syntax")
	elif ex in ['js']:
		hide_view.assign_syntax("JavaScript.sublime-syntax")
	elif ex in ['Makefile']:
		hide_view.assign_syntax("Makefile.sublime-syntax")
	elif ex in ['php']:
		hide_view.assign_syntax("PHP.sublime-syntax")
	elif ex in ['cs']:
		hide_view.assign_syntax("C#.sublime-syntax")
	elif ex in ['pl']:
		hide_view.assign_syntax("PERL.sublime-syntax")
	elif ex in ['css']:
		hide_view.assign_syntax("CSS.sublime-syntax")
	return hide_view

clean_name = re.compile('^\s*(public\s+|private\s+|protected\s+|static\s+|function\s+|def\s+)+', re.I)
def parse_scope_full_name(view, region_row, region_col):
	global DEBUG
	view.sel().clear()
	pt = view.text_point(region_row, region_col)
	view.sel().add(sublime.Region(pt, pt))
	is_class = view.match_selector(pt, 'entity.name.class')
	if DEBUG:
		view.show(view.text_point(region_row, region_col))

	s = ''
	found = False

	# Look for any classes
	class_point = None
	class_regions = view.find_by_selector('entity.name.class')
	for r in reversed(class_regions):
		row, col = view.rowcol(r.begin())
		if row <= region_row:
			class_point = r.begin()
			s += view.substr(r)
			found = True
			break;

	function_point = None
	if not is_class:
		# Look for any functions
		function_regions = view.find_by_selector('entity.name.function')
		if function_regions:
			for r in reversed(function_regions):
				if r.contains(pt):
					function_point = r.begin()
					if s:
						s += "::"
					lines = view.substr(r).splitlines()
					name = clean_name.sub('', lines[0])
					if True :
						s += name.strip()
					else:
						if 'C++' in view.settings().get('syntax'):
							if len(name.split('(')[0].split('::'))<2: # True
								s += name.split('(')[0].strip()
							else:
								s += name.split('(')[0].split('::')[1].strip()
						else:
							s += name.split('(')[0].split(':')[0].strip()
					found = True
					break
		# for parens wrap
		if function_point:
			function_params = view.find_by_selector('meta.function.parameters | meta.method.parameters')
			if function_params:
				for r in function_params:
					if function_point < r.begin():
						s += view.substr(r)
						# print('arg' , view.rowcol(function_point) , view.rowcol(r.begin()), ': ', view.substr(r))
						break;

	if found:
		s = ('O ' if class_point == pt or function_point == pt else 'X ') + s
		return s

	# Not found, just capture the line and do something
	length = view.line(pt).end() - pt + 1
	s = view.substr(view.line(pt)).strip(' ;\t{}(')
	s_next = s
	while len(s_next) > length and '' != s_next:
		s, _, s_next = s_next.partition(' ')

	return '? ' + s + ' ' + s_next

class ShowDefinitionCommand(sublime_plugin.WindowCommand):
	def run(self, startTime, symbol, point):
		global open_cnt
		open_cnt = 0
		global lastStartTime
		# print('point: ', point)
		# if symbol is None:
		# 	view = self.window.active_view()
		# 	symbol = view.substr(view.word(view.sel()[0]))

		symbol_list = self.window.lookup_symbol_in_index(symbol)
		if 0 == len(symbol_list):
			print('no symbol_list of', symbol)
			sublime.status_message("")
			return

		view = self.window.active_view()
		em = view.em_width()
		own_file = view.file_name()
		own_row, own_col = view.rowcol(point)
		max_popup_width, max_popup_height = view.viewport_extent()
		# print('popup', (max_popup_width, max_popup_height))
		max_len = 0
		content_list = []
		self.display_list = []
		for idx, loc in enumerate(symbol_list):
			if startTime != lastStartTime:
				print('skip update')
				return
			if  own_file == loc[0] and own_row == loc[2][0]-1:
				print('skip own_file:', loc[0], ':', own_row+1, ':', loc[2][1])
				continue
			view = get_lint_file(loc[0], own_file)
			scope_name = None
			if view:
				scope_name = parse_scope_full_name(view, loc[2][0]-1, loc[2][1]-1)
			else:
				continue

			scope_name = scope_name.replace('\n', '')
			scope_name = scope_name.replace('\t', '')
			scope_name = scope_name.replace('\r', ' ')
			scope_name = scope_name.replace('  ', ' ')
			max_len = max(max_len, len(scope_name))
			self.display_list.append(idx)
			content_list.append(scope_name)

			if DEBUG:
				break # only show first match
				pass

		for idx in range(len(self.display_list)):
			self.display_list[idx] = symbol_list[self.display_list[idx]]

		str_tpl = '<code>%s</code><small style="padding-left:%dpx"><a href=%d>%s:%d:%d</a></small>'
		if 0 != len(content_list):
			if startTime != lastStartTime:
				print('skip update')
			content = '<h3 style="padding:-20 0 -12 0">Definition of %s:</h3>' % symbol
			content += '<br>'.join([str_tpl % (htmlEncode(content_list[idx]), (max_len-len(content_list[idx]))*em + 20, idx, htmlEncode(symplify_path(self.display_list[idx][1])), self.display_list[idx][2][0], self.display_list[idx][2][1]) for idx in range(len(content_list))])
			content += '<br style="padding-bottom:20">'
			self.window.active_view().show_popup(content, sublime.HIDE_ON_MOUSE_MOVE_AWAY, location= point, max_width= max_popup_width, max_height= max_popup_height, on_navigate= self.on_navigate)

		sublime.status_message("")
		print('open_cnt', open_cnt)

	def on_navigate(self, idx):
		idx = int(idx)
		self.window.open_file('%s:%d:%d' % (self.display_list[idx][0], self.display_list[idx][2][0], self.display_list[idx][2][1]), sublime.ENCODED_POSITION)
		pass

def toggle_setting(settings, name):
	if True == settings.get(name):
		print('Disable system', name)
		settings.set(name, False)
	else:
		print('Enable system', name)
		settings.set(name, True)

# toggle "show_definitions"
class ShowDefinitionToggleCommand(sublime_plugin.ApplicationCommand):
	def run(self):
		sublime.active_window().run_command('hide_popup')
		s = sublime.load_settings("Preferences.sublime-settings")
		toggle_setting(s, 'show_definitions')
		sublime.save_settings("Preferences.sublime-settings")

class ShowDefinitionHoverCommand(sublime_plugin.EventListener):
	def on_hover(self, view, point, hover_zone):
		global lastStartTime, lastSymbol
		if sublime.HOVER_TEXT is not hover_zone or not self.is_enabled():
			return

		track = True
		for select in ['constant.language', 'meta.statement']:	# may not track
			if view.match_selector(point, select):
				track = False
				print('match', select, '-')
				break
		if not track:
			for select in ['meta.function-call']:	# may track
				if view.match_selector(point, select):
					track = True
					print('match', select, '+')
					break
		if track:
			for select in ['meta.string', 'comment', 'storage.modifier', 'storage.type', 'keyword']:	# must not track
				if view.match_selector(point, select):
					track = False
					print('match', select, '-')
					break
		if not track:
			print('Finally decided to skip')
			return

		symbol = view.substr(view.word(point))
		timeout = 5
		if symbol is None or symbol == lastSymbol and lastStartTime + timeout > time.time():
			print('symbol not change skip update')
			return
		sublime.status_message("Parse scope name of " + symbol + "...")
		lastSymbol = symbol
		lastStartTime = time.time()
		sublime.set_timeout_async(lambda: view.window().run_command('show_definition', {'symbol': symbol, 'point': point, 'startTime': lastStartTime}), 0)

	def is_enabled(self):
		return not sublime.load_settings("Preferences.sublime-settings").get('show_definitions')
