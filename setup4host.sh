#!/bin/bash
# setup4host.sh - set up virtual environment, install dependencies and create systemd file
# 确保脚本运行幂等，有更新时保证运行一次脚本就可以满足更新的需要

set -e

program_name="source2RSS"   # 不能有空格等特殊符号
current_uid=$(id -u)

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_environment="${root_dir}/.venv"
python_bin="${python_environment}/bin/python3"

# 确保存在虚拟环境并安装包
uv sync --all-groups --all-packages
source "${python_environment}/bin/activate"
# 安装指定的浏览器
python -m playwright install chromium
# 安装 playwright 的依赖
python -m playwright install --with-deps

# 创建 systemd 配置文件
if [ "$1" != "agent" ]; then
# 如果第一个参数不是 "agent" 或者为空

cd services/web
# 配置文件。若不存在目录 config_and_data_files 就自动复制示例配置文件，否则不操作
if [ ! -d config_and_data_files ]
then
    mkdir config_and_data_files && \
    cp examples/config.example.yaml config_and_data_files/config.yaml && \
    cp examples/scraper_profile.example.yaml config_and_data_files/scraper_profile.yaml && \
    sed -i 's|examples/scraper_profile\.example\.yaml|config_and_data_files/scraper_profile.yaml|g' config_and_data_files/config.yaml
fi
cd -

if [ ! -f ${program_name}.service ]
then

cd services/web
cat > ./${program_name}.service <<EOF
[Unit]
Description=source2RSS Web Service
After=network.target

[Service]
WorkingDirectory=${root}/services/web
User=${current_uid}
Group=${current_uid}
Type=simple
ExecStart=${python_environment}/bin/uvicorn main:app --host 127.0.0.1 --port 8536
ExecStop=/bin/kill -s HUP \$MAINPID
Environment=PYTHONUNBUFFERED=1
RestartSec=15
Restart=on-failure

[Install]
WantedBy=default.target
EOF

chmod 644 ${program_name}.service
cd -
fi


else
# 如果第一个参数是 "agent"

cd services/agent
if [ ! -d config_and_data_files ]
then
    mkdir config_and_data_files && \
    cp examples/config.yaml config_and_data_files/config.yaml
fi
cd -

d_agent_pgm_name="source2RSS_d_agent"

if [ ! -f ${d_agent_pgm_name}.service ]
then

cd services/agent
cat > ./${d_agent_pgm_name}.service <<EOF
[Unit]
Description=source2RSS direct agent Service
After=network.target

[Service]
WorkingDirectory=${root}/services/agent
User=${current_uid}
Group=${current_uid}
Type=simple
ExecStart=${python_environment}/bin/uvicorn as_d_agent:app --host 0.0.0.0 --port 8537
ExecStop=/bin/kill -s HUP \$MAINPID
Environment=PYTHONUNBUFFERED=1
RestartSec=15
Restart=on-failure

[Install]
WantedBy=default.target
EOF

chmod 644 ${d_agent_pgm_name}.service
cd -
fi

fi

# vim: expandtab shiftwidth=4 softtabstop=4
