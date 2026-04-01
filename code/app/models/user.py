from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime
from functools import wraps
from flask import abort
from flask_login import current_user


# 定义用户角色
class UserRole:
    ADMIN = 'admin'
    USER = 'user'

    @staticmethod
    def get_roles():
        return [UserRole.ADMIN, UserRole.USER]


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(512))
    role = db.Column(db.String(20), nullable=False, default=UserRole.USER)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        """设置用户密码"""
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)

    def update_last_login(self):
        """更新最后登录时间"""
        self.last_login = datetime.utcnow()
        db.session.commit()

    @property
    def is_admin(self):
        """判断用户是否是管理员"""
        return self.role == UserRole.ADMIN

    def __repr__(self):
        """用户的字符串表示"""
        return f'<User {self.username}>'

    def to_dict(self):
        """将用户信息转为字典格式"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'last_login': self.last_login.strftime('%Y-%m-%d %H:%M:%S') if self.last_login else None,
            'is_active': self.is_active
        }

    @staticmethod
    def get_user_by_username(username):
        """根据用户名查询用户"""
        return User.query.filter_by(username=username).first()

    @staticmethod
    def get_user_by_email(email):
        """根据邮箱查询用户"""
        return User.query.filter_by(email=email).first()


def admin_required(f):
    """管理员权限验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function
