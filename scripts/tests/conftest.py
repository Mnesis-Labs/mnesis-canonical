"""让 scripts/tests/ 能直接 `import dev_local` —— 与 Iris#208 参考 conftest 一致。"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
