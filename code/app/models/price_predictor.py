import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, LabelEncoder
from sklearn.neural_network import MLPRegressor
import joblib
import os
from datetime import datetime, timedelta
import logging
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import r2_score

class PricePredictor:
    def __init__(self, model_path='price_predictor_model'):
        self.model_path = model_path
        self.model = None
        self.scaler = MinMaxScaler()
        self.label_encoders = {}
        self.feature_columns = [
            'district_encoded',
            'area_normalized',
            'price_per_sqm_normalized',
            'subway_dist_normalized',
            'district_count_normalized',
            'is_master',
            'days_online_normalized',
            'is_new',
            'is_entire_rent'
        ]
        self.logger = logging.getLogger(__name__)
        self.district_encoder = LabelEncoder()
        self.area_scaler = MinMaxScaler()
        self.price_per_sqm_scaler = MinMaxScaler()
        self.subway_dist_scaler = MinMaxScaler()
        self.district_count_scaler = MinMaxScaler()
        self.days_online_scaler = MinMaxScaler()
        self.X_train = None
        self.y_train = None

    def _preprocess_data(self, df):
        """预处理数据"""
        try:
            # 复制数据，避免修改原始数据
            df = df.copy()
            
            # 确保必需的列存在
            required_columns = ['price', 'area', 'location']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"缺少必需的列: {', '.join(missing_columns)}")
            
            # 处理可选列
            if 'title' not in df.columns:
                df['title'] = ''  # 如果没有title列，添加空字符串
            
            if 'created_at' not in df.columns:
                df['created_at'] = pd.Timestamp.now()  # 如果没有created_at列，使用当前时间
            
            # 处理价格：确保是字符串类型，然后移除"元/月"和"元"，转换为数值
            df['price'] = df['price'].astype(str).str.replace('元/月', '').str.replace('元', '').astype(float)
            
            # 处理面积：确保是字符串类型，然后提取数字部分，转换为数值
            df['area'] = df['area'].astype(str).str.extract('(\d+(?:\.\d+)?)').astype(float)
            
            # 处理location：确保不为空
            df = df[df['location'].notna()]
            
            # 处理title：确保不为空，用空字符串填充
            df['title'] = df['title'].fillna('')
            
            # 处理created_at：确保是日期格式，无效日期用当前时间填充
            df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
            df['created_at'] = df['created_at'].fillna(pd.Timestamp.now())
            
            # 过滤异常值
            df = df[
                (df['price'] > 0) & 
                (df['price'] < 100000) &  # 设置合理的价格上限
                (df['area'] > 0) & 
                (df['area'] < 1000) &     # 设置合理的面积上限
                (df['price'] / df['area'] < 1000)  # 设置合理的单价上限
            ]
            
            # 确保没有空值
            df = df.dropna(subset=['price', 'area', 'location'])
            
            self.logger.info(f"预处理后的数据量: {len(df)}")
            return df
            
        except Exception as e:
            self.logger.error(f"数据预处理失败: {str(e)}")
            raise

    def _create_features(self, data, is_training=False):
        """创建特征"""
        try:
            # 确保数据是DataFrame
            if not isinstance(data, pd.DataFrame):
                data = pd.DataFrame(data)
            
            # 创建特征DataFrame
            features = pd.DataFrame()
            
            # 确保所有必需的列存在
            if is_training:
                required_columns = ['price', 'area', 'location']
            else:
                required_columns = ['area', 'location']  # 预测时不需要price列
                
            missing_columns = [col for col in required_columns if col not in data.columns]
            if missing_columns:
                raise ValueError(f"缺少必需的列: {', '.join(missing_columns)}")
            
            # 添加可选列（如果不存在）
            if 'title' not in data.columns:
                data['title'] = ''
            
            if 'created_at' not in data.columns:
                data['created_at'] = pd.Timestamp.now()
            
            # 1. 地理位置特征
            # 1.1 地区编码
            districts = data['location'].str.split().str[0]
            districts = districts.fillna('未知')  # 处理可能的空值
            
            # 初始化district_encoded为-1（用于未知地区）
            features['district_encoded'] = pd.Series([-1] * len(data), index=data.index)
            
            if is_training:
                features['district_encoded'] = self.district_encoder.fit_transform(districts)
            else:
                try:
                    features['district_encoded'] = self.district_encoder.transform(districts)
                except ValueError as e:
                    self.logger.warning(f"地区编码转换失败，使用默认值-1: {str(e)}")
                    # 保持默认值-1
            
            # 1.2 地铁距离
            subway_dist = data['location'].str.extract('距[\d\w号线-]+(\d+)m').astype(float)
            # 使用中位数填充缺失值
            median_dist = subway_dist.iloc[:, 0].median() if not subway_dist.empty else 1000
            subway_dist = subway_dist.fillna(median_dist)
            
            if is_training:
                features['subway_dist_normalized'] = self.subway_dist_scaler.fit_transform(subway_dist)
            else:
                features['subway_dist_normalized'] = self.subway_dist_scaler.transform(subway_dist)
            
            # 1.3 商圈热度
            district_count = districts.groupby(districts).transform('count')
            district_count = district_count.values.reshape(-1, 1)
            
            if is_training:
                features['district_count_normalized'] = self.district_count_scaler.fit_transform(district_count)
            else:
                features['district_count_normalized'] = self.district_count_scaler.transform(district_count)
            
            # 2. 房屋基础特征
            # 2.1 面积标准化
            area_values = data['area'].values.reshape(-1, 1)
            if is_training:
                features['area_normalized'] = self.area_scaler.fit_transform(area_values)
            else:
                features['area_normalized'] = self.area_scaler.transform(area_values)
            
            # 单价特征（仅在训练时计算）
            if is_training:
                price_per_sqm = (data['price'] / data['area']).values.reshape(-1, 1)
                price_per_sqm = np.nan_to_num(price_per_sqm, nan=0.0, posinf=0.0, neginf=0.0)  # 处理无效值
                features['price_per_sqm_normalized'] = self.price_per_sqm_scaler.fit_transform(price_per_sqm)
            else:
                # 预测时，使用面积的缩放值作为占位符
                features['price_per_sqm_normalized'] = features['area_normalized'].copy()
            
            # 2.2 房间类型和主卧特征
            features['is_entire_rent'] = data['title'].str.contains('整租', na=False, regex=False).astype(int)
            features['is_master'] = data['title'].str.contains('主卧', na=False, regex=False).astype(int)
            
            # 3. 时间特征
            # 3.1 房源新鲜度
            current_time = pd.Timestamp.now()
            days_online = (current_time - pd.to_datetime(data['created_at'])).dt.total_seconds() / (24 * 3600)
            days_online = days_online.fillna(0)
            days_online = days_online.values.reshape(-1, 1)
            
            if is_training:
                features['days_online_normalized'] = self.days_online_scaler.fit_transform(days_online)
            else:
                features['days_online_normalized'] = self.days_online_scaler.transform(days_online)
            
            # 3.2 是否新上
            features['is_new'] = (days_online <= 7).astype(int)
            
            # 确保所有必需的特征都存在，对缺失的特征填充0
            for feature in self.feature_columns:
                if feature not in features.columns:
                    features[feature] = 0
            
            # 确保特征列的顺序与定义一致
            features = features[self.feature_columns]
            
            # 最后检查确保没有NaN值
            features = features.fillna(0)
            
            return features
            
        except Exception as e:
            self.logger.error(f"特征创建失败: {str(e)}")
            raise

    def train(self, data, force_retrain=False):
        """训练模型并进行评估"""
        try:
            # 如果强制重新训练，删除现有模型文件
            if force_retrain and os.path.exists(self.model_path):
                self.logger.info("强制重新训练：删除现有模型文件")
                try:
                    for file in os.listdir(self.model_path):
                        file_path = os.path.join(self.model_path, file)
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    os.rmdir(self.model_path)
                except Exception as e:
                    self.logger.error(f"删除模型文件时出错: {str(e)}")

            self.logger.info("开始训练模型...")
            
            # 准备训练数据
            df = self._preprocess_data(data)
            
            # 划分数据集
            train_df, test_df = train_test_split(df, test_size=0.2, random_state=42)
            
            # 创建训练特征
            features_train_df = self._create_features(train_df, is_training=True)
            
            # 准备特征和目标变量
            X_train = features_train_df.values
            y_train = train_df['price'].values
            
            # 保存训练数据
            self.X_train = X_train
            self.y_train = y_train
            
            # 训练多层感知机模型
            self.model = MLPRegressor(
                hidden_layer_sizes=(100, 50),  # 两个隐藏层，分别有100和50个神经元
                activation='relu',             # 使用ReLU激活函数
                solver='adam',                 # 使用Adam优化器
                max_iter=500,                 # 最大迭代次数
                batch_size='auto',          # 设置自动切片cpu加速
                early_stopping=True,          # 自动早停
                alpha=0.0001,                 # 正则化参数
                learning_rate='adaptive',      # 自适应学习率
                random_state=42,
                verbose=True                   # 显示训练进度
            )
            
            # 使用numpy数组进行训练
            self.model.fit(X_train, y_train)
            
            # 交叉验证
            cv_scores = cross_val_score(self.model, X_train, y_train, cv=5, scoring='r2')
            self.logger.info(f"交叉验证R²分数: {cv_scores}")
            self.logger.info(f"交叉验证平均R²分数: {cv_scores.mean():.4f}")
            
            # 在测试集上评估模型
            features_test_df = self._create_features(test_df, is_training=False)
            X_test = features_test_df.values
            y_test = test_df['price'].values
            y_pred = self.model.predict(X_test)
            test_score = r2_score(y_test, y_pred)
            self.logger.info(f"测试集R²分数: {test_score:.4f}")
            
            # 创建模型保存目录
            os.makedirs(self.model_path, exist_ok=True)
            
            # 保存模型和相关组件
            joblib.dump(self.model, os.path.join(self.model_path, 'model.joblib'))
            joblib.dump(self.area_scaler, os.path.join(self.model_path, 'area_scaler.joblib'))
            joblib.dump(self.price_per_sqm_scaler, os.path.join(self.model_path, 'price_per_sqm_scaler.joblib'))
            joblib.dump(self.subway_dist_scaler, os.path.join(self.model_path, 'subway_dist_scaler.joblib'))
            joblib.dump(self.district_count_scaler, os.path.join(self.model_path, 'district_count_scaler.joblib'))
            joblib.dump(self.days_online_scaler, os.path.join(self.model_path, 'days_online_scaler.joblib'))
            joblib.dump(self.district_encoder, os.path.join(self.model_path, 'district_encoder.joblib'))
            
            # 保存训练数据
            train_data = {
                'X_train': self.X_train,
                'y_train': self.y_train
            }
            joblib.dump(train_data, os.path.join(self.model_path, 'train_data.joblib'))
            
            self.logger.info("模型和相关信息保存成功")
            
            return {
                'train_score': self.model.score(X_train, y_train),
                'cv_score_mean': cv_scores.mean(),
                'test_score': test_score
            }
        except Exception as e:
            self.logger.error(f"模型训练失败: {str(e)}")
            return None

    def load_model(self):
        """加载模型和相关组件"""
        try:
            # 定义所需文件
            required_files = {
                'model.joblib': '模型文件',
                'area_scaler.joblib': '面积标准化器',
                'price_per_sqm_scaler.joblib': '单价标准化器',
                'subway_dist_scaler.joblib': '地铁距离标准化器',
                'district_count_scaler.joblib': '商圈热度标准化器',
                'days_online_scaler.joblib': '在线天数标准化器',
                'district_encoder.joblib': '地区编码器',
                'train_data.joblib': '训练数据'
            }
            
            # 检查所有必需文件是否存在
            for filename, description in required_files.items():
                file_path = os.path.join(self.model_path, filename)
                if not os.path.exists(file_path):
                    self.logger.info(f"缺少{description}，需要重新训练")
                    return False
            
            # 加载模型
            model_file = os.path.join(self.model_path, 'model.joblib')
            loaded_model = joblib.load(model_file)
            if not isinstance(loaded_model, MLPRegressor):
                self.logger.info("现有模型不是MLPRegressor类型，需要重新训练")
                return False
            
            self.model = loaded_model
            
            # 加载所有标准化器
            self.area_scaler = joblib.load(os.path.join(self.model_path, 'area_scaler.joblib'))
            self.price_per_sqm_scaler = joblib.load(os.path.join(self.model_path, 'price_per_sqm_scaler.joblib'))
            self.subway_dist_scaler = joblib.load(os.path.join(self.model_path, 'subway_dist_scaler.joblib'))
            self.district_count_scaler = joblib.load(os.path.join(self.model_path, 'district_count_scaler.joblib'))
            self.days_online_scaler = joblib.load(os.path.join(self.model_path, 'days_online_scaler.joblib'))
            
            # 加载地区编码器
            self.district_encoder = joblib.load(os.path.join(self.model_path, 'district_encoder.joblib'))
            
            # 加载训练数据
            train_data = joblib.load(os.path.join(self.model_path, 'train_data.joblib'))
            self.X_train = train_data['X_train']
            self.y_train = train_data['y_train']
            
            self.logger.info("模型和相关信息加载成功")
            return True
        except Exception as e:
            self.logger.error(f"加载模型失败: {str(e)}")
            return False

    def predict(self, district, area):
        """预测价格"""
        try:
            # 准备预测数据
            data = pd.DataFrame({
                'location': [district],
                'area': [area]
            })
            
            # 创建特征
            features = self._create_features(data)
            
            # 转换为numpy数组进行预测
            features_array = features.values
            
            # 预测
            predicted_price = self.model.predict(features_array)[0]
            
            return float(predicted_price)
            
        except Exception as e:
            self.logger.error(f"预测失败: {str(e)}")
            raise

    def get_model_info(self):
        """获取模型信息"""
        try:
            if self.model is None:
                return {
                    'status': '未训练',
                    'model_type': '多层感知机回归器',
                    'feature_count': len(self.feature_columns),
                    'model_score': None,
                    'feature_importance': None
                }

            # 计算特征重要性
            feature_importance = []
            feature_names_zh = {
                'district_encoded': '地区编码',
                'area_normalized': '标准化面积',
                'price_per_sqm_normalized': '单价标准化',
                'subway_dist_normalized': '地铁距离标准化',
                'district_count_normalized': '商圈热度标准化',
                'days_online_normalized': '在线天数标准化',
                'is_master': '主卧',
                'is_entire_rent': '整租',
                'is_new': '新上'
            }

            # 根据模型类型计算特征重要性
            if isinstance(self.model, MLPRegressor):
                # 获取第一层的权重
                weights = self.model.coefs_[0]
                # 计算每个输入特征的重要性
                importance_scores = np.abs(weights).sum(axis=1)
                # 归一化重要性分数
                importance_scores = importance_scores / importance_scores.sum()
            else:
                # 对于其他类型的模型，使用默认的特征重要性
                importance_scores = np.ones(len(self.feature_columns)) / len(self.feature_columns)

            for feature, importance in zip(self.feature_columns, importance_scores):
                feature_importance.append({
                    'feature': feature_names_zh.get(feature, feature),
                    'importance': float(importance)
                })
            feature_importance.sort(key=lambda x: x['importance'], reverse=True)

            # 计算模型得分（使用训练数据的R²分数）
            if hasattr(self.model, 'score'):
                model_score = float(self.model.score(self.X_train, self.y_train))
            else:
                model_score = None

            return {
                'status': '已训练',
                'model_type': '深度学习模型MLP' if isinstance(self.model, MLPRegressor) else '其他回归器',
                'feature_count': len(self.feature_columns),
                'model_score': model_score,
                'feature_importance': feature_importance
            }
        except Exception as e:
            self.logger.error(f"获取模型信息时发生错误: {str(e)}")
            return {
                'status': '已训练',
                'model_type': '深度学习模型MLP',
                'feature_count': len(self.feature_columns),
                'model_score': None,
                'feature_importance': None
            }