import os
from datetime import timedelta
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # 基础配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev'
    ADMIN_REGISTRATION_CODE = os.environ.get('ADMIN_REGISTRATION_CODE') or 'admin123'  # 管理员注册码
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 数据库配置
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or '127.0.0.1'
    MYSQL_PORT = os.environ.get('MYSQL_PORT') or '11336'
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'root'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or '123456'
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE') or 'cqzf'
    
    # MySQL连接URL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4'
    
    # 百度地图API配置
    BAIDU_AK = os.environ.get('c2DAbj9olsVQRHs8wNbwCE4k9dTvujiZ')
    
    # 高德地图API配置
    AMAP_KEY = 'b8685a3a98917f4a77007793a8eb685d'  # 高德Web端(JS API)Key
    AMAP_SECURITY_CODE = '3d59923db05c64af87b1628ed0a11080'  # 高德安全密钥
    
    # 会话配置
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # 日志配置
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    
    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

class ProductionConfig(Config):
    DEBUG = False
    # 生产环境配置

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
} 