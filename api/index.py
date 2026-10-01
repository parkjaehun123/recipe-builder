import os
import sys

# 프로젝트 루트 경로를 sys.path에 추가하여 app.py를 안전하게 import
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app import app
