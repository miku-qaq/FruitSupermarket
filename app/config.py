# app/config.py

import os
from dotenv import load_dotenv

# 加载环境变量 (用于安全地存储数据库密码等敏感信息)
load_dotenv()


class Config:
    # 秘钥：用于保护会话和 CSRF 令牌等
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess-a-strong-secret-key'

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'mysql+pymysql://root:password@localhost:3306/fruit_supermarket_db'

    # 关闭 SQLALCHEMY 跟踪，以节省资源
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 可视化报表配置（如果使用 Echarts 或 Plotly）
    CHART_COLORS = ['#5470C6', '#91CC75', '#EE6666', '#73C0DE', '#FAC858']