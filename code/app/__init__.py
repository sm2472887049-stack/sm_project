from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from config import config
import logging

# 初始化扩展
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = '请先登录'
migrate = Migrate()

@login_manager.user_loader
def load_user(user_id):
    from .models.user import User
    return User.query.get(int(user_id))

def create_app(config_name='default'):
    app = Flask(__name__)
    
    # 加载配置
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # 配置日志
    logging.basicConfig(level=logging.INFO)
    
    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # 注册蓝图
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')
    
    # 注册CLI命令
    from . import cli
    cli.init_app(app)
    
    # 导入模型
    from .models.rental import Rental
    from .models.user import User
    
    # 创建数据库表
    with app.app_context():
        db.create_all()
    
    return app 