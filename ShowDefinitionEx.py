import sublime
import sublime_plugin
import re
import time
import html

lastSymbol = None
lastStartTime = time.time()
settings = {}

def load_all_settings():
	global hover_view, global_settings, settings, DEBUG, SHOW_PATH, MAX_LEN_TO_WRAP, MAX_LIST_ITEM

	global_settings = hover_view.settings()

	settings = sublime.load_settings('show_definition_ex.sublime-settings')
	DEBUG = settings.get('DEBUG', False)
	SHOW_PATH = settings.get('show_path', True)
	MAX_LEN_TO_WRAP = settings.get('max_len_to_wrap', 60)
	MAX_LIST_ITEM = settings.get('max_list_item', 20)

def symplify_path(path):
	s = path.split('/');
	count = 2
	if count*2 < len(s):
		return '/'.join(s[0:count] + ['..'] + s[-count:])
	return path

def get_file_ex(path):
	path_l = path.lower()
	if 'makefile' in path_l:
		return 'makefile'
	return path_l[path_l.rfind('.')+1:]

def file_related(ex1, ex2):
	global settings
	if ex1 == ex2:
		return True
	for r_list in settings.get('related_list',[]):
		rt1 = True if ex1 in r_list else False
		rt2 = True if ex2 in r_list else False
		if rt1 and rt2:
			return True
	return False

hide_view = None
hide_view_filename = None

def show_hide_view():
	global hide_view
	if hide_view is not None:
		sublime.active_window().run_command('show_panel', {'panel': 'output._show_definition_ex'})
		sublime.active_window().focus_view(hide_view)

def get_lint_file(filename, own_file = None):
	global DEBUG, hide_view, hide_view_filename, hide_view_ex, settings, global_settings
	if hide_view_filename == filename:
		return hide_view, hide_view_ex

	ex = get_file_ex(filename)
	if ex in settings.get('exclude_files',[]):	# Not index file extension
		if DEBUG:
			print('    skip exclude_files file')
		return None, None

	hide_view_ex = ex
	if own_file:
		own_ex = get_file_ex(own_file)
		if not file_related(hide_view_ex, own_ex):
			if DEBUG:
				print('    skip none related file', (hide_view_ex, own_ex))
			return None, None

	if hide_view is None:
		hide_view = sublime.active_window().create_output_panel("_show_definition_ex", True)
	if DEBUG:
		show_hide_view()
	content = None

	try:
		with open(filename, 'r', encoding = 'utf8') as file:
			content = file.read()
	except Exception as e:
		print(e, 'Cant open file:', filename)
		return None, None

	hide_view_filename = filename

	hide_view.run_command("select_all")
	hide_view.run_command("left_delete")
	hide_view.run_command("append", {"characters": content})

	syntax_lists = settings.get('syntax_lists')
	syntax = None
	if syntax_lists:
		for syntax_list in syntax_lists:
			if hide_view_ex in syntax_list[1]: 	# ['h', 'hpp', 'c', 'cpp'],
				syntax = syntax_list[0] 		# "C++.sublime-syntax"
	if syntax is None:
		syntax = global_settings.get('syntax', {'extension': hide_view_ex})
	if DEBUG:
		print('    filename:', filename, ', hide_view_ex:', hide_view_ex, ', syntax:', syntax)
	hide_view.assign_syntax(syntax)
	return hide_view, hide_view_ex

def get_indent(view, point):
	indent_len = 1
	line_start = view.find_by_class(point, False, sublime.CLASS_LINE_START)
	line_end = view.find_by_class(point, True, sublime.CLASS_LINE_END)
	loc_indent = view.find('^\t+', line_start)
	if -1 == loc_indent.a or -1 == loc_indent.b:
		loc_indent = view.find('^(    )+', line_start)
		indent_len = 4
	if loc_indent.a > line_end:
		return 0
	return (loc_indent.b - loc_indent.a) / indent_len

def ensure_func_in_class_by_indent(view, class_point, function_point):
	class_indent = get_indent(view, class_point)
	function_indent = get_indent(view, function_point)
	if class_indent != function_indent - 1:
		return False
	next_class_indent = view.find('^(    ){0' + ',' + str(class_indent) + '}[^\t \r\n]+', class_point)
	if -1 == next_class_indent.a or -1 == next_class_indent.b:
		next_class_indent = view.find('^\t{0' + ',' + str(class_indent) + '}[^\t \r\n]+', class_point)
	if -1 == next_class_indent.a or -1 == next_class_indent.b:
		return True
	return next_class_indent.b > function_point

def ensure_func_in_class_by_parans(view, class_point, function_point):
	first_semicolon = view.find(';', class_point).a
	first_parentheses = view.find('{', class_point).a
	if first_semicolon < first_parentheses:
		return False

	parentheses_l = 1
	loc = first_parentheses + 1
	while True:
		loc = view.find('{', loc)
		if -1 == loc.a or -1 == loc.b:
			break
		if loc.b > function_point:
			break
		loc = loc.b
		parentheses_l += 1

	parentheses_r = 0
	loc = first_parentheses + 1
	while True:
		loc = view.find('}', loc)
		if -1 == loc.a or -1 == loc.b:
			break
		if loc.b > function_point:
			break
		loc = loc.b
		parentheses_r += 1

	return parentheses_r < parentheses_l

def ensure_func_in_class(view, class_point, function_point):
	if 'python' in view.settings().get('syntax').lower():
		return ensure_func_in_class_by_indent(view, class_point, function_point)

	return ensure_func_in_class_by_parans(view, class_point, function_point)

def parse_scope_full_name(view, region_row = None, region_col = None):
	global DEBUG, hide_view_ex
	if region_row is None or region_col is None:
		pt = view.sel()[0].begin()
		region_row, region_col = view.rowcol(pt)
	else:
		pt = view.text_point(region_row, region_col)

	# skip calling
	prec = view.substr(pt-1)
	if 'js' == hide_view_ex:
		prec_list = {'>', '!', '\(', '\{'}
	else:
		prec_list = {'.', '>', '!', '\(', '\{'}
	if prec in prec_list:
		if DEBUG:
			print('    skip prefix char:', prec)
			return

	is_class = view.match_selector(pt, 'entity.name.class | entity.name.struct')
	if DEBUG:
		view.sel().clear()
		view.sel().add(sublime.Region(pt, pt))
		view.show(pt)

	s = ''
	found = False

	# Look for any classes
	class_point = None
	class_regions = view.find_by_selector('entity.name.class | entity.name.struct')
	class_name = ''
	for r in reversed(class_regions):
		row, col = view.rowcol(r.a)
		if row <= region_row:
			class_point = r.a
			r.b = view.find("[ \n\r\{\[\(;,'\"]", r.a).a
			class_name = view.substr(r).strip(':')
			found = True
			break;

	function_point = None
	function_name = ''
	param_name = ''
	if not is_class:
		# Look for any functions
		function_regions = view.find_by_selector('entity.name.function')
		if function_regions:
			for r in reversed(function_regions):
				if r.contains(pt):
					function_point = r.begin()
					s = view.substr(view.split_by_newlines(r)[-1])
					if '::' in s:
						sp = s.rsplit('::')
						class_point = None
						class_name = sp[0].strip()
						function_name = '::'.join(sp[1:]).strip()
					else:
						function_name = s
					found = True
					break
		# for parens wrap
		if function_point:
			function_params = view.find_by_selector('meta.function.parameters | meta.method.parameters | punctuation.section.group')
			if function_params:
				for r in function_params:
					if function_point < r.begin():
						param_name = view.substr(r)
						break;

	if DEBUG:
		print('    class_point:', class_point, ', class_name:', class_name, ', function_point:', function_point, ', function_name:', function_name, ', param_name', param_name, ', s:', s)
	if class_point is not None and function_point is not None:
		if not ensure_func_in_class(view, class_point, function_point):
			if DEBUG:
				print('   ',function_name, 'not in', class_name)
			class_name = ''

	if '' != class_name and '' != function_name:
		s = class_name + '::' + function_name
	else:
		s = class_name + function_name

	if '' != param_name:
		param_name = param_name if 0 < len(param_name) and param_name[0] != '(' else param_name[1:]
		param_name = param_name if 0 < len(param_name) and param_name[-1] != ')' else param_name[:-1]
		s = s + '(' + param_name + ')'

	if found:
		s = ('O ' if class_point == pt or function_point == pt else 'X ') + s
	else:
		# Not found, just capture the line and do something
		length = view.line(pt).end() - pt + 1
		s = view.substr(view.line(pt)).strip(' ;\t{}(')
		s_next = s
		while len(s_next) > length and '' != s_next:
			s, _, s_next = s_next.partition(' ')
		if s == s_next:
			s_next = ''
		s = '? ' + s + ' ' + s_next

	s = s.strip();
	s = re.sub(r'[\n\r\t]+', '', s)
	s = re.sub(r'[ ]+', ' ', s)
	s = re.sub(r',(\w)', ', \\1', s)
	s = s.replace('( ', '(')
	s = s.replace(' )', ')')
	if DEBUG:
		print('    result:', s)
	return s

class ShowDefinitionExTestCommand(sublime_plugin.WindowCommand):
	def run(self):
		global hover_view
		hover_view = self.window.active_view()
		load_all_settings()

		base_dir = sublime.packages_path() + '\\ShowDefinitionEx\\'
		file = open(base_dir + "tests\\list.txt", "r")
		has_fail = False
		line_num = 0
		if file:
			line = file.readline().strip()
			line_num += 1
			while line:
				if line.startswith('#'):
					line = file.readline().strip()
					line_num += 1
					continue
				ans = file.readline().strip()
				line_num += 1
				loc = line.split(':')
				view, _ = get_lint_file(base_dir + loc[0])
				scope_name = parse_scope_full_name(view, int(loc[1])-1, int(loc[2])-1)
				scope_name = scope_name.partition(' ')[2]
				if scope_name != ans:
					print('Error!!!!')
					print('#', line_num - 1, ' : ', line)
					print(' ans  : ', ans)
					print('parse : ', scope_name)
					has_fail = True
					view.sel().clear()
					view.sel().add(view.text_point(int(loc[1])-1, int(loc[2])-1))
					view.show(view.sel())
					show_hide_view()
					break;
				line = file.readline().strip()
				line_num += 1
			if False == has_fail:
				sublime.message_dialog('All test pass!')
			else:
				sublime.message_dialog('Test failed at line ' + str(line_num - 1) + '!')
			file.close()

class ShowDefinitionExSelCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		view = self.view
		max_popup_width, max_popup_height = view.viewport_extent()
		scope_name = parse_scope_full_name(view)
		view.show_popup(html.escape(scope_name, False), sublime.HIDE_ON_MOUSE_MOVE_AWAY, max_width= max_popup_width, max_height= max_popup_height)

class ShowDefinitionExCommand(sublime_plugin.WindowCommand):
	def run(self, startTime, symbol, point):
		global lastStartTime, hover_view
		# skip update
		if startTime != lastStartTime:
			return
		self.startTime = startTime
		self.symbol = symbol
		self.point = point
		self.symbol_list = hover_view.window().lookup_symbol_in_index(self.symbol)
		if 0 == len(self.symbol_list):
			print('no symbol_list of', self.symbol)
			sublime.status_message("")
			return

		load_all_settings()

		self.em = hover_view.em_width()
		self.own_file = hover_view.file_name()
		self.own_row, _ = hover_view.rowcol(point)
		self.max_popup_width, self.max_popup_height = hover_view.viewport_extent()
		self.start = 0
		self.had_wrap = False
		self.first_show = True
		self.show()

	def show(self):
		global hover_view, lastStartTime, DEBUG, SHOW_PATH, MAX_LEN_TO_WRAP, MAX_LIST_ITEM
		max_len = 0
		has_more = False
		content_list = []
		self.display_list = []
		idx_range = range(self.start, len(self.symbol_list))
		for idx in idx_range:
			# skip update
			if self.startTime != lastStartTime:
				return
			loc = self.symbol_list[idx]
			if  self.own_file == loc[0] and self.own_row == loc[2][0]-1:
				if DEBUG:
					print('skip own_file')
				continue
			if DEBUG:
				print('parse #%d:' % (idx))
			view, ex = get_lint_file(loc[0], self.own_file)
			scope_name = None
			if view:
				scope_name = parse_scope_full_name(view, loc[2][0]-1, loc[2][1]-1)
			if scope_name:
				max_len = max(max_len, len(scope_name))
				self.display_list.append({'name': scope_name[1:], 'ex': ex, 'loc': loc})
				if MAX_LIST_ITEM <= len(self.display_list):
					has_more = idx != len(self.symbol_list) - 1
					self.start = idx + 1
					break

		self.display_list.sort(key = lambda x: x['name'])

		if 0 != len(self.display_list):
			if self.startTime != lastStartTime:
				print('skip update')
			if SHOW_PATH:
				if max_len >= MAX_LEN_TO_WRAP or self.had_wrap:
					self.had_wrap = True
					str_tpl = '<a href=%d><code><i>%s</i>%s</code><br /><small style="padding-left:%dpx">%s:%d</small></a>'
					content = '<br />'.join([str_tpl % (idx, self.display_list[idx]['ex'][0].upper(), html.escape(self.display_list[idx]['name'], False).replace(self.symbol, '<m>' + self.symbol + '</m>', 1), 2 * self.em, html.escape(symplify_path(self.display_list[idx]['loc'][1]), False), self.display_list[idx]['loc'][2][0]) for idx in range(len(self.display_list))])
				else:
					str_tpl = '<a href=%d><code><i>%s</i>%s</code><small style="padding-left:%dpx">%s:%d</small></a>'
					content = '<br />'.join([str_tpl % (idx, self.display_list[idx]['ex'][0].upper(), html.escape(self.display_list[idx]['name'], False).replace(self.symbol, '<m>' + self.symbol + '</m>', 1), (max_len-len(self.display_list[idx]['name']))*self.em + 5, html.escape(symplify_path(self.display_list[idx]['loc'][1]), False), self.display_list[idx]['loc'][2][0]) for idx in range(len(self.display_list))])
			else:
				str_tpl = '<a href=%d><code><i>%s</i>%s</code></a>'
				content = '<br />'.join([str_tpl % (idx, self.display_list[idx]['ex'][0].upper(), html.escape(self.display_list[idx]['name'], False).replace(self.symbol, '<m>' + self.symbol + '</m>', 1)) for idx in range(len(self.display_list))])

			if has_more:
				content += '<br /><br /><a href=more><n>click to see more ...</n></a>'

			body = """
				<body id=show-definitions>
					<style>
						body {
							font-family: system;
						}
						h1 {
							font-size: 1.1rem;
							font-weight: bold;
							margin: 0 0 0.25em 0;
						}
						m {
							color: #FFFB9D;
							text-decoration: none;
						}
						code {
							font-family: monospace;
							color: #FFFFFF;
							text-decoration: none;
						}
						i {
							color: #73AE86;
							font-weight: bold;
							font-style: normal;
							text-decoration: none;
							width: 30px;
						}
						n {
							font-weight: bold;
							padding: 0px 0px 0px %dpx;
						}
					</style>
				<h1>Definition of <m>%s</m> %s:</h1>
				<p>%s</p>
				</body>
			""" % (self.em*2, self.symbol, '' if not has_more else '%d/%d' % (self.start, len(self.symbol_list)), content)
			if self.first_show:
				hover_view.show_popup(body, sublime.HIDE_ON_MOUSE_MOVE_AWAY, location= self.point, max_width= self.max_popup_width, max_height= self.max_popup_height, on_navigate= self.on_navigate)
			else:
				hover_view.update_popup(body)

		sublime.status_message("")

	def on_navigate(self, idx):
		global MAX_LIST_ITEM
		if 'more' == idx:
			self.first_show = False
			self.show()
		else:
			idx = int(idx)
			self.window.open_file('%s:%d:%d' % (self.display_list[idx]['loc'][0], self.display_list[idx]['loc'][2][0], self.display_list[idx]['loc'][2][1]), sublime.ENCODED_POSITION)

def toggle_setting(settings, name):
	if True == settings.get(name):
		print('Disable system', name)
		settings.set(name, False)
	else:
		print('Enable system', name)
		settings.set(name, True)

# toggle "show_definitions"
class ShowDefinitionExToggleCommand(sublime_plugin.ApplicationCommand):
	def run(self):
		sublime.active_window().run_command('hide_popup')
		s = sublime.load_settings("Preferences.sublime-settings")
		toggle_setting(s, 'show_definitions')
		sublime.save_settings("Preferences.sublime-settings")

def lookup_symbol(window, symbol):
	if len(symbol.strip()) < 3:
		return []

	index_locations = window.lookup_symbol_in_index(symbol)
	open_file_locations = window.lookup_symbol_in_open_files(symbol)

	def file_in_location_list(fname, locations):
		for l in locations:
			if l[0] == fname:
				return True
		return False

	# Combine the two lists, overriding results in the index with results
	# from open files, while trying to preserve the order of the files in
	# the index.
	locations = []
	ofl_ignore = []
	for l in index_locations:
		if file_in_location_list(l[0], open_file_locations):
			if not file_in_location_list(l[0], ofl_ignore):
				for ofl in open_file_locations:
					if l[0] == ofl[0]:
						locations.append(ofl)
						ofl_ignore.append(ofl)
		else:
			locations.append(l)

	for ofl in open_file_locations:
		if not file_in_location_list(ofl[0], ofl_ignore):
			locations.append(ofl)

	return locations

def symbol_at_point(view, pt):
	symbol = view.substr(view.expand_by_class(pt, sublime.CLASS_WORD_START | sublime.CLASS_WORD_END, "[]{}()<>:."))
	locations = lookup_symbol(view.window(), symbol)

	if len(locations) == 0:
		symbol = view.substr(view.word(pt))
		locations = lookup_symbol(view.window(), symbol)

	return symbol, locations

def filter_current_symbol(view, point, symbol, locations):
	"""
	Filter the point specified from the list of symbol locations. This
	results in a nicer user experience so the current symbol doesn't pop up
	when hovering over a class definition. We don't just skip all class and
	function definitions for the sake of languages that split the definition
	and implementation.
	"""

	def match_view(path, view):
		fname = view.file_name()
		if fname is None:
			if path.startswith('<untitled '):
				path_view = view.window().find_open_file(path)
				return path_view and path_view.id() == view.id()
			return False
		return path == fname

	new_locations = []
	for l in locations:
		if match_view(l[0], view):
			symbol_begin_pt = view.text_point(l[2][0] - 1, l[2][1])
			symbol_end_pt = symbol_begin_pt + len(symbol)
			if point >= symbol_begin_pt and point <= symbol_end_pt:
				continue
		new_locations.append(l)
	return new_locations

class ShowDefinitionExHoverCommand(sublime_plugin.EventListener):
	def on_hover(self, view, point, hover_zone):
		global hover_view, lastStartTime, lastSymbol, DEBUG
		if sublime.HOVER_TEXT is not hover_zone or not self.is_enabled():
			return

		# decide to show or not to show by built-in logic
		def score(scopes):
			return view.score_selector(point, scopes)

		# Limit where we show the hover popup
		if score('text.html') and not score('text.html source'):
			is_class = score('meta.attribute-with-value.class')
			is_id = score('meta.attribute-with-value.id')
			if not is_class and not is_id:
				return
		else:
			if not score('source'):
				return
			if score('comment'):
				return
			# Only show definitions in a string if there is interpolated source
			if score('string') and not score('string source'):
				return

		# decide to show or not to show by this package
		symbol, locations = symbol_at_point(view, point)
		locations = filter_current_symbol(view, point, symbol, locations)
		if not locations:
			if DEBUG:
				print('skip by symbol check')
			return

		track = True
		for select in ['constant.language', 'meta.statement']:	# may not track
			if view.match_selector(point, select):
				track = False
				break
		if not track:
			for select in ['meta.function-call']:	# may track
				if view.match_selector(point, select):
					track = True
					break
		if track:
			for select in ['meta.string', 'comment', 'storage.modifier', 'storage.type', 'keyword']:	# must not track
				if view.match_selector(point, select):
					track = False
					break
		if not track:
			if DEBUG:
				print('Finally decided to skip, select:', select)
			return

		timeout = 5
		if symbol is None or symbol == lastSymbol and lastStartTime + timeout > time.time():
			if DEBUG:
				print('symbol not change skip update')
			return
		sublime.status_message("Parse definitions of " + symbol + "... 0/" + str(len(view.window().lookup_symbol_in_index(symbol))))
		lastSymbol = symbol
		lastStartTime = time.time()
		hover_view = view
		sublime.set_timeout_async(lambda: view.window().run_command('show_definition_ex', {'symbol': symbol, 'point': point, 'startTime': lastStartTime}), 0)

	def is_enabled(self):
		return not sublime.load_settings("Preferences.sublime-settings").get('show_definitions')
