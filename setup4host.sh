#!/bin/bash
# setup4host.sh - set up virtual environment, install dependencies and create systemd file
# 确保脚本运行幂等，有更新时保证运行一次脚本就可以满足更新的需要

program_name="source2RSS"   # 不能有空格等特殊符号
current_uid=$(id -u)
current_dir=$(pwd)

mkdir -p plugins

# 确保存在虚拟环境并安装包
if [ ! -d .env ]
then
    python3 -m venv .env
fi
source .env/bin/activate
pip install -r requirements.txt
# 安装指定的浏览器
playwright install chromium
# 如果显示缺乏依赖
# python -m playwright install --with-deps

# 配置文件。若不存在目录 config_and_data_files 就自动复制示例配置文件，否则不操作
if [ ! -d config_and_data_files ]
then
    mkdir config_and_data_files && \
    cp examples/config.example.yaml config_and_data_files/config.yaml && \
    cp examples/scraper_profile.example.yaml config_and_data_files/scraper_profile.yaml && \
    sed -i 's|examples/scraper_profile\.example\.yaml|config_and_data_files/scraper_profile.yaml|g' config_and_data_files/config.yaml
fi

# 创建 systemd 配置文件
if [ "$1" != "agent" ]; then
# 如果第一个参数不是 "agent" 或者为空

if [ ! -f ${program_name}.service ]
then
cat > ./${program_name}.service <<EOF
[Unit]
Description=vfly2 client Service
After=network.target

[Service]
WorkingDirectory=${current_dir}
User=${current_uid}
Group=${current_uid}
Type=simple
ExecStart=${current_dir}/.env/bin/uvicorn main:app --host 0.0.0.0 --port 8536
ExecStop=/bin/kill -s HUP $MAINPID
Environment=PYTHONUNBUFFERED=1
RestartSec=15
Restart=on-failure

[Install]
WantedBy=default.target
EOF
fi

chmod 644 ${program_name}.service

else
# 如果第一个参数是 "agent"
cp examples/agent_config.example.yaml config_and_data_files/agent_config.yaml

d_agent_pgm_name="source2RSS_d_agent"

if [ ! -f ${d_agent_pgm_name}.service ]
then
cat > ./${d_agent_pgm_name}.service <<EOF
[Unit]
Description=source2RSS direct agent Service
After=network.target

[Service]
WorkingDirectory=${current_dir}
User=${current_uid}
Group=${current_uid}
Type=simple
ExecStart=${current_dir}/.env/bin/python -m src.node.as_d_agent
ExecStop=/bin/kill -s HUP $MAINPID
Environment=PYTHONUNBUFFERED=1
RestartSec=15
Restart=on-failure

[Install]
WantedBy=default.target
EOF
fi

chmod 644 ${d_agent_pgm_name}.service


r_agent_pgm_name="source2RSS_r_agent"

if [ ! -f ${r_agent_pgm_name}.service ]
then
cat > ./${r_agent_pgm_name}.service <<EOF
[Unit]
Description=source2RSS reverse agent Service
After=network.target

[Service]
WorkingDirectory=${current_dir}
User=${current_uid}
Group=${current_uid}
Type=simple
ExecStart=${current_dir}/.env/bin/python -m src.node.as_r_agent
ExecStop=/bin/kill -s HUP $MAINPID
Environment=PYTHONUNBUFFERED=1
RestartSec=15
Restart=on-failure

[Install]
WantedBy=default.target
EOF
fi

chmod 644 ${r_agent_pgm_name}.service
fi

# vim: expandtab shiftwidth=4 softtabstop=4
