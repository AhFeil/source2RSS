#!/bin/bash
# setup4host.sh - set up virtual environment, install dependencies and create systemd file

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
playwright install
# 如果显示缺乏依赖
# python -m playwright install --with-deps

# 配置文件。若不存在 config_and_data_files 就自动复制示例配置文件，否则不操作
if [ ! -d config_and_data_files ]
then
    mkdir config_and_data_files && \
    cp libs/config.example.yaml config_and_data_files/config.yaml
fi

# 创建 systemd 配置文件
if [ ! -d ${program_name}.service ]
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


# vim: expandtab shiftwidth=4 softtabstop=4
