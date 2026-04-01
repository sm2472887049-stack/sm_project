import time
import random
import pandas as pd  # 引入pandas库
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 设置Chrome的无界面模式
chrome_options = Options()
chrome_options.add_argument("--headless")  # 启用无头模式
chrome_options.add_argument("--disable-gpu")  # 禁用GPU加速
chrome_options.add_argument("--no-sandbox")  # 解决DevToolsActivePort文件不存在的错误

# 使用固定的 User-Agent
chrome_options.add_argument(
    "User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36")

# 设置Chrome浏览器路径
service = Service('C:/Program Files/Google/Chrome/Application/chromedriver.exe')  # 请替换为你安装的chromedriver路径

# 启动浏览器
driver = webdriver.Chrome(service=service, options=chrome_options)


# 保存数据到CSV文件
def save_data_to_csv(house_data, filename='./data/input/cq.csv'):
    # 将爬取的房源数据保存为CSV文件
    try:
        df = pd.DataFrame(house_data)
        df.to_csv(filename, index=False, encoding='utf-8')  # 保存为CSV文件，不保存行索引
        print(f"成功保存 {len(house_data)} 条数据到 {filename}")
    except Exception as e:
        print(f"保存数据到CSV文件失败: {e}")


# 爬取58同城租房数据
def crawl_58_dynamic(city_code='sz', start_page=1, end_page=3):
    base_url = f'https://{city_code}.58.com/chuzu/pn{{}}'  # 58同城分页URL模板, 动态获取城市代码
    house_data = []

    # 获取城市名称（通过城市代码推测）
    city_name_dict = {
        'sz': '深圳',
        'sh': '上海',
        'bj': '北京',
        'wh': '武汉',
        'cd': '成都',
        'su': '苏州',
        'gz': '广州',
        'tj': '天津',
        'xa': '西安',
        'cq': '重庆'
    }

    city_name = city_name_dict.get(city_code, '未知城市')  # 默认值为'未知城市'，如果没找到则返回此值

    for page in range(start_page, end_page + 1):  # 根据用户输入的页码范围爬取
        url = base_url.format(page)
        driver.get(url)

        # 随机延迟，防止反爬虫
        time.sleep(random.uniform(3, 6))  # 增加随机等待时间，防止反爬虫

        # 打印页面源码以调试
        print(f"正在爬取第 {page} 页...")

        # 模拟滚动到页面底部以加载更多数据
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(3, 6))  # 随机时间等待加载完成

        # 等待房源列表元素加载
        try:
            listings = WebDriverWait(driver, 20).until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, 'house-cell'))
            )
            print(f"成功加载第 {page} 页房源数据")
        except Exception as e:
            print(f"第 {page} 页加载失败，错误信息: {e}")
            continue  # 跳过当前页，继续下一页

        # 获取每一条房源数据
        for listing in listings:
            try:
                title = listing.find_element(By.TAG_NAME, 'h2').text.strip()  # 提取标题
            except Exception as e:
                print(f"未找到标题，错误: {e}")
                title = '无标题'

            try:
                price = listing.find_element(By.CLASS_NAME, 'money').text.strip()  # 提取价格
            except Exception as e:
                print(f"未找到价格，错误: {e}")
                price = '无价格'

            try:
                area_room = listing.find_element(By.CLASS_NAME, 'room').text.strip()  # 提取面积和房间数
            except Exception as e:
                print(f"未找到面积或房间数，错误: {e}")
                area_room = '未知面积'

            try:
                location = listing.find_element(By.CLASS_NAME, 'infor').text.strip()  # 提取位置
            except Exception as e:
                print(f"未找到位置，错误: {e}")
                location = '未知位置'

            try:
                url = listing.find_element(By.TAG_NAME, 'a').get_attribute('href')  # 提取房源链接
            except Exception as e:
                print(f"未找到链接，错误: {e}")
                url = '无链接'

            # 获取房源图片链接
            try:
                img_url = listing.find_element(By.TAG_NAME, 'img').get_attribute('src')  # 提取图片链接
            except Exception as e:
                print(f"未找到图片链接，错误: {e}")
                img_url = '无图片'

            # 获取经纪人信息
            try:
                agent_name = listing.find_element(By.CLASS_NAME, 'listjjr').text.strip()  # 经纪人姓名
            except Exception as e:
                print(f"未找到经纪人姓名，错误: {e}")
                agent_name = '无经纪人'

            try:
                agent_company = listing.find_element(By.CLASS_NAME, 'jjr_par_dp').text.strip()  # 经纪公司
            except Exception as e:
                print(f"未找到经纪公司，错误: {e}")
                agent_company = '无经纪公司'

            house_data.append({
                'city': city_name,  # 添加城市字段
                'title': title,  # 房源标题
                'price': price,  # 房源价格
                'area_room': area_room,  # 房源面积和房间数
                'location': location,  # 房源位置
                'url': url,  # 房源链接
                'img_url': img_url,  # 房源图片链接
                'agent_name': agent_name,  # 经纪人姓名
                'agent_company': agent_company  # 经纪公司
            })

    # 将数据保存为CSV文件
    save_data_to_csv(house_data)

    # 输出爬取的数据
    for house in house_data:
        print(house)


# 设置城市代码、起始页和结束页并调用爬取函数
city_code = input("请输入城市代码 (例如：sz, sh, bj): ")
start_page = int(input("请输入爬取的起始页数: "))
end_page = int(input("请输入爬取的结束页数: "))
crawl_58_dynamic(city_code, start_page, end_page)

# 关闭浏览器
driver.quit()
