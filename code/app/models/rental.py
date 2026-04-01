from .. import db
from datetime import datetime
import re

class Rental(db.Model):
    """租房信息模型"""
    __tablename__ = 'rentals'
    
    # 定义字段映射
    id = db.Column('id', db.Integer, primary_key=True)
    city = db.Column('city', db.String(50), nullable=False)
    title = db.Column('title', db.Text, nullable=False)
    price = db.Column('price', db.String(50), nullable=False)
    area = db.Column('area', db.String(100))
    location = db.Column('location', db.String(255))
    source_url = db.Column('url', db.Text, nullable=False)  # 注意这里映射到 url 字段
    img_url = db.Column('img_url', db.Text)
    agent_name = db.Column('agent_name', db.String(100))
    agent_company = db.Column('agent_company', db.String(255))
    created_at = db.Column('created_at', db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Rental {self.title}>'
    
    @property
    def price_value(self):
        """提取价格数值"""
        try:
            7
        except:
            return 0
    
    @property
    def area_value(self):
        """提取面积数值"""
        try:
            return float(re.search(r'\d+(\.\d+)?', self.area).group())
        except:
            return 0.0
    
    @property
    def district(self):
        """提取区域信息"""
        try:
            return self.location.split()[0]
        except:
            return ''
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'city': self.city,
            'title': self.title,
            'price': self.price,
            'price_value': self.price_value,
            'area': self.area,
            'area_value': self.area_value,
            'location': self.location,
            'district': self.district,
            'url': self.source_url,
            'img_url': self.img_url,
            'agent_name': self.agent_name,
            'agent_company': self.agent_company,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    @staticmethod
    def get_statistics():
        """获取统计信息"""
        try:
            rentals = Rental.query.all()
            if not rentals:
                return None
            
            prices = [r.price_value for r in rentals if r.price_value > 0]
            areas = [r.area_value for r in rentals if r.area_value > 0]
            districts = set(r.district for r in rentals if r.district)
            cities = set(r.city for r in rentals if r.city)  # 添加城市统计
            
            return {
                'total_listings': len(rentals),
                'avg_price': round(sum(prices) / len(prices), 2) if prices else 0,
                'avg_area': round(sum(areas) / len(areas), 2) if areas else 0,
                'districts': len(districts),
                'cities': list(cities),  # 添加城市列表
                'price_range': {
                    'min': min(prices) if prices else 0,
                    'max': max(prices) if prices else 0
                },
                'area_range': {
                    'min': min(areas) if areas else 0,
                    'max': max(areas) if areas else 0
                }
            }
        except Exception as e:
            db.session.rollback()
            return None 