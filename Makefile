# =====================================================
# 教培 CRM Makefile (macOS / Linux)
# Windows 用户请用 start_crm.bat
# =====================================================
.PHONY: help install run init init-empty reset seed backup clean stop

PY      := python3
PORT    ?= 5050
HOST    ?= 127.0.0.1

help:           ## 显示本帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:       ## 安装依赖到 venv
	@test -d venv || $(PY) -m venv venv
	. venv/bin/activate && pip install -q -r requirements.txt

run:           ## 启动服务 (run.py 会自动 init)
	PORT=$(PORT) HOST=$(HOST) $(PY) run.py

init:          ## 初始化数据库 + 写示例数据
	$(PY) init_db.py

init-empty:    ## 初始化数据库(不写示例数据)
	$(PY) init_db.py --no-seed

reset:         ## ⚠ 删库重建(会丢所有数据!)
	$(PY) init_db.py --reset

seed:          ## 在空库里写入示例数据(若已有数据会自动跳过)
	$(PY) init_db.py

backup:        ## 手动触发数据库备份
	$(PY) backup_now.py

stop:          ## 停止 5050 端口的 Flask 服务
	@lsof -nP -iTCP:$(PORT) -sTCP:LISTEN -t | xargs -r kill -TERM 2>/dev/null || true
	@echo "已停止"

clean:         ## 清理 Python 缓存
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	@echo "已清理"
