import os

import sublime

from . import encodings
from . import platform as plat


class SideBarItem(object):
    def __init__(self, path):
        self.path = plat.normalize(path)

    @property
    def name(self):
        return os.path.basename(self.path)

    @property
    def is_dir(self):
        return os.path.isdir(self.path)

    @property
    def is_file(self):
        return os.path.isfile(self.path)

    @property
    def is_symlink(self):
        return os.path.islink(self.path)

    @property
    def exists(self):
        return os.path.exists(self.path)

    @property
    def dirname(self):
        return os.path.dirname(self.path)

    @property
    def stem(self):
        return os.path.splitext(self.name)[0]

    @property
    def ext(self):
        return os.path.splitext(self.name)[1]

    def join(self, name):
        return SideBarItem(os.path.join(self.path, name))

    def resolve(self):
        return os.path.realpath(self.path)

    def __repr__(self):
        return "SideBarItem(%r)" % self.path

    def __eq__(self, other):
        if not isinstance(other, SideBarItem):
            return NotImplemented
        return plat.same_path(self.path, other.path)

    def __hash__(self):
        return hash(os.path.normcase(self.path))


class SideBarSelection(object):
    def __init__(self, paths):
        self.paths = [plat.normalize(p) for p in (paths or []) if p]
        self._items = None

    @property
    def items(self):
        if self._items is None:
            self._items = [SideBarItem(p) for p in self.paths]
        return self._items

    @property
    def files(self):
        return [i for i in self.items if i.is_file or (i.exists and not i.is_dir)]

    @property
    def dirs(self):
        return [i for i in self.items if i.is_dir and not i.is_symlink]

    @property
    def is_empty(self):
        return not self.paths

    @property
    def has_single_dir(self):
        return len(self.items) == 1 and self.items[0].is_dir

    def without_child_items(self):
        result = []
        for item in self.items:
            if any(plat.is_within(item.path, other.path) for other in self.items):
                continue
            result.append(item)
        return result

    def common_base(self):
        if not self.paths:
            return None
        if len(self.paths) == 1:
            single = self.paths[0]
            return single if os.path.isdir(single) else os.path.dirname(single)
        try:
            common = os.path.commonpath(self.paths)
        except ValueError:
            return None
        if not os.path.isdir(common):
            common = os.path.dirname(common)
        return plat.normalize(common)

    def __len__(self):
        return len(self.paths)


class SideBarProject(object):
    def __init__(self, window):
        self.window = window

    def folders(self):
        if self.window is None:
            return []
        return [plat.normalize(f) for f in self.window.folders()]

    def project_data(self):
        if self.window is None:
            return None
        return self.window.project_data()

    def find_root(self, path):
        target = plat.normalize(path)
        best = None
        for folder in self.folders():
            if plat.is_within(target, folder):
                if best is None or len(folder) > len(best):
                    best = folder
        return best

    def relative_path(self, path):
        root = self.find_root(path)
        if root is None:
            return None
        return plat.rel_path(path, root)


class ViewResolver(object):
    @staticmethod
    def resolve_tab_view(window, group=-1, index=-1):
        if window is None:
            return None
        g = group if group >= 0 else window.active_group()
        if g < 0 or g >= window.num_groups():
            return None
        sheets = window.sheets_in_group(g)
        if index >= 0:
            if index >= len(sheets):
                return None
            sheet = sheets[index]
        else:
            sheet = window.active_sheet()
            if sheet is None:
                return None
        return ViewResolver.sheet_to_view(sheet)

    @staticmethod
    def sheet_to_view(sheet):
        if sheet is None:
            return None
        view = sheet if isinstance(sheet, sublime.View) else None
        if view is None and hasattr(sheet, "view"):
            view = sheet.view()
        if view is None:
            return None
        if not view.is_valid():
            return None
        if not view.file_name():
            return None
        return view

    @staticmethod
    def count_views_for_file(path, exclude_view=None):
        target = plat.normalize(path)
        count = 0
        for window in sublime.windows():
            for view in window.views():
                fname = view.file_name()
                if not fname:
                    continue
                if exclude_view is not None and view.id() == exclude_view.id():
                    continue
                if plat.same_path(fname, target):
                    count += 1
        return count

    @staticmethod
    def retarget_views(mappings):
        for window in sublime.windows():
            for view in window.views():
                fname = view.file_name()
                if not fname:
                    continue
                normalized = os.path.normcase(plat.normalize(fname))
                new_path = mappings.get(normalized)
                if new_path is None:
                    continue
                if plat.same_path(fname, new_path):
                    continue
                if not os.path.exists(new_path):
                    continue
                view.retarget(new_path)

    @staticmethod
    def retarget_pairs(pairs):
        mapping = {}
        for source, target in pairs or []:
            mapping[os.path.normcase(plat.normalize(source))] = target
        if not mapping:
            return
        ViewResolver.retarget_views(mapping)

    @staticmethod
    def close_views_for_paths(paths):
        targets = [os.path.normcase(plat.normalize(p)) for p in (paths or []) if p]
        if not targets:
            return
        doomed = []
        for window in sublime.windows():
            for view in window.views():
                fname = view.file_name()
                if not fname:
                    continue
                if os.path.normcase(plat.normalize(fname)) not in targets:
                    continue
                if view.is_dirty():
                    continue
                doomed.append((window, view))
        for window, view in doomed:
            if not view.is_valid():
                continue
            window.focus_view(view)
            window.run_command("close_file")

    @staticmethod
    def set_encoding_checked(view, name):
        if view is None or name is None:
            return False
        if not encodings.is_valid(name):
            return False
        try:
            view.set_encoding(name)
        except Exception:
            return False
        return view.encoding() == name