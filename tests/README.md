# 单元测试

`skills/` 下脚本的单元测试。**一个脚本一个子目录**，避免多个脚本的测试混在一起。

## 目录约定

```text
tests/
├── conftest.py              # 跨脚本共享夹具：make_project / git_repo / run_script
├── frontend_index/          # → skills/frontend-index/scripts/scan_frontend.py
│   ├── __init__.py          # 必须有：让不同子目录可以存在同名测试文件（如各自的 test_cli.py）
│   ├── conftest.py          # 该脚本专属夹具：sf（加载被测模块）/ scan_of / run_cli
│   ├── _helpers.py          # 断言助手（纯函数）
│   └── test_*.py            # 按关注点拆分：routes / apis / mapping / cli …
└── {skill_name}/            # 下一个脚本照此新建（目录名 = skill 名，连字符改下划线）
```

## 跑法

```bash
cd <repo root>
python3 -m pytest tests -q                      # 全部
python3 -m pytest tests/frontend_index -q       # 只跑某个脚本
python3 -m pytest tests/frontend_index -q -k routes   # 只跑某组用例
```

依赖仅为 `pytest`（本机已有；仓库脚本本身零依赖）。需要 git 的用例在本机无 git 时自动 skip。

## 加新脚本的测试

1. 新建 `tests/{skill_name}/`，加 `__init__.py`（内容照抄现有那份的注释即可）
2. 加 `conftest.py`，定义「加载被测模块」与「CLI 运行器」两个夹具（CLI 运行器包一层共享的 `run_script`）
3. 按关注点拆 `test_*.py`；断言助手放 `_helpers.py`，用 `from ._helpers import ...` 引入
4. 用例只断言**对外契约**（函数返回值结构 / CLI 退出码与产物），不依赖内部函数名与实现细节

## 与文档的联动

`reference.md` 的「已实测项目」记录了端到端回归命令：**改脚本前后**各跑一次
`python3 -m pytest tests -q`，再用那两条真实项目命令核对数字（单测保证契约，回归保证真实项目不退化）。
