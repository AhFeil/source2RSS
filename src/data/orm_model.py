from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import declarative_base, declared_attr

from config_handle import config
from src.scraper import ArticleDict, SrcMetaDict

Base = declarative_base()

class SourceMeta4ORM(Base):
    __tablename__ = config.source_meta

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    link = Column(String)
    desc = Column(String)
    lang = Column(String)
    tags = Column(String)
    key4sort = Column(String(30), nullable=False)
    access = Column(Integer)
    table_name = Column(String, unique=True, nullable=False, index=True)   # 作为文章表的名称

    def __repr__(self):
        return f"<SourceMeta({self.id=}, {self.name=}, ={self.link=}, {self.desc=}, {self.lang=}, {self.tags=}, {self.key4sort=}, {self.access=}, {self.table_name=})>"  # noqa: E501

    def equal_to(self, other_source_meta: SrcMetaDict) -> bool:
        # 如果缺少键，运行时不会报错 KeyError ，而是会卡死
        return all(getattr(self, column.name) == other_source_meta[column.name] for column in self.__table__.columns if not column.primary_key)

    def update_from(self, other_source_meta: SrcMetaDict):
        for column in self.__table__.columns:
            if column.primary_key:
                continue
            setattr(self, column.name, other_source_meta[column.name])

    def export_to_dict(self) -> SrcMetaDict:
        source_info = {}
        for column in self.__table__.columns:
            if column.primary_key:
                continue
            source_info[column.name] = getattr(self, column.name)
        return source_info # type: ignore


article_models: dict[str, type] = {}

class ArticleBase:
    """动态文章表的基类"""
    t_id = Column(Integer, primary_key=True)
    id = Column(Integer)
    title = Column(String)
    summary = Column(String)
    link = Column(String)
    image_link = Column(String)
    content = Column(String)
    pub_time = Column(DateTime, index=True)
    chapter_number = Column(Integer, index=True)
    time4sort = Column(DateTime, index=True)
    num4sort = Column(Integer, index=True)
    # 动态外键关联（需要创建时赋值）
    @declared_attr
    def website_id(cls): # todo 改名
        return Column(Integer, ForeignKey('source_meta.id'))  # config.source_meta

    def export_to_dict(self) -> ArticleDict:
        article = {}
        for column in self.__table__.columns: # type: ignore
            if column.primary_key or column.name == "website_id":
                continue
            article[column.name] = getattr(self, column.name)
        return article # type: ignore

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id}, title='{self.title}', pub_time={self.pub_time})>"

    @staticmethod
    def create_article_model(table_name) -> type:
        """动态创建文章表的工厂函数"""
        class_name = f"ArticleOf{table_name}"
        # 使用type动态创建类
        return type(
            class_name,
            (ArticleBase, Base),
            {
                '__tablename__': table_name,
                '__mapper_args__': {
                    'polymorphic_identity': table_name
                }
            }
        )
    # 运行时，如果创建两次就会出错，因此需要缓存结果，非线程安全
    @staticmethod
    def get_article_model(table_name) -> type:
        """获取动态创建的文章表模型"""
        if article_models.get(table_name):
            return article_models[table_name]
        ArticleModel = ArticleBase.create_article_model(table_name)
        article_models[table_name] = ArticleModel
        return ArticleModel
