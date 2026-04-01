# 租房数据分析平台

一个基于Flask的租房数据分析和可视化平台，使用Spark进行大规模数据处理。

## 功能特点

- 用户认证系统（注册/登录）
- 租房数据可视化
  - 租金价格分布
  - 面积与价格关系分析
  - 区域价格箱线图
  - 房源分布热力图
- 数据统计分析
- 响应式设计
- 基于Spark的大规模数据处理

## 技术栈

- Backend: Flask
- Database: SQLite
- Frontend: HTML, CSS, JavaScript
- Data Visualization: Plotly.js
- Maps: Baidu Maps API
- Big Data Processing: Apache Spark
- Data Analysis: Pandas

## 系统要求

- Python 3.11+
- Java 8 或更高版本（Spark依赖）
- 足够的系统内存（建议8GB以上）

## 安装说明

1. 克隆项目
```bash
git clone [repository-url]
cd rental-analysis
```

2. 创建虚拟环境
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 配置环境变量
```bash
# Linux/Mac
export FLASK_APP=run.py
export FLASK_ENV=development
export BAIDU_AK=your_baidu_api_key
export JAVA_HOME=/path/to/your/java  # 设置Java环境变量

# Windows
set FLASK_APP=run.py
set FLASK_ENV=development
set BAIDU_AK=your_baidu_api_key
set JAVA_HOME=C:\path\to\your\java  # 设置Java环境变量
```

5. 初始化数据库
```bash
flask db upgrade
```

6. 运行应用
```bash
python run.py
```

## 项目结构
```
rental_analysis/
├── app/                    # 应用主目录
│   ├── auth/              # 认证相关模块
│   ├── main/              # 主要功能模块
│   ├── models/            # 数据模型
│   ├── static/            # 静态文件
│   ├── templates/         # 模板文件
│   └── utils/             # 工具函数
├── data                   # 数据文件
│   ├── input/            # 原始数据
│   └── input/clean/      # 清洗后的数据
├── bianma.py              # 可视化数据地理位置转换为经纬度
├── cleaning.py            # 基于Spark的数据清洗脚本
├── config.py              # 配置文件
├── requirements.txt       # 项目依赖
├── pider58csv.py          # CSV爬虫
├── pider58db.py           # 数据库爬虫
└── run.py                 # 应用入口
```

## 数据处理流程

1. 数据采集
   - 使用`pider58csv.py`和`pider58db.py`采集租房数据
   - 数据存储在`data/input`目录下

2. 数据清洗
   - 使用`cleaning.py`（基于Spark）进行数据清洗
   - 清洗后的数据存储在`data/input/clean`目录下

3. 数据可视化
   - 使用`bianma.py`处理地理位置信息
   - 通过Web界面展示分析结果

## API文档

### 认证接口
- POST /auth/login - 用户登录
- POST /auth/register - 用户注册
- GET /auth/logout - 用户登出

### 数据接口
- GET /api/stats - 获取基础统计数据
- GET /api/price_distribution - 获取价格分布数据
- GET /api/area_price_scatter - 获取面积价格散点图数据
- GET /api/district_price_box - 获取区域价格箱线图数据
- GET /api/dashboard - 获取热力图数据

## 开发指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交改动 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 注意事项

1. 确保系统已正确安装Java环境
2. 首次运行数据清洗脚本可能需要较长时间
3. 定期备份数据库文件



