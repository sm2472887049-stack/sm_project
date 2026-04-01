from urllib import request
from . import main
from sqlalchemy import text
import plotly.express as px
import pandas as pd
from flask import render_template, jsonify, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from app import db
from app.models.rental import Rental
from app.models.user import User, admin_required
import numpy as np
from werkzeug.utils import secure_filename
import os
import json
from app.models.price_predictor import PricePredictor
from datetime import datetime, timedelta

# ===============================================================
# 工具函数部分
# ===============================================================

def convert_ndarray(obj):
    """递归转换所有的ndarray为列表
    
    Plotly图表处理时需要将NumPy数组转换为普通列表
    
    参数:
        obj: 需要转换的对象，可能是ndarray、字典或列表
        
    返回:
        转换后的对象
    """
    if isinstance(obj, np.ndarray):
        return obj.tolist()  # 将ndarray转换为列表
    elif isinstance(obj, dict):
        return {key: convert_ndarray(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_ndarray(item) for item in obj]
    return obj


# ===============================================================
# 页面路由部分
# ===============================================================

@main.route('/')
@login_required
def index():
    """主页面，显示基本统计信息"""
    try:
        # 检查数据库连接和总记录数
        total_count = db.session.execute(text("SELECT COUNT(*) FROM rentals")).scalar()
        current_app.logger.info(f"数据库总记录数: {total_count}")

        # 1. 基础统计数据
        stats_sql = text("""
        SELECT 
            COUNT(*) as total,
            AVG(CAST(REPLACE(REPLACE(price, '元/月', ''), '元', '') AS DECIMAL(10,2))) as avg_price,
            AVG(CAST(REPLACE(REPLACE(area, '平米', ''), '㎡', '') AS DECIMAL(10,2))) as avg_area,
            COUNT(DISTINCT SUBSTRING_INDEX(location, ' ', 1)) as districts,
            COUNT(DISTINCT city) as cities
        FROM rentals
        WHERE price REGEXP '^[0-9]'
        """)
        stats_result = db.session.execute(stats_sql).fetchone()
        current_app.logger.info(f"基础统计结果: {stats_result}")

        # 2. 各城市房源数量统计
        city_stats_sql = text("""
        SELECT 
            city,
            COUNT(*) as count,
            AVG(CAST(REPLACE(REPLACE(price, '元/月', ''), '元', '') AS DECIMAL(10,2))) as avg_price
        FROM rentals
        WHERE price REGEXP '^[0-9]'
        GROUP BY city
        ORDER BY count DESC
        """)
        city_stats = db.session.execute(city_stats_sql).fetchall()
        current_app.logger.info(f"城市统计数量: {len(city_stats)}")

        # 3. 获取最新的10条房源信息
        latest_rentals_sql = text("""
        SELECT 
            id,
            city,
            title,
            price,
            area,
            location,
            url,
            created_at
        FROM rentals
        ORDER BY created_at DESC
        LIMIT 10
        """)
        latest_rentals = db.session.execute(latest_rentals_sql).fetchall()
        current_app.logger.info(f"最新房源数量: {len(latest_rentals)}")
        if len(latest_rentals) > 0:
            current_app.logger.info(f"第一条房源记录: {latest_rentals[0]}")

        # 4. 构建统计数据字典
        stats = {
            'total_listings': stats_result[0] or 0,
            'avg_price': round(float(stats_result[1] or 0), 2),
            'avg_area': round(float(stats_result[2] or 0), 2),
            'districts': stats_result[3] or 0,
            'cities': stats_result[4] or 0
        }

        # 5. 处理城市统计数据
        city_data = [{
            'city': row[0],
            'count': row[1],
            'avg_price': round(float(row[2] or 0), 2)
        } for row in city_stats]

        # 6. 处理最新房源数据
        latest_listings = []
        for row in latest_rentals:
            try:
                listing = {
                    'id': row[0],
                    'city': row[1],
                    'title': row[2],
                    'price': row[3],
                    'area': row[4],
                    'location': row[5],
                    'url': row[6],
                    'created_at': row[7].strftime('%Y-%m-%d %H:%M:%S') if row[7] else None
                }
                latest_listings.append(listing)
            except Exception as e:
                current_app.logger.error(f"处理房源记录时出错: {str(e)}, 记录: {row}")

        current_app.logger.info(f"处理后的最新房源数量: {len(latest_listings)}")

        return render_template('main/index.html',
                             stats=stats,
                             city_data=city_data,
                             latest_listings=latest_listings)
    except Exception as e:
        current_app.logger.error(f"Error fetching statistics data: {str(e)}")
        return render_template('main/index.html',
                             stats={'total_listings': 0, 'avg_price': 0, 'avg_area': 0,
                                   'districts': 0, 'cities': 0},
                             city_data=[],
                             latest_listings=[],
                             error_message=f"发生错误: {str(e)}")


@main.route('/dashboard')
@login_required
def dashboard():
    """大屏可视化页面 - 显示房源地理分布热力图
    
    加载带有地理坐标的房源数据，用于在地图上展示房源分布
    """
    try:
        # 读取包含地理位置坐标的JSON文件
        json_file_path = './data/locations_with_coordinates_1.json'
        if not os.path.exists(json_file_path):
            return render_template('main/dashboard.html', error_message="JSON 文件未找到！")

        # 读取生成的 JSON 文件
        with open(json_file_path, 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)

        # 确保 data 是 JSON 可序列化的
        if data is None or len(data) == 0:
            return render_template('main/dashboard.html', error_message="没有有效的数据！")

        # 过滤掉无效的数据（不包含经纬度的数据点）
        filtered_data = [item for item in data if
                         item.get('latitude') is not None and item.get('longitude') is not None]

        # 将过滤后的数据传递到前端
        return render_template('main/dashboard.html', data=filtered_data)

    except Exception as e:
        current_app.logger.error(f"Error generating dashboard: {str(e)}")
        return render_template('main/dashboard.html', error_message=f"加载失败: {str(e)}")


@main.route('/price-distribution')
@login_required
def price_distribution():
    """价格分布分析页面
    
    展示租金价格分布的可视化页面，包括不同价格区间的分布情况
    """
    return render_template('main/price_distribution.html')


@main.route('/area-price')
@login_required
def area_price():
    """面积与租金关系分析页面
    
    展示房屋面积与租金价格关系的可视化页面
    """
    return render_template('main/area_price.html')


@main.route('/district-analysis')
@login_required
def district_analysis():
    """区域与租金分析页面
    
    展示不同城市各区域租金价格对比的可视化页面
    支持按城市筛选查看不同区域的分析结果
    """
    try:
        # 获取所有城市列表
        cities_sql = """
            SELECT DISTINCT city 
            FROM rentals 
            WHERE city IS NOT NULL 
            ORDER BY city
        """
        cities = [row[0] for row in db.session.execute(text(cities_sql))]
        
        # 获取选中的城市（默认选择第一个城市）
        selected_city = request.args.get('city', cities[0] if cities else None)
        
        if selected_city:
            # 获取选中城市的区域数据
            district_sql = """
                SELECT 
                    SUBSTRING_INDEX(location, ' ', 1) as district,
                    COUNT(*) as count,
                    AVG(CAST(REPLACE(REPLACE(price, '元/月', ''), '元', '') AS DECIMAL(10,2))) as avg_price,
                    MIN(CAST(REPLACE(REPLACE(price, '元/月', ''), '元', '') AS DECIMAL(10,2))) as min_price,
                    MAX(CAST(REPLACE(REPLACE(price, '元/月', ''), '元', '') AS DECIMAL(10,2))) as max_price,
                    AVG(CAST(REPLACE(REPLACE(area, '平米', ''), '㎡', '') AS DECIMAL(10,2))) as avg_area
                FROM rentals
                WHERE city = :city
                    AND price REGEXP '^[0-9]'
                GROUP BY SUBSTRING_INDEX(location, ' ', 1)
                HAVING count >= 3
                ORDER BY count DESC
            """
            districts_data = db.session.execute(text(district_sql), {'city': selected_city}).fetchall()
            
            # 处理数据
            districts = []
            for row in districts_data:
                districts.append({
                    'district': row.district,
                    'count': row.count,
                    'avg_price': round(float(row.avg_price), 2),
                    'min_price': round(float(row.min_price), 2),
                    'max_price': round(float(row.max_price), 2),
                    'avg_area': round(float(row.avg_area), 2)
                })
            
            # 计算城市整体统计
            city_stats = {
                'total_count': sum(d['count'] for d in districts),
                'avg_price': round(sum(d['avg_price'] * d['count'] for d in districts) / 
                                 sum(d['count'] for d in districts), 2),
                'districts_count': len(districts)
            }
        else:
            districts = []
            city_stats = {'total_count': 0, 'avg_price': 0, 'districts_count': 0}
        
        return render_template('main/district_analysis.html',
                             cities=cities,
                             selected_city=selected_city,
                             districts=districts,
                             city_stats=city_stats)
                             
    except Exception as e:
        current_app.logger.error(f"区域分析错误: {str(e)}")
        flash('加载区域分析数据时发生错误，请稍后再试', 'error')
        return render_template('main/district_analysis.html',
                             cities=[],
                             selected_city=None,
                             districts=[],
                             city_stats={'total_count': 0, 'avg_price': 0, 'districts_count': 0})


@main.route('/recommendation')
@login_required
def recommendation():
    """热门房源推荐页面
    
    基于机器学习算法的智能房源推荐系统
    根据用户选择的条件智能推荐最适合的房源
    """
    try:
        # 查询所有不同的城市和区域名称
        sql = text("""
        SELECT DISTINCT city, SUBSTRING_INDEX(location, ' ', 1) as district
        FROM rentals
        ORDER BY city, district
        """)
        results = db.session.execute(sql).fetchall()
        
        # 整理城市和区域数据
        cities = []
        districts_by_city = {}
        for row in results:
            city = row[0]
            district = row[1]
            if city not in cities:
                cities.append(city)
                districts_by_city[city] = []
            if district and district not in districts_by_city[city]:
                districts_by_city[city].append(district)
        
        # 获取价格和面积的范围
        sql_range = text("""
        SELECT 
            MIN(CAST(REPLACE(REPLACE(price, '元/月', ''), '元', '') AS DECIMAL(10,2))) as min_price,
            MAX(CAST(REPLACE(REPLACE(price, '元/月', ''), '元', '') AS DECIMAL(10,2))) as max_price,
            MIN(CAST(REPLACE(REPLACE(area, '平米', ''), '㎡', '') AS DECIMAL(10,2))) as min_area,
            MAX(CAST(REPLACE(REPLACE(area, '平米', ''), '㎡', '') AS DECIMAL(10,2))) as max_area
        FROM rentals
        """)
        range_data = db.session.execute(sql_range).fetchone()
        
        price_range = {
            'min': int(range_data.min_price) if range_data.min_price else 0,
            'max': int(range_data.max_price) if range_data.max_price else 10000
        }
        
        area_range = {
            'min': int(range_data.min_area) if range_data.min_area else 0,
            'max': int(range_data.max_area) if range_data.max_area else 200
        }
        
        return render_template(
            'main/recommendation.html',
            cities=cities,
            districts_by_city=districts_by_city,
            price_range=price_range,
            area_range=area_range
        )
    except Exception as e:
        current_app.logger.error(f"Error loading recommendation page: {str(e)}")
        return render_template(
            'main/recommendation.html',
            error_message=f"加载页面失败: {str(e)}",
            cities=[],
            districts_by_city={},
            price_range={'min': 0, 'max': 10000},
            area_range={'min': 0, 'max': 200}
        )


# ===============================================================
# API路由部分 - 为可视化提供数据
# ===============================================================

@main.route('/api/price_distribution')
@login_required
def get_price_distribution():
    """获取价格分布数据的API
    
    返回:
        - 柱状图数据：显示各价格区间的房源数量
        - 饼图数据：显示各价格区间的占比
        - 统计信息：总数量、平均价格、最低价格、最高价格
    """
    try:
        # 获取所有租房数据
        rentals = Rental.query.all()
        
        # 提取有效的价格数据
        prices = [rental.price_value for rental in rentals if rental.price_value > 0]
        if not prices:

            return jsonify({'error': '没有找到有效的价格数据'})

        # 计算基本统计信息
        total_count = len(prices)
        avg_price = sum(prices) / total_count
        min_price = min(prices)
        max_price = max(prices)

        # 定义价格区间
        price_ranges = [
            (0, 1000, '1000元以下'),
            (1001, 2000, '1001-2000元'),
            (2001, 3000, '2001-3000元'),
            (3001, 4000, '3001-4000元'),
            (4001, 5000, '4001-5000元'),
            (5001, float('inf'), '5000元以上')
        ]
        
        # 统计每个区间的房源数量
        range_counts = {range_label: 0 for _, _, range_label in price_ranges}
        for price in prices:
            for min_price_range, max_price_range, range_label in price_ranges:
                if min_price_range <= price <= max_price_range:
                    range_counts[range_label] += 1
                    break
        
        # 准备柱状图数据
        histogram_data = {
            'data': [{
                'x': list(range_counts.keys()),
                'y': list(range_counts.values()),
                'type': 'bar',
                'name': '房源数量',
                'marker': {
                    'color': '#1f77b4',
                    'opacity': 0.8
                },
                'text': [f'{count}套<br>{(count/total_count*100):.1f}%' for count in range_counts.values()],
                'textposition': 'auto',
                'hovertemplate': 
                    "价格区间: %{x}<br>" +
                    "房源数量: %{y}套<br>" +
                    "占比: %{text}<br>" +
                    "<extra></extra>"
            }],
            'layout': {
                'xaxis': {
                    'title': '租金区间',
                    'tickangle': -45
                },
                'yaxis': {
                    'title': '房源数量',
                    'gridcolor': '#f0f0f0'
                },
                'showlegend': False,
                'plot_bgcolor': 'white',
                'bargap': 0.2
            }
        }

        # 准备饼图数据
        pie_data = {
            'data': [{
                'labels': list(range_counts.keys()),
                'values': list(range_counts.values()),
                'type': 'pie',
                'hole': 0.4,
                'textinfo': 'label+percent',
                'textposition': 'outside',
                'marker': {
                    'colors': ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
                },
                'hovertemplate': 
                    "价格区间: %{label}<br>" +
                    "房源数量: %{value}套<br>" +
                    "占比: %{percent}<br>" +
                    "<extra></extra>"
            }],
            'layout': {
                'showlegend': True,
                'legend': {
                    'orientation': 'h',
                    'y': -0.1
                }
            }
        }

        # 返回完整的数据包
        return jsonify({
            'histogram': histogram_data,  # 柱状图数据
            'pie': pie_data,              # 饼图数据
            'stats': {
                'total_count': total_count,
                'avg_price': round(avg_price, 2),
                'min_price': min_price,
                'max_price': max_price
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching price distribution data: {str(e)}")
        return jsonify({'error': str(e)}), 500


@main.route('/api/area_price')
def get_area_price():
    """获取面积与租金关系数据的API
    
    分析面积与租金的关系，包括:
    - 散点图数据（直接展示面积与租金的对应关系）
    - 趋势线数据（价格与面积的线性回归）
    - 分区间的平均价格数据
    - 相关统计信息（相关系数、样本数量、平均值等）
    """
    try:
        # 1. 使用MySQL兼容的SQL查询
        sql = text("""
            SELECT 
                CAST(
                    REPLACE(
                        REPLACE(
                            REPLACE(area, '平米', ''),
                            '㎡', ''
                        ),
                        ' ', ''
                    ) AS DECIMAL(10,2)
                ) as area_value,
                CAST(
                    REPLACE(
                        REPLACE(
                            REPLACE(price, '元/月', ''),
                            '元', ''
                        ),
                        ' ', ''
                    ) AS DECIMAL(10,2)
                ) as price_value,
                title,
                location
            FROM rentals
            WHERE area IS NOT NULL 
                AND price IS NOT NULL
                AND area != ''
                AND price != ''
                AND area REGEXP '^[0-9]'
                AND price REGEXP '^[0-9]'
            HAVING area_value BETWEEN 10 AND 300
                AND price_value BETWEEN 100 AND 50000
            ORDER BY area_value
        """)
        
        try:
            result = db.session.execute(sql)
            rows = result.fetchall()
        except Exception as e:
            current_app.logger.error(f"Database query error: {str(e)}")
            return jsonify({'error': '数据库查询错误'}), 500
        
        if not rows:
            return jsonify({
                'areas': [],
                'prices': [],
                'hover_texts': [],
                'stats': {
                    'sample_count': 0,
                    'avg_price': 0,
                    'avg_area': 0,
                    'correlation': 0
                }
            })

        # 2. 数据处理优化
        areas = []
        prices = []
        hover_texts = []
        
        # 一次性处理所有数据
        for row in rows:
            try:
                area = float(row[0]) if row[0] is not None else None
                price = float(row[1]) if row[1] is not None else None
                
                if area is not None and price is not None:
                    areas.append(area)
                    prices.append(price)
                    hover_texts.append(f"{row[2]}<br>{row[3]}")
            except (ValueError, TypeError) as e:
                current_app.logger.warning(f"Data conversion error: {str(e)}")
                continue

        # 3. 计算基本统计信息
        sample_count = len(areas)
        if sample_count == 0:
            return jsonify({
                'areas': [],
                'prices': [],
                'hover_texts': [],
                'stats': {
                    'sample_count': 0,
                    'avg_price': 0,
                    'avg_area': 0,
                    'correlation': 0
                }
            })
        avg_area = sum(areas) / sample_count
        avg_price = sum(prices) / sample_count
        # 4. 计算相关系数
        try:
            # 使用numpy进行向量化计算，提高性能
            areas_np = np.array(areas)
            prices_np = np.array(prices)
            
            correlation = np.corrcoef(areas_np, prices_np)[0, 1]
            if np.isnan(correlation):
                correlation = 0
        except Exception as e:
            current_app.logger.error(f"Correlation calculation error: {str(e)}")
            correlation = 0
        # 5. 计算趋势线
        try:
            coefficients = np.polyfit(areas, prices, 1)
            trend_x = [min(areas), max(areas)]
            trend_y = [float(coefficients[0] * x + coefficients[1]) for x in trend_x]
        except Exception as e:
            current_app.logger.error(f"Trend line calculation error: {str(e)}")
            trend_x = []
            trend_y = []

        # 6. 计算面积区间统计
        try:
            df = pd.DataFrame({'area': areas, 'price': prices})
            df['area_range'] = (df['area'] // 10) * 10
            
            # 只保留样本数量>=3的区间
            range_stats = df.groupby('area_range').agg({
                'price': ['mean', 'min', 'max', 'count']
            }).reset_index()
            range_stats = range_stats[range_stats[('price', 'count')] >= 3]

            if not range_stats.empty:
                avg_by_area_x = (range_stats['area_range'] + 5).tolist()
                avg_by_area_y = range_stats[('price', 'mean')].tolist()
                min_by_area_y = range_stats[('price', 'min')].tolist()
                max_by_area_y = range_stats[('price', 'max')].tolist()
            else:
                avg_by_area_x = []
                avg_by_area_y = []
                min_by_area_y = []
                max_by_area_y = []
        except Exception as e:
            current_app.logger.error(f"Range statistics calculation error: {str(e)}")
            avg_by_area_x = []
            avg_by_area_y = []
            min_by_area_y = []
            max_by_area_y = []

        # 7. 返回优化后的数据结构
        return jsonify({
            'areas': areas[:1000],  # 限制返回的数据点数量
            'prices': prices[:1000],
            'hover_texts': hover_texts[:1000],
            'trend': {
                'x': trend_x,
                'y': trend_y
            },
            'range_stats': {
                'x': avg_by_area_x,
                'avg_y': avg_by_area_y,
                'min_y': min_by_area_y,
                'max_y': max_by_area_y
            },
            'stats': {
                'correlation': round(float(correlation), 3),
                'sample_count': sample_count,
                'avg_price': round(float(avg_price), 2),
                'avg_area': round(float(avg_area), 2)
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error in area price analysis: {str(e)}")
        return jsonify({'error': '数据分析过程中发生错误，请稍后再试'}), 500


@main.route('/api/area_price_scatter')
@login_required
def get_area_price_scatter():
    """获取面积与租金散点图数据的简化API
    
    使用Plotly Express直接生成面积与租金关系的散点图
    这个API直接返回完整的Plotly图表配置
    
    返回:
        包含散点图完整配置的JSON数据
    """
    try:
        # 使用SQL查询从数据库获取处理后的面积和价格数据
        sql = """
        SELECT 
            CAST(REPLACE(REPLACE(area, '平米', ''), '㎡', '') AS DECIMAL(10,2)) as area,
            CAST(REPLACE(REPLACE(price, '元/月', ''), '元', '') AS DECIMAL(10,2)) as price 
        FROM rentals
        """
        # 使用pandas直接读取SQL查询结果
        df = pd.read_sql(sql, db.engine)
        if df.empty:
            return jsonify({'error': '暂无数据'})

        # 使用Plotly Express生成散点图
        fig = px.scatter(df, x='area', y='price',
                         title='面积与租金关系',
                         labels={'area': '面积（平方米）', 'price': '租金（元/月）'})

        # 将图表转换为字典，并确保NumPy数组被转换为普通列表
        fig_dict = convert_ndarray(fig.to_dict())

        return jsonify(fig_dict)
    except Exception as e:
        current_app.logger.error(f"Error fetching area_price_scatter data: {str(e)}")
        return jsonify({'error': str(e)}), 500


@main.route('/api/district_price_box')
@login_required
def get_district_price_box():
    """获取区域与租金箱线图数据的API
    
    分析不同区域的租金分布情况，返回箱线图数据，包括:
    - 每个区域的租金分布箱线图
    - 每个区域的租金统计信息（样本数、平均值、最小值、最大值）
    """
    try:
        # 获取所有有效的租房数据
        rentals = Rental.query.all()
        
        # 按区域分组数据
        district_data = {}
        for rental in rentals:
            price = rental.price_value  # 使用模型的price_value方法
            district = rental.district  # 使用模型的district方法
            
            # 验证数据有效性
            if price <= 0 or not district:
                continue
                
            if district not in district_data:
                district_data[district] = []
            district_data[district].append(price)
        
        # 准备箱线图数据和统计信息
        box_data = []
        stats = []
        
        # 处理每个区域的数据
        for district, prices in district_data.items():
            # 只处理样本数量大于等于5的区域
            if len(prices) < 5:
                continue
                
            # 计算统计信息
            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)
            
            # 添加箱线图数据
            box_data.append({
                'y': prices,  # 价格数据作为Y轴值
                'name': f"{district}\n(n={len(prices)})",  # 显示区域名称和样本数
                'type': 'box',  # 图表类型：箱线图
                'boxpoints': 'outliers',  # 只显示异常值点
                'boxmean': True,  # 显示均值线
                'line': {
                    'width': 2
                },
                'marker': {
                    'color': '#1f77b4',
                    'outliercolor': 'rgba(219, 64, 82, 0.6)',  # 异常值点颜色
                    'size': 4
                },
                'hovertemplate': 
                    f"区域: {district}<br>" +
                    "租金: %{y:,.0f}元/月<br>" +
                    f"样本数: {len(prices)}<br>" +
                    "<extra></extra>"
            })
            
            # 添加统计信息
            stats.append({
                'district': district,
                'count': len(prices),
                'avg_price': round(avg_price, 2),
                'min_price': min_price,
                'max_price': max_price
            })
        
        if not box_data:
            return jsonify({'error': '没有找到有效的数据进行分析'})
            
        # 按平均价格降序排序统计信息
        stats.sort(key=lambda x: x['avg_price'], reverse=True)
        
        # 返回完整的数据包
        return jsonify({
            'data': box_data,  # 箱线图数据
            'stats': stats     # 统计信息
        })

    except Exception as e:
        current_app.logger.error(f"Error in district price box analysis: {str(e)}")
        return jsonify({'error': str(e)}), 500


@main.route('/import-csv', methods=['POST'])
@login_required
@admin_required
def import_csv_data():
    """导入CSV数据到数据库
    
    处理用户上传的CSV文件，将其中的租房数据导入到数据库中
    CSV文件必须包含必要的字段：title, price, area, location等
    
    返回:
        重定向到首页，并显示导入结果的闪现消息
    """
    # 检查是否有文件上传
    if 'file' not in request.files:
        flash('没有选择文件', 'error')
        return redirect(url_for('main.index'))

    file = request.files['file']

    # 检查文件名是否为空
    if file.filename == '':
        flash('没有选择文件', 'error')
        return redirect(url_for('main.index'))

    # 验证文件类型
    if file and allowed_file(file.filename):  # 确保是允许的文件类型
        # 使用secure_filename确保文件名安全
        filename = secure_filename(file.filename)

        # 使用pandas读取CSV文件
        try:
            df = pd.read_csv(file)

            # 数据验证和导入处理
            for index, row in df.iterrows():
                # 创建Rental对象并添加到数据库
                try:
                    rental = Rental(
                        city=row['city'],           # 城市名称
                        title=row['title'],         # 房源标题
                        price=row['price'],         # 租金价格
                        area=row['area'],           # 房屋面积
                        location=row['location'],   # 位置信息
                        source_url=row['url'],      # 来源链接
                        img_url=row['img_url'],     # 图片链接
                        agent_name=row['agent_name'],      # 中介名称
                        agent_company=row['agent_company'] # 中介公司
                    )
                    db.session.add(rental)
                except Exception as e:
                    # 记录导入失败的行
                    print(f"Error inserting row {index}: {str(e)}")

            # 提交所有的插入操作
            db.session.commit()
            flash(f"成功导入 {len(df)} 条数据", 'success')

        except Exception as e:
            flash(f"CSV 文件处理失败: {str(e)}", 'error')
            return redirect(url_for('main.index'))

    else:
        flash('无效的文件类型，请上传CSV文件', 'error')

    return redirect(url_for('main.index'))


def allowed_file(filename):
    """检查文件扩展名是否为csv
    
    参数:
        filename: 文件名
        
    返回:
        布尔值，表示文件是否是CSV格式
    """
    ALLOWED_EXTENSIONS = {'csv'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@main.route('/export-csv', methods=['POST'])
@login_required
@admin_required
def export_csv_data():
    """导出CSV数据的路由
    
    将数据库中的租房数据导出为CSV文件
    
    返回:
        重定向到首页，并显示导出结果的闪现消息
    """
    file_name = request.form['file_name']  # 获取用户输入的文件名
    if not file_name.endswith('.csv'):
        file_name += '.csv'  # 如果文件名没有.csv后缀，则自动添加

    # 调用导出函数
    success, message = export_to_csv(file_name)
    if success:
        flash(message, 'success')
    else:
        flash('导出失败：' + message, 'error')

    return redirect(url_for('main.index'))


def export_to_csv(file_name='export_data.csv'):
    """导出数据到CSV文件
    
    参数:
        file_name: 导出文件名，默认为'export_data.csv'
        
    返回:
        (success, message) - 元组，表示操作是否成功及相关信息
    """
    try:
        # 查询所有租房数据
        rentals = Rental.query.all()

        # 转换为DataFrame格式
        data = []
        for rental in rentals:
            data.append({
                'title': rental.title,               # 房源标题
                'price': rental.price,               # 租金价格
                'area': rental.area,                 # 房屋面积
                'location': rental.location,         # 位置信息
                'url': rental.source_url,            # 来源链接
                'img_url': rental.img_url,           # 图片链接
                'agent_name': rental.agent_name,     # 中介名称
                'agent_company': rental.agent_company # 中介公司
            })

        df = pd.DataFrame(data)

        # 创建保存文件的目录
        data_dir = os.path.join(current_app.root_path, '..', 'data/output')
        os.makedirs(data_dir, exist_ok=True)  # 确保目录存在

        # 保存为CSV文件
        csv_path = os.path.join(data_dir, file_name)
        df.to_csv(csv_path, index=False, encoding='utf-8')

        return True, f"成功导出 {len(data)} 条数据到 {csv_path}"
    except Exception as e:
        return False, str(e)


# ===============================================================
# 数据管理相关路由
# ===============================================================

@main.route('/data-management')
@login_required
@admin_required
def data_management():
    """数据管理页面：展示数据并提供增删改查功能
    
    提供租房数据的完整管理功能，包括:
    - 分页浏览所有数据
    - 搜索特定数据
    - 添加/编辑/删除数据
    
    返回:
        渲染后的数据管理页面
    """
    try:
        # 1. 获取分页参数
        page = request.args.get('page', 1, type=int)        # 当前页码，默认第1页
        per_page = request.args.get('per_page', 15, type=int)  # 每页显示数量，默认15条
        
        # 2. 获取搜索参数和城市筛选参数
        search_term = request.args.get('search', '')
        selected_city = request.args.get('city', '')
        
        # 3. 构建查询
        query = Rental.query
        
        # 4. 添加筛选条件
        # 4.1 如果选择了城市，添加城市筛选
        if selected_city:
            query = query.filter(Rental.city == selected_city)
            
        # 4.2 如果有搜索条件，添加搜索过滤器
        if search_term:
            search_pattern = f'%{search_term}%'  # 模糊匹配
            query = query.filter(
                db.or_(  # 多字段匹配任一条件
                    Rental.title.like(search_pattern),     # 标题匹配
                    Rental.location.like(search_pattern),  # 位置匹配
                    Rental.price.like(search_pattern),     # 价格匹配
                    Rental.area.like(search_pattern)       # 面积匹配
                )
            )
        
        # 5. 获取所有城市列表（用于下拉框）
        cities_query = db.session.query(Rental.city).distinct().order_by(Rental.city)
        cities = [city[0] for city in cities_query.all() if city[0]]  # 过滤掉空值
        
        # 6. 获取结果总数用于分页计算
        total_count = query.count()
        
        # 7. 分页并获取当前页的数据
        paginated_rentals = query.order_by(Rental.id.desc()).paginate(  # 按ID降序排列
            page=page, per_page=per_page, error_out=False
        )
        
        # 8. 计算统计信息
        stats = {
            'total_count': total_count,                      # 总数据条数
            'displayed_count': len(paginated_rentals.items), # 当前页显示条数
            'page_count': paginated_rentals.pages,           # 总页数
            'current_page': page                             # 当前页码
        }
        
        # 9. 渲染模板
        return render_template(
            'main/data_management.html',
            rentals=paginated_rentals.items,  # 当前页的数据
            pagination=paginated_rentals,     # 分页对象
            stats=stats,                      # 统计信息
            search_term=search_term,          # 搜索关键词
            cities=cities,                    # 城市列表
            selected_city=selected_city       # 当前选中的城市
        )
    except Exception as e:
        # 出现异常时记录错误并返回错误提示
        current_app.logger.error(f"Error in data management: {str(e)}")
        return render_template(
            'main/data_management.html',
            error_message=f"加载数据失败: {str(e)}",
            rentals=[],
            pagination=None,
            stats={'total_count': 0, 'displayed_count': 0, 'page_count': 0, 'current_page': 1},
            search_term="",
            cities=[],
            selected_city=""
        )


# ===============================================================
# 租房数据CRUD操作的API端点
# ===============================================================

@main.route('/api/rentals/<int:rental_id>', methods=['GET'])
@login_required
@admin_required
def get_rental(rental_id):
    """获取单个租房信息API
    
    参数:
        rental_id: 租房信息ID
        
    返回:
        JSON格式的租房详细信息
    """
    try:
        # 查询指定ID的租房信息，不存在则返回404错误
        rental = Rental.query.get_or_404(rental_id)
        
        # 转换为JSON格式返回
        return jsonify({
            'id': rental.id,
            'city': rental.city,
            'title': rental.title,
            'price': rental.price,
            'area': rental.area,
            'location': rental.location,
            'url': rental.source_url,
            'img_url': rental.img_url,
            'agent_name': rental.agent_name,
            'agent_company': rental.agent_company
        })
    except Exception as e:
        current_app.logger.error(f"Error getting rental {rental_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@main.route('/api/rentals', methods=['POST'])
@login_required
@admin_required
def create_rental():
    """创建新的租房信息API
    
    接收JSON格式的租房数据，创建新的租房记录
    
    返回:
        JSON格式的创建结果，包含新记录的ID
    """
    try:
        # 获取JSON数据
        data = request.json
        
        # 验证必填字段
        required_fields = ['title', 'price', 'area', 'location']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'缺少必填字段: {field}'}), 400
        
        # 创建新的租房记录
        rental = Rental(
            title=data.get('title'),
            price=data.get('price'),
            area=data.get('area'),
            location=data.get('location'),
            city=data.get('city'),  
            url=data.get('url', ''),
            img_url=data.get('img_url', ''),
            agent_name=data.get('agent_name', ''),
            agent_company=data.get('agent_company', '')
        )
        
        # 保存到数据库
        db.session.add(rental)
        db.session.commit()
        
        # 返回创建成功信息和新记录ID
        return jsonify({
            'message': '创建成功',
            'id': rental.id
        }), 201
        
    except Exception as e:
        # 出现异常时回滚事务
        db.session.rollback()
        current_app.logger.error(f"Error creating rental: {str(e)}")
        return jsonify({'error': str(e)}), 500


@main.route('/api/rentals/<int:rental_id>', methods=['PUT'])
@login_required
@admin_required
def update_rental(rental_id):
    """更新租房信息API
    
    接收JSON格式的租房数据，更新指定ID的租房记录
    
    参数:
        rental_id: 要更新的租房信息ID
        
    返回:
        JSON格式的更新结果
    """
    try:
        # 查询指定ID的租房信息，不存在则返回404错误
        rental = Rental.query.get_or_404(rental_id)
        
        # 获取JSON数据
        data = request.json
        
        # 更新各个字段（只更新提供的字段）
        if 'city' in data:
            rental.city = data['city']
        if 'title' in data:
            rental.title = data['title']
        if 'price' in data:
            rental.price = data['price']
        if 'area' in data:
            rental.area = data['area']
        if 'location' in data:
            rental.location = data['location']
        if 'url' in data:
            rental.url = data['url']
        if 'img_url' in data:
            rental.img_url = data['img_url']
        if 'agent_name' in data:
            rental.agent_name = data['agent_name']
        if 'agent_company' in data:
            rental.agent_company = data['agent_company']
        
        # 保存更新
        db.session.commit()
        
        # 返回更新成功信息
        return jsonify({
            'message': '更新成功',
            'id': rental.id
        })
        
    except Exception as e:
        # 出现异常时回滚事务
        db.session.rollback()
        current_app.logger.error(f"Error updating rental {rental_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@main.route('/api/rentals/<int:rental_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_rental(rental_id):
    """删除租房信息API
    
    删除指定ID的租房记录
    
    参数:
        rental_id: 要删除的租房信息ID
        
    返回:
        JSON格式的删除结果
    """
    try:
        # 查询指定ID的租房信息，不存在则返回404错误
        rental = Rental.query.get_or_404(rental_id)
        
        # 从数据库中删除
        db.session.delete(rental)
        db.session.commit()
        
        # 返回删除成功信息
        return jsonify({
            'message': '删除成功'
        })
        
    except Exception as e:
        # 出现异常时回滚事务
        db.session.rollback()
        current_app.logger.error(f"Error deleting rental {rental_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@main.route('/api/rentals/batch-delete', methods=['POST'])
@login_required
@admin_required
def batch_delete_rentals():
    """批量删除租房信息API
    
    接收JSON格式的ID列表，批量删除多条租房记录
    
    返回:
        JSON格式的批量删除结果
    """
    try:
        # 获取JSON数据
        data = request.json
        
        # 验证数据有效性
        if not data or 'ids' not in data or not data['ids']:
            return jsonify({'error': '没有提供要删除的ID列表'}), 400
        
        # 批量删除指定ID列表中的所有记录
        Rental.query.filter(Rental.id.in_(data['ids'])).delete(synchronize_session=False)
        db.session.commit()
        
        # 返回删除成功信息
        return jsonify({
            'message': f'成功删除 {len(data["ids"])} 条记录'
        })
        
    except Exception as e:
        # 出现异常时回滚事务
        db.session.rollback()
        current_app.logger.error(f"Error batch deleting rentals: {str(e)}")
        return jsonify({'error': str(e)}), 500


@main.route('/api/recommend', methods=['GET', 'POST'])
@login_required
def get_recommendations():
    """获取房源推荐的API
    
    基于用户选择的条件，使用机器学习算法推荐最合适的房源
    """
    try:
        # 根据请求方法获取参数
        if request.method == 'POST':
            data = request.json
            city = data.get('city', '')
            districts = data.get('districts', [])
            price_range = data.get('price_range', {})
            area_range = data.get('area_range', {})
            weights = data.get('weights', {})
            
            min_price = price_range.get('min', 0)
            max_price = price_range.get('max', 100000)
            min_area = area_range.get('min', 0)
            max_area = area_range.get('max', 1000)
            
            price_weight = weights.get('price', 5)
            area_weight = weights.get('area', 5)
            location_weight = weights.get('location', 5)
        else:
            city = request.args.get('city', '')
            districts = request.args.get('districts', '').split(',')
            min_price = request.args.get('min_price', 0, type=int)
            max_price = request.args.get('max_price', 100000, type=int)
            min_area = request.args.get('min_area', 0, type=float)
            max_area = request.args.get('max_area', 1000, type=float)
            
            price_weight = request.args.get('price_weight', 5, type=int)
            area_weight = request.args.get('area_weight', 5, type=int)
            location_weight = request.args.get('location_weight', 5, type=int)

        # 清理districts列表
        districts = [d.strip() for d in districts if d.strip()]
        
        # 计算权重
        weights = [price_weight, area_weight, location_weight]
        weights_sum = sum(weights)
        if weights_sum > 0:
            weights = [w / weights_sum for w in weights]
        else:
            weights = [1/3, 1/3, 1/3]
        
        # 构建查询条件
        query = Rental.query
        
        # 添加城市筛选
        if city:
            query = query.filter(Rental.city == city)
        
        # 添加区域筛选
        if districts:
            district_conditions = []
            for district in districts:
                district_conditions.append(Rental.location.like(f"{district}%"))
            if district_conditions:
                query = query.filter(db.or_(*district_conditions))
        
        # 获取所有符合条件的房源
        rentals = query.all()
        filtered_rentals = []
        seen_titles = set()  # 用于记录已经处理过的房源标题
        
        # 处理每个房源
        for rental in rentals:
            try:
                # 获取价格和面积的数值
                price = float(rental.price.replace('元/月', '').replace('元', '').strip()) if rental.price else None
                area = float(rental.area.replace('平米', '').replace('㎡', '').strip()) if rental.area else None
                
                # 验证价格和面积是否在范围内，并检查标题是否重复
                if (price is not None and area is not None and
                    price >= min_price and price <= max_price and
                    area >= min_area and area <= max_area and
                    rental.title not in seen_titles):
                    filtered_rentals.append(rental)
                    seen_titles.add(rental.title)
            except (ValueError, AttributeError) as e:
                current_app.logger.warning(f"处理房源数据时出错: {str(e)}, 房源ID: {rental.id}")
                continue
        
        if not filtered_rentals:
            return jsonify({
                'success': True,
                'recommendations': [],
                'message': '没有找到符合条件的房源'
            })
        
        # 计算评分
        rental_scores = []
        for rental in filtered_rentals:
            try:
                # 获取价格和面积的数值
                price = float(rental.price.replace('元/月', '').replace('元', '').strip())
                area = float(rental.area.replace('平米', '').replace('㎡', '').strip())
                
                # 计算价格评分（价格越低分数越高）
                price_score = 1 - (price - min_price) / (max_price - min_price) if max_price > min_price else 0.5
                
                # 计算面积评分（面积越大分数越高）
                area_score = (area - min_area) / (max_area - min_area) if max_area > min_area else 0.5
                
                # 计算位置评分
                location_score = 0.8  # 默认分数
                location = rental.location.lower() if rental.location else ''
                if '市中心' in location or '核心' in location:
                    location_score = 1.0
                elif '地铁' in location or '交通' in location:
                    location_score = 0.9
                elif '商圈' in location or '商业' in location:
                    location_score = 0.8
                elif '学校' in location or '大学' in location:
                    location_score = 0.7
                
                # 计算加权总分
                total_score = (
                    weights[0] * price_score +
                    weights[1] * area_score +
                    weights[2] * location_score
                )
                
                # 确定推荐理由
                reasons = []
                if price_score > 0.7:
                    reasons.append("价格合理")
                if area_score > 0.7:
                    reasons.append("面积适中")
                if location_score > 0.7:
                    reasons.append("位置优越")
                if not reasons:
                    reasons.append("综合评分较高")
                
                # 获取区域信息
                district = rental.location.split()[0] if rental.location else '未知区域'
                
                rental_scores.append({
                    'id': rental.id,
                    'title': rental.title,
                    'price': rental.price,
                    'area': rental.area,
                    'district': district,
                    'description': rental.description if hasattr(rental, 'description') else '',
                    'score': total_score,
                    'reasons': reasons
                })
            except (ValueError, AttributeError) as e:
                current_app.logger.warning(f"计算房源评分时出错: {str(e)}, 房源ID: {rental.id}")
                continue
        
        # 按评分排序，取前10个
        rental_scores.sort(key=lambda x: x['score'], reverse=True)
        top_recommendations = rental_scores[:10]
        
        return jsonify({
            'success': True,
            'recommendations': top_recommendations,
            'filters': {
                'city': city,
                'districts': districts,
                'price_range': {'min': min_price, 'max': max_price},
                'area_range': {'min': min_area, 'max': max_area},
                'weights': weights
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error generating recommendations: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '获取推荐失败，请稍后重试'
        }), 500


# ===============================================================
# 用户管理相关路由
# ===============================================================

@main.route('/user-management')
@login_required
@admin_required
def user_management():
    """用户管理页面
    
    显示所有用户列表，提供用户管理功能
    """
    try:
        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)
        
        # 获取搜索参数
        search_term = request.args.get('search', '')
        
        # 构建查询
        query = User.query
        
        # 如果有搜索条件，添加过滤器
        if search_term:
            search_pattern = f'%{search_term}%'
            query = query.filter(
                db.or_(
                    User.username.like(search_pattern),
                    User.email.like(search_pattern)
                )
            )
        
        # 分页
        users = query.order_by(User.id).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return render_template(
            'main/user_management.html',
            users=users,
            search_term=search_term
        )
    except Exception as e:
        current_app.logger.error(f"Error in user management: {str(e)}")
        return render_template(
            'main/user_management.html',
            error_message=f"加载用户列表失败: {str(e)}",
            users=None,
            search_term=""
        )


@main.route('/api/users/<int:user_id>', methods=['GET'])
@login_required
@admin_required
def get_user(user_id):
    """获取用户信息API
    
    参数:
        user_id: 用户ID
        
    返回:
        JSON格式的用户信息
    """
    try:
        user = User.query.get_or_404(user_id)
        return jsonify({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
@admin_required
def update_user(user_id):
    """更新用户信息API
    
    参数:
        user_id: 用户ID
        
    返回:
        JSON格式的更新结果
    """
    try:
        # 不允许修改自己的角色
        if user_id == current_user.id:
            return jsonify({'error': '不能修改自己的信息'}), 403
            
        user = User.query.get_or_404(user_id)
        data = request.json
        
        # 验证用户名唯一性
        if 'username' in data and data['username'] != user.username:
            if User.query.filter_by(username=data['username']).first():
                return jsonify({'error': '用户名已存在'}), 400
        
        # 验证邮箱唯一性
        if 'email' in data and data['email'] != user.email:
            if User.query.filter_by(email=data['email']).first():
                return jsonify({'error': '邮箱已存在'}), 400
        
        # 更新用户信息
        if 'username' in data:
            user.username = data['username']
        if 'email' in data:
            user.email = data['email']
        if 'role' in data:
            user.role = data['role']
        
        db.session.commit()
        return jsonify({'message': '更新成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@main.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    """删除用户API
    
    参数:
        user_id: 用户ID
        
    返回:
        JSON格式的删除结果
    """
    try:
        # 不允许删除自己
        if user_id == current_user.id:
            return jsonify({'error': '不能删除自己的账号'}), 403
            
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({'message': '删除成功'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@main.route('/price_prediction')
@login_required
def price_prediction():
    """价格预测页面"""
    try:
        # 获取原始数据
        sql = """
            SELECT 
                id,
                price,
                area,
                location,
                created_at
            FROM rentals
            WHERE price IS NOT NULL 
                AND area IS NOT NULL 
                AND location IS NOT NULL
                AND created_at IS NOT NULL
            ORDER BY created_at DESC
        """
        
        df = pd.read_sql(text(sql), db.engine)
        current_app.logger.info(f"从数据库获取到 {len(df)} 条记录")
        
        if len(df) < 2:
            flash('没有足够的历史数据来进行预测（至少需要3条数据）', 'warning')
            return render_template('main/price_prediction.html', 
                                historical_data={'dates': [], 'prices': []}, 
                                prediction_data={'dates': [], 'prices': []},
                                model_info=None)

        # 数据预处理
        df['price'] = pd.to_numeric(df['price'].str.replace('元/月', '').str.replace('元', ''), errors='coerce')
        df['area'] = pd.to_numeric(df['area'].str.replace('平米', '').str.replace('㎡', ''), errors='coerce')
        df = df.dropna(subset=['price', 'area'])
        
        if len(df) < 3:
            flash('数据预处理后没有足够的有效数据来进行预测', 'warning')
            return render_template('main/price_prediction.html',
                                historical_data={'dates': [], 'prices': []},
                                prediction_data={'dates': [], 'prices': []},
                                model_info=None)

        # 初始化预测器
        model_path = os.path.join(current_app.root_path, 'models', 'price_predictor_model')
        predictor = PricePredictor(model_path=model_path)
        
        # 尝试加载已有模型
        loaded = predictor.load_model()
        if not loaded:
            current_app.logger.info("开始训练新模型")
            success = predictor.train(df)
            if not success:
                flash('模型训练失败，请稍后再试', 'error')
                return render_template('main/price_prediction.html',
                                    historical_data={'dates': [], 'prices': []},
                                    prediction_data={'dates': [], 'prices': []},
                                    model_info=predictor.get_model_info())
        
        # 获取最新的模型信息
        model_info = predictor.get_model_info()
        current_app.logger.info(f"当前模型信息: {model_info}")
        
        # 准备历史数据
        historical_data = {
            'dates': df['created_at'].dt.strftime('%Y-%m-%d').tolist(),
            'prices': df['price'].tolist()
        }
        
        # 准备预测数据
        prediction_data = []
        
        # 对每个区域进行预测
        districts = df['location'].str.split().str[0].unique()
        for district in districts[:3]:  # 只预测前3个区域
            district_data = df[df['location'].str.startswith(district)]
            if not district_data.empty:
                avg_area = district_data['area'].mean()
                try:
                    # 预测未来3天的价格
                    dates = [(datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1, 4)]
                    predicted_price = predictor.predict(district, avg_area)
                    
                    prediction_data.append({
                        'district': district,
                        'dates': dates,
                        'prices': [predicted_price] * 3  # 使用相同的预测价格
                    })
                except Exception as e:
                    current_app.logger.error(f"预测失败: {str(e)}")
                    continue
        
        return render_template('main/price_prediction.html',
                            historical_data=historical_data,
                            prediction_data=prediction_data,
                            model_info=model_info)
                            
    except Exception as e:
        current_app.logger.error(f"价格预测发生错误: {str(e)}")
        flash('处理请求时发生错误，请稍后再试', 'error')
        return render_template('main/price_prediction.html',
                             historical_data={'dates': [], 'prices': []},
                             prediction_data=[],
                             model_info=None)


@main.route('/retrain_model', methods=['POST'])
@login_required
@admin_required
def retrain_model():
    """强制重新训练模型的路由"""
    try:
        # 获取原始数据
        sql = """
            SELECT 
                id,
                price,
                area,
                location,
                created_at,
                title
            FROM rentals
            WHERE price IS NOT NULL 
                AND area IS NOT NULL 
                AND location IS NOT NULL
                AND created_at IS NOT NULL
            ORDER BY created_at DESC
        """
        
        df = pd.read_sql(text(sql), db.engine)
        current_app.logger.info(f"从数据库获取到 {len(df)} 条记录用于重新训练")
        
        if len(df) < 2:
            return jsonify({
                'error': '没有足够的历史数据来进行训练（至少需要2条数据）'
            }), 400

        # 初始化预测器
        model_path = os.path.join(current_app.root_path, 'models', 'price_predictor_model')
        predictor = PricePredictor(model_path=model_path)
        
        # 强制重新训练
        training_result = predictor.train(df, force_retrain=True)
        
        if training_result:
            # 获取更新后的模型信息
            model_info = predictor.get_model_info()
            
            # 添加训练结果到模型信息中
            model_info.update({
                'train_score': training_result['train_score'],
                'cv_score_mean': training_result['cv_score_mean'],
                'test_score': training_result['test_score']
            })
            
            return jsonify({
                'success': True,
                'message': '模型重新训练成功！',
                'model_info': model_info
            })
        else:
            return jsonify({
                'error': '模型重新训练失败，请查看日志了解详情'
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"重新训练模型时发生错误: {str(e)}")
        return jsonify({
            'error': f'重新训练模型时发生错误: {str(e)}'
        }), 500


@main.route('/api/price_prediction')
@login_required
def get_price_prediction():
    """获取价格预测数据的API"""
    try:
        # 获取城市和区域参数
        city = request.args.get('city')
        district = request.args.get('district')
        
        if not city or not district:
            return jsonify({'error': '请指定城市和区域'}), 400
            
        # 获取原始数据
        sql = text("""
            SELECT 
                id,
                price,
                area,
                location,
                created_at
            FROM rentals
            WHERE city = :city
                AND location LIKE :district_pattern
                AND price IS NOT NULL 
                AND area IS NOT NULL 
                AND location IS NOT NULL
                AND created_at IS NOT NULL
            ORDER BY created_at DESC
        """)
        
        df = pd.read_sql(sql, db.engine, params={
            'city': city,
            'district_pattern': f"{district}%"
        })
        current_app.logger.info(f"从数据库获取到 {len(df)} 条记录")
        
        if len(df) < 2:
            return jsonify({'error': '没有足够的历史数据来进行预测（至少需要2条数据）'})

        # 数据预处理
        df['price'] = pd.to_numeric(df['price'].str.replace('元/月', '').str.replace('元', ''), errors='coerce')
        df['area'] = pd.to_numeric(df['area'].str.replace('平米', '').str.replace('㎡', ''), errors='coerce')
        df = df.dropna(subset=['price', 'area'])
        
        if len(df) < 2:
            return jsonify({'error': '数据预处理后没有足够的有效数据来进行预测'})

        # 初始化预测器
        model_path = os.path.join(current_app.root_path, 'models', 'price_predictor_model')
        predictor = PricePredictor(model_path=model_path)
        
        # 尝试加载已有模型
        loaded = predictor.load_model()
        if not loaded:
            current_app.logger.info("开始训练新模型")
            success = predictor.train(df)
            if not success:
                return jsonify({'error': '模型训练失败，请稍后再试'})
        
        # 获取最新的模型信息
        model_info = predictor.get_model_info()
        current_app.logger.info(f"当前模型信息: {model_info}")
        
        # 准备历史数据
        historical_data = {
            'dates': df['created_at'].dt.strftime('%Y-%m-%d').tolist(),
            'prices': df['price'].tolist()
        }
        
        # 准备预测数据
        prediction_data = []
        
        try:
            # 计算该区域的平均面积
            avg_area = df['area'].mean()
            
            # 预测未来3天的价格
            dates = [(datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1, 4)]
            predicted_price = predictor.predict(district, avg_area)
            
            prediction_data.append({
                'district': district,
                'dates': dates,
                'prices': [predicted_price] * 3  # 使用相同的预测价格
            })
        except Exception as e:
            current_app.logger.error(f"预测失败: {str(e)}")
            return jsonify({'error': f'预测失败: {str(e)}'}), 500
        
        return jsonify({
            'historical': historical_data,
            'prediction': prediction_data,
            'model_info': model_info
        })
                            
    except Exception as e:
        current_app.logger.error(f"价格预测发生错误: {str(e)}")
        return jsonify({'error': '处理请求时发生错误，请稍后再试'}), 500


@main.route('/api/cities')
@login_required
def get_cities():
    """获取所有城市列表的API"""
    try:
        sql = text("""
            SELECT DISTINCT city 
            FROM rentals 
            WHERE city IS NOT NULL 
            ORDER BY city
        """)
        cities = [row[0] for row in db.session.execute(sql)]
        return jsonify({'cities': cities})
    except Exception as e:
        current_app.logger.error(f"获取城市列表失败: {str(e)}")
        return jsonify({'error': '获取城市列表失败'}), 500


@main.route('/api/districts')
@login_required
def get_districts():
    """获取指定城市的所有区域列表的API"""
    try:
        city = request.args.get('city')
        if not city:
            return jsonify({'error': '请指定城市'}), 400
            
        sql = text("""
            SELECT DISTINCT SUBSTRING_INDEX(location, ' ', 1) as district
            FROM rentals
            WHERE city = :city
                AND location IS NOT NULL
            ORDER BY district
        """)
        districts = [row[0] for row in db.session.execute(sql, {'city': city})]
        return jsonify({'districts': districts})
    except Exception as e:
        current_app.logger.error(f"获取区域列表失败: {str(e)}")
        return jsonify({'error': '获取区域列表失败'}), 500


