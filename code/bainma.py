import requests
import pandas as pd
import mysql.connector
import json

# 百度API密钥
BAIDU_API_KEY = 'c2DAbj9olsVQRHs8wNbwCE4k9dTvujiZ'  # API密钥

# 连接到 MySQL 数据库
connection = mysql.connector.connect(
    host="localhost",  # 数据库主机
    user="root",  # 数据库用户名
    port="11336",  # 数据库端口
    password="123456",  # 数据库密码
    database="cqzf"  # 数据库名称
)

# 创建数据库游标
cursor = connection.cursor()

# SQL 查询：只提取地址字段
limit = 5000
cursor.execute(f"SELECT location FROM rentals ORDER BY RAND() LIMIT {limit}")
addresses = cursor.fetchall()


# 关闭数据库连接
cursor.close()
connection.close()


# 获取经纬度数据
def get_geocode_baidu(address):
    """使用百度地图API获取中文地址的经纬度"""
    geocode_url = "https://api.map.baidu.com/geocoding/v3/"
    try:
        url = f"{geocode_url}?address={address}&output=json&ak={BAIDU_API_KEY}"
        response = requests.get(url)
        result = response.json()

        if result['status'] == 0:  # 请求成功
            location = result['result']['location']
            return {'lat': location['lat'], 'lng': location['lng']}
        else:
            return None
    except Exception as e:
        print(f"Error getting geocode for {address}: {str(e)}")
        return None


# 用于存储经纬度数据的列表
geocoded_data = []

# 获取每个地址的经纬度
for address in addresses:
    location = address[0]  # 地址字段
    geocode = get_geocode_baidu(location)  # 获取经纬度
    if geocode:
        geocoded_data.append({
            'location': location,
            'latitude': geocode['lat'],
            'longitude': geocode['lng']
        })
    else:
        geocoded_data.append({
            'location': location,
            'latitude': None,
            'longitude': None
        })

# 将经纬度数据保存为 JSON 文件
with open('./data/locations_with_coordinates_1.json', 'w', encoding='utf-8') as json_file:
    json.dump(geocoded_data, json_file, ensure_ascii=False, indent=4)

print("JSON 文件已保存：locations_with_coordinates_1.json")

# 将数据保存为 CSV 文件
df = pd.DataFrame(geocoded_data)
df.to_csv('./data/locations_with_coordinates_1.csv', index=False, encoding='utf-8')
print("CSV 文件已保存：locations_with_coordinates_1.csv")
