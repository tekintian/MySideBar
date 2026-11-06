import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PKG = os.path.join(ROOT, "src")

sys.dont_write_bytecode = True
sys.path.insert(0, PKG)
os.chdir(PKG)