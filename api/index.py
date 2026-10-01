import os
import sys

# 프로젝트 루트 경로를 작업 디렉토리 및 sys.path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    os.chdir(root_dir)
except Exception:
    pass

from app import app
