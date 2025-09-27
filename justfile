root := justfile_directory()

machine_ip := `ip -4 addr show scope global | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n1`


@run:
  echo "网页地址： http://{{machine_ip}}:8536/"
  echo "管理员访问： http://vfly2:123456@{{machine_ip}}:8536/"
  cd "{{root}}" && .env/bin/python main.py

@run_agent:
  cd "{{root}}" && .env/bin/python -m src.node.as_agent


@test: (start_agent "d") && (stop_agent "d")
  SOURCE2RSS_CONFIG_FILE=tests/test_config.yaml .env/bin/python -m pytest tests/ -m "not slow" || true

@test_all: (start_agent "d") && (stop_agent "d")
  echo "全量测试"
  SOURCE2RSS_CONFIG_FILE=tests/test_config.yaml .env/bin/python -m pytest tests/ || true

# 启动 agent 并后台运行，设置 PID 变量
start_agent type:
  #!/usr/bin/env bash
  set -eu pipefail
  echo "Starting {{type}}_agent in background..."
  SOURCE2RSS_AGENT_CONFIG_FILE=examples/agent_config.example.yaml .env/bin/python -m src.node.as_{{type}}_agent > {{type}}_agent.log 2>&1 &
  echo $! > .{{type}}_agent.pid
  sleep 2  # 等待启动

# 停止 agent
stop_agent type:
  #!/usr/bin/env bash
  set -eu pipefail
  if [[ -f .{{type}}_agent.pid ]]; then
    pid=$(cat .{{type}}_agent.pid)
    echo "Stopping {{type}}_agent with PID $pid"
    kill $pid 2>/dev/null || true
    rm -f .{{type}}_agent.pid
    wait $pid 2>/dev/null || true
  fi
  echo -e "\n"


# 将所有文件 amend
amend argument="":
  cd "{{root}}" && git add .
  git commit --amend {{argument}}

# 将所有文件 commit
commit msg argument="":
  cd "{{root}}" && git add .
  git commit -m "{{msg}}" {{argument}}


# === just 管理命令 ===

bashrc := "$HOME/.bashrc"
# 设置 just 的命令补全
@setup-completions:
  # 检查是否已经存在补全命令
  cmd="eval \"\$(just --justfile {{justfile()}} --completions bash)\""; \
  if ! grep -Fxq "$cmd" "{{bashrc}}"; then \
      echo '添加 just 补全到 {{bashrc}}'; \
      echo $cmd >> "{{bashrc}}"; \
  else \
      echo "补全命令已存在 {{bashrc}}，无需重复添加"; \
      echo "执行命令 source {{bashrc}} ，使之生效"; \
  fi
