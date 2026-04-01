from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    regexp_extract,
    col,
    split,
    monotonically_increasing_id,
    when,
    regexp_replace,
    trim,
    upper,
    lower,
    length,
    isnull,
    coalesce,
    count
)
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    DoubleType
)
from typing import Tuple, Dict, Any
import logging
from dataclasses import dataclass
from pathlib import Path
import mysql.connector
from mysql.connector import Error
import pandas as pd
from sqlalchemy import create_engine

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class DBConfig:
    """数据库配置类"""
    host: str = '127.0.0.1'
    port: int = 11336
    database: str = 'cqzf'
    user: str = 'root'
    password: str = '123456'
    charset: str = 'utf8mb4'


@dataclass
class DataConfig:
    """数据配置类"""
    input_table: str = 'rentals_listings'  # 原始数据表名
    output_table: str = 'rentals'  # 清洗后数据表名
    batch_size: int = 1000  # 批处理大小


@dataclass
class CleaningConfig:
    """清洗配置类"""
    min_price: int = 0
    min_area: float = 0
    min_district_length: int = 0


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, db_config: DBConfig):
        self.db_config = db_config
        self.engine = self._create_engine()

    def _create_engine(self):
        """创建数据库引擎"""
        connection_str = (
            f"mysql+mysqlconnector://{self.db_config.user}:{self.db_config.password}"
            f"@{self.db_config.host}:{self.db_config.port}/{self.db_config.database}"
        )
        return create_engine(connection_str)

    def read_data(self, table_name: str) -> pd.DataFrame:
        """从数据库读取数据"""
        try:
            query = f"SELECT * FROM {table_name}"
            return pd.read_sql(query, self.engine)
        except Error as e:
            logger.error(f"读取数据失败: {str(e)}")
            raise

    def write_data(self, df: pd.DataFrame, table_name: str) -> None:
        """将数据写入数据库"""
        try:
            df.to_sql(
                table_name,
                self.engine,
                if_exists='replace',
                index=False,
                chunksize=self.db_config.batch_size
            )
        except Error as e:
            logger.error(f"写入数据失败: {str(e)}")
            raise


class SparkSessionManager:
    """SparkSession管理器"""

    @staticmethod
    def create_session(app_name: str = "Rental Data Cleaning") -> SparkSession:
        """创建SparkSession实例"""
        return SparkSession.builder \
            .appName(app_name) \
            .config("spark.sql.legacy.timeParserPolicy", "LEGACY") \
            .getOrCreate()


class SchemaManager:
    """Schema管理器"""

    @staticmethod
    def get_rental_schema() -> StructType:
        """获取租房数据schema"""
        return StructType([
            StructField("city", StringType(), True),  # 城市
            StructField("title", StringType(), True),  # 房源标题
            StructField("price", StringType(), True),  # 价格
            StructField("area_room", StringType(), True),  # 面积和房间信息
            StructField("location", StringType(), True),  # 位置信息
            StructField("url", StringType(), True),  # 房源链接
            StructField("img_url", StringType(), True),  # 图片链接
            StructField("agent_name", StringType(), True),  # 经纪人姓名
            StructField("agent_company", StringType(), True)  # 经纪公司
        ])


class DataCleaner:
    """数据清洗器"""

    def __init__(self, db_config: DBConfig, data_config: DataConfig, cleaning_config: CleaningConfig):
        self.db_config = db_config
        self.data_config = data_config
        self.cleaning_config = cleaning_config
        self.spark = SparkSessionManager.create_session()
        self.db_manager = DatabaseManager(db_config)

    def read_data(self) -> Any:
        """从数据库读取数据"""
        # 从数据库读取数据到pandas DataFrame
        pdf = self.db_manager.read_data(self.data_config.input_table)
        # 转换为Spark DataFrame
        return self.spark.createDataFrame(pdf)

    def clean_price(self, df: Any) -> Any:
        """清洗价格字段"""
        return df.withColumn(
            "price",
            when(
                regexp_extract(col("price"), r"(\d+)元/月", 1) != "",
                regexp_extract(col("price"), r"(\d+)元/月", 1)
            ).otherwise(
                regexp_extract(col("price"), r"(\d+)元", 1)
            ).cast(IntegerType())
        )

    def clean_area(self, df: Any) -> Any:
        """清洗面积字段"""
        return df.withColumn(
            "area",
            when(
                regexp_extract(col("area_room"), r"(\d+)㎡", 1) != "",
                regexp_extract(col("area_room"), r"(\d+)㎡", 1)
            ).otherwise(
                regexp_extract(col("area_room"), r"(\d+)平米", 1)
            ).cast(DoubleType())
        )

    def clean_district(self, df: Any) -> Any:
        """清洗区域字段"""
        return df.withColumn(
            "district",
            trim(split(col("location"), " ").getItem(0))
        )

    def clean_text_fields(self, df: Any) -> Any:
        """清洗文本字段"""
        text_columns = ["city", "title", "location", "url", "img_url", "agent_name", "agent_company"]
        for column in text_columns:
            df = df.withColumn(
                column,
                when(length(trim(col(column))) > 0, trim(col(column))).otherwise(None)
            )
        return df.withColumn("city", upper(col("city")))

    def filter_data(self, df: Any) -> Any:
        """过滤数据"""
        return df.filter(
            (col("price").isNotNull()) &
            (col("price") > self.cleaning_config.min_price) &
            (col("area").isNotNull()) &
            (col("area") > self.cleaning_config.min_area) &
            (col("district").isNotNull()) &
            (length(col("district")) > self.cleaning_config.min_district_length)
        )

    def add_id(self, df: Any) -> Any:
        """添加ID字段"""
        return df.withColumn("id", monotonically_increasing_id() + 1)

    def select_columns(self, df: Any) -> Any:
        """选择需要的列"""
        return df.select(
            "id", "city", "title", "price", "area", "district",
            "location", "url", "img_url", "agent_name", "agent_company"
        )

    def check_data_quality(self, df: Any) -> None:
        """检查数据质量"""
        total_count = df.count()
        null_counts = df.select([
            count(when(isnull(c), c)).alias(c)
            for c in df.columns
        ])

        logger.info(f"清洗后的数据总量: {total_count}")
        logger.info("各字段空值数量:")
        null_counts.show()

    def save_data(self, df: Any) -> None:
        """保存数据到数据库"""
        # 转换为pandas DataFrame
        pdf = df.toPandas()
        # 写入数据库
        self.db_manager.write_data(pdf, self.data_config.output_table)

    def clean(self) -> Tuple[bool, str]:
        """执行数据清洗流程"""
        try:
            # 读取数据
            df = self.read_data()

            # 执行清洗步骤
            df = self.clean_price(df)
            df = self.clean_area(df)
            df = self.clean_district(df)
            df = self.clean_text_fields(df)
            df = self.filter_data(df)
            df = self.add_id(df)
            df = self.select_columns(df)

            # 检查数据质量
            self.check_data_quality(df)

            # 保存数据
            self.save_data(df)

            return True, f"成功清洗 {df.count()} 条数据"

        except Exception as e:
            logger.error(f"数据清洗失败: {str(e)}")
            return False, f"数据清洗失败: {str(e)}"
        finally:
            self.spark.stop()


def main():
    """主函数"""
    # 数据库配置
    db_config = DBConfig(
        host='localhost',
        port=3306,
        database='cqzf',
        user='root',
        password='123456'
    )

    # 数据配置
    data_config = DataConfig(
        input_table='raw_rentals',
        output_table='cleaned_rentals',
        batch_size=1000
    )

    # 清洗配置
    cleaning_config = CleaningConfig(
        min_price=0,
        min_area=0,
        min_district_length=0
    )

    # 创建清洗器并执行清洗
    cleaner = DataCleaner(db_config, data_config, cleaning_config)
    success, message = cleaner.clean()
    logger.info(message)


if __name__ == "__main__":
    main()




#
# import pandas as pd
# import re
# from sqlalchemy import create_engine
#
# # 创建数据库连接（以PostgreSQL为例）
# # 你可以根据需要替换为相应数据库的连接字符串
# engine = create_engine(f'mysql+mysqlconnector://root:123456@127.0.0.1:11336/cqzf')
#
# # 从数据库读取数据
# query = "SELECT * FROM rentals_listings;"  # 替换为实际的查询
# df = pd.read_sql(query, engine)
#
# # 数据清洗
# def clean_data(row):
#     # 清洗价格字段，提取数字
#     price_match = re.search(r"(\d+)元/月", row['price'])
#     row['price'] = price_match.group(1) if price_match else None
#
#     # 清洗面积字段，提取数字
#     area_match = re.search(r"(\d+)㎡", row['area'])
#     row['area'] = area_match.group(1) if area_match else None
#
#     # 提取区县信息
#     location_parts = row['location'].split(" ")
#     row['district'] = location_parts[0] if location_parts else None
#
#     return row
#
# # 应用数据清洗函数
# df = df.apply(clean_data, axis=1)
#
# # 将价格和面积转换为数值类型
# df['price'] = pd.to_numeric(df['price'], errors='coerce')
# df['area'] = pd.to_numeric(df['area'], errors='coerce')
#
# # 移除价格为0或空的记录
# print(f"原始数据条数: {len(df)}")
# invalid_price = df['price'].isin([0]) | df['price'].isna()
# print(f"价格为0或空的记录数: {invalid_price.sum()}")
#
# # 移除面积为0或空的记录
# invalid_area = df['area'].isin([0]) | df['area'].isna()
# print(f"面积为0或空的记录数: {invalid_area.sum()}")
#
# # 移除无效记录
# df = df[~(invalid_price | invalid_area)]
# print(f"清洗后数据条数: {len(df)}")
#
# # 选择需要的列
# cleaned_df = df[[
#     'city','title', 'price', 'area', 'location', 'url', 'img_url',
#     'agent_name', 'agent_company','created_at'
# ]]
#
# # 将清洗后的数据保存回数据库
#
# cleaned_df.to_sql('rentals', engine, index=False, if_exists='append')  # 替换为目标表名
#
# # 关闭数据库连接
# engine.dispose()