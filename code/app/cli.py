import click
from flask.cli import with_appcontext
from app.models.user import User
from app import db

def init_app(app):
    """注册命令行命令"""
    app.cli.add_command(create_test_user)

@click.command('create-test-user')
@with_appcontext
def create_test_user():
    """创建测试用户"""
    username = 'admin'
    password = 'admin123'
    email = 'admin@example.com'
    
    if User.query.filter_by(username=username).first():
        click.echo('测试用户已存在')
        return
    
    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo('测试用户创建成功！') 