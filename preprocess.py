# 添加命令行参数解析，调用 configHandle，调用 dataHandle，实例一些全局类
import argparse

from configHandle import Config

# 创建一个解析器
parser = argparse.ArgumentParser(description="Your script description")
# 添加你想要接收的命令行参数
parser.add_argument('--config', required=False, default='./config_and_data_files/config.yaml', help='Config File Path')
# 解析命令行参数
args = parser.parse_args()

# 将参数值赋给你的变量
configfile = args.config

# 定义所有变量
config = Config(configfile)

# 如果前面没出错，可以加载持久化的数据
from dataHandle import Data

data = Data(config)