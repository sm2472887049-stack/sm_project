from flask import Blueprint

main = Blueprint('main', __name__)

# 在创建Blueprint后导入路由
from . import routes 