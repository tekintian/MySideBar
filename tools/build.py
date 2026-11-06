import argparse
import hashlib
import os
import re
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "src")
DIST_DIR = os.path.join(ROOT, "dist")

REQUIRED_AT_ROOT = (
    "MySideBar.py",
    ".no-sublime-package",
    ".python-version",
    "messages.json",
    "messages/install.txt",
)

EXCLUDED_NAMES = (".DS_Store", "Thumbs.db", "desktop.ini")
EXCLUDED_DIRS = ("__pycache__",)

PYTHON_VERSION = "3.8"


def fail(message):
    sys.stderr.write("[build] ERROR: %s\n" % message)
    sys.exit(1)


def read_version():
    path = os.path.join(SRC_DIR, "meta.py")
    with open(path, "r", encoding="utf-8") as fp:
        source = fp.read()
    match = re.search(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", source, re.MULTILINE)
    if not match:
        fail('cannot read __version__ from %s' % path)
    return match.group(1)


def check_python_version_file():
    path = os.path.join(SRC_DIR, ".python-version")
    if not os.path.isfile(path):
        fail("missing %s" % path)
    with open(path, "r", encoding="utf-8") as fp:
        value = fp.read().strip()
    if value != PYTHON_VERSION:
        fail(
            "%s must contain %s (Sublime Text 4 only ships the 3.8 plugin host), found %r"
            % (".python-version", PYTHON_VERSION, value)
        )


def check_layout():
    for name in REQUIRED_AT_ROOT:
        if not os.path.exists(os.path.join(SRC_DIR, name)):
            fail("src/%s is required at the package root" % name)
    if os.path.isfile(os.path.join(ROOT, ".no-sublime-package")):
        fail("remove the stray .no-sublime-package at the repo root; it belongs in src/")
    if os.path.isfile(os.path.join(SRC_DIR, "packages.json")):
        fail("remove src/packages.json; Package Control only reads the repo root copy")
    if not os.path.isfile(os.path.join(ROOT, "packages.json")):
        fail("packages.json must live at the repo root so Package Control can fetch it")


def check_install_message(version):
    path = os.path.join(SRC_DIR, "messages", "install.txt")
    with open(path, "r", encoding="utf-8") as fp:
        first = fp.readline().strip()
    if not first.startswith("MySideBar " + version):
        fail(
            "src/messages/install.txt must start with 'MySideBar %s' so upgrades show the right notice"
            % version
        )


def iter_members():
    for dirpath, dirnames, filenames in os.walk(SRC_DIR):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for filename in sorted(filenames):
            if filename in EXCLUDED_NAMES:
                continue
            absolute = os.path.join(dirpath, filename)
            relative = os.path.relpath(absolute, SRC_DIR)
            yield absolute, relative.replace(os.sep, "/")


def build(version):
    archive_name = "MySideBar-%s.zip" % version
    archive_path = os.path.join(DIST_DIR, archive_name)
    if not os.path.isdir(DIST_DIR):
        os.makedirs(DIST_DIR)

    members = list(iter_members())
    if not members:
        fail("src/ produced no files")

    entries = []
    for absolute, relative in members:
        executable = os.access(absolute, os.X_OK)
        entries.append((absolute, relative, executable))

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for absolute, relative, executable in entries:
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            mode = 0o755 if executable else 0o644
            info.external_attr = (mode & 0xFFFF) << 16
            with open(absolute, "rb") as fp:
                zf.writestr(info, fp.read())

    with open(archive_path, "rb") as fp:
        digest = hashlib.sha256(fp.read()).hexdigest()

    validate(archive_path, version)

    print("[build] archive: %s" % archive_path)
    print("[build] version: %s" % version)
    print("[build] sha256: %s" % digest)
    print("[build] size: %d bytes" % os.path.getsize(archive_path))
    return archive_path, digest, archive_name


def validate(archive_path, version):
    with zipfile.ZipFile(archive_path) as zf:
        names = zf.namelist()
        for name in names:
            if name.startswith("src/") or "/src/" in name:
                fail("archive must not contain a src/ prefix: %s" % name)
        for name in REQUIRED_AT_ROOT:
            if name not in names:
                fail("archive is missing %s at the package root" % name)
        try:
            python_version = zf.read(".python-version").decode("utf-8").strip()
        except KeyError:
            fail("archive is missing .python-version")
        if python_version != PYTHON_VERSION:
            fail("archive .python-version must be %s" % PYTHON_VERSION)
        try:
            install_message = zf.read("messages/install.txt").decode("utf-8")
        except KeyError:
            fail("archive is missing messages/install.txt")
        if not install_message.startswith("MySideBar " + version):
            fail("archive messages/install.txt does not match version %s" % version)

        expected_subfolders = ("mysidebar", "mysidebar/cmds", "messages")
        subfolders = set(
            name.rsplit("/", 1)[0] for name in names if "/" in name
        )
        unknown = subfolders.difference(expected_subfolders)
        if unknown:
            fail(
                "archive must not be wrapped in an extra folder; Package Control "
                "would nest it again. Unexpected folders: %s" % ", ".join(sorted(unknown))
            )


def main():
    parser = argparse.ArgumentParser(description="Build the MySideBar release archive")
    parser.add_argument("--version", default=None, help="override the version read from src/meta.py")
    parser.add_argument("--clean", action="store_true", help="remove dist/ before building")
    args = parser.parse_args()

    version = args.version or read_version()
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        fail("version must be semantic (major.minor.patch), got %r" % version)

    if args.clean and os.path.isdir(DIST_DIR):
        shutil.rmtree(DIST_DIR)

    check_layout()
    check_python_version_file()
    check_install_message(version)
    build(version)


if __name__ == "__main__":
    main()